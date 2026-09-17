#!/usr/bin/env python3
"""Build a deterministic, read-only index for the local HOI4 UI asset library."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    from PIL import Image
except ImportError:  # Pillow is optional; standard-library readers remain available.
    Image = None


COLLECTION_NAMES = ("素材库", "秋起美术馆")
EXCLUDED_EXTENSIONS = {".exe", ".lnk"}
ARCHIVE_EXTENSIONS = {".7z", ".rar", ".zip"}
EDITABLE_EXTENSIONS = {".pdn", ".psd", ".xcf"}
RASTER_EXTENSIONS = {".jpeg", ".jpg", ".png"}
RENDERABLE_EXTENSIONS = RASTER_EXTENSIONS | {".dds"}
REFERENCE_EXTENSIONS = {
    ".doc",
    ".docx",
    ".md",
    ".mp4",
    ".txt",
}
PREVIEW_PRIORITY = {".png": 0, ".jpg": 1, ".jpeg": 2}
EDITABLE_PRIORITY = {".psd": 0, ".xcf": 1, ".pdn": 2}

CORE_LICENSE_NOTE = (
    "AoM/Ultimate HOI4 GFX local terms: free to use with contributor consent; "
    "do not re-upload the library; credit finished-icon creators."
)


@dataclass(frozen=True)
class FileEntry:
    collection: str
    path: Path
    relative_path: str


@dataclass(frozen=True)
class ImageMetadata:
    width: int | None = None
    height: int | None = None
    alpha: bool | None = None
    detected_format: str | None = None
    error: str | None = None


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", value))


def alias_matches(normalized_haystack: str, alias: str) -> bool:
    needle = normalize_text(alias)
    if not needle:
        return False
    if re.fullmatch(r"[a-z0-9]+", needle):
        return needle in normalized_haystack.split()
    return needle in normalized_haystack


def infer_alias(table: dict[str, list[str]], text: str, default: str) -> str:
    normalized = normalize_text(text)
    for canonical, aliases in table.items():
        if any(alias_matches(normalized, alias) for alias in aliases):
            return canonical
    return default


def load_aliases(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        aliases = json.load(handle)
    if not isinstance(aliases, dict):
        raise ValueError(f"Aliases file must contain a JSON object: {path}")
    for key in ("style_aliases", "icon_type_aliases", "role_aliases", "semantic_tags"):
        if not isinstance(aliases.get(key), dict):
            raise ValueError(f"Aliases file is missing object field {key!r}: {path}")
    return aliases


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def sniff_format(path: Path) -> str | None:
    with path.open("rb") as handle:
        header = handle.read(12)
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(b"8BPS"):
        return "psd"
    if header.startswith(b"DDS "):
        return "dds"
    return None


def read_png_header(path: Path) -> ImageMetadata:
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValueError("not a PNG payload")
        width = height = None
        color_type = None
        has_transparency_chunk = False
        while True:
            length_bytes = handle.read(4)
            if len(length_bytes) != 4:
                break
            length = struct.unpack(">I", length_bytes)[0]
            chunk_type = handle.read(4)
            if len(chunk_type) != 4:
                break
            data = handle.read(length)
            if len(data) != length or len(handle.read(4)) != 4:
                break
            if chunk_type == b"IHDR" and len(data) >= 10:
                width, height = struct.unpack(">II", data[:8])
                color_type = data[9]
            elif chunk_type == b"tRNS":
                has_transparency_chunk = True
            elif chunk_type in {b"IDAT", b"IEND"}:
                break
        if width is None or height is None:
            raise ValueError("PNG IHDR is missing or truncated")
        alpha = color_type in {4, 6} or has_transparency_chunk
        return ImageMetadata(width, height, alpha, "png")


def read_jpeg_header(path: Path) -> ImageMetadata:
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ValueError("not a JPEG payload")
        while True:
            byte = handle.read(1)
            if not byte:
                break
            if byte != b"\xff":
                continue
            while byte == b"\xff":
                byte = handle.read(1)
            if not byte:
                break
            marker = byte[0]
            if marker in {0x01, 0xD8, 0xD9}:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) != 2:
                break
            segment_length = struct.unpack(">H", length_bytes)[0]
            if segment_length < 2:
                raise ValueError("invalid JPEG segment length")
            if marker in sof_markers:
                data = handle.read(5)
                if len(data) != 5:
                    break
                height, width = struct.unpack(">HH", data[1:5])
                return ImageMetadata(width, height, False, "jpg")
            handle.seek(segment_length - 2, os.SEEK_CUR)
    raise ValueError("JPEG SOF marker is missing or truncated")


def read_psd_header(path: Path) -> ImageMetadata:
    with path.open("rb") as handle:
        header = handle.read(26)
    if len(header) < 26 or header[:4] != b"8BPS":
        raise ValueError("not a PSD payload")
    version = struct.unpack(">H", header[4:6])[0]
    if version not in {1, 2}:
        raise ValueError(f"unsupported PSD version {version}")
    height, width = struct.unpack(">II", header[14:22])
    if width <= 0 or height <= 0:
        raise ValueError("invalid PSD dimensions")
    return ImageMetadata(width, height, None, "psd")


def read_dds_header(path: Path) -> ImageMetadata:
    with path.open("rb") as handle:
        header = handle.read(20)
    if len(header) < 20 or header[:4] != b"DDS ":
        raise ValueError("not a DDS payload")
    header_size = struct.unpack("<I", header[4:8])[0]
    if header_size != 124:
        raise ValueError(f"invalid DDS header size {header_size}")
    height, width = struct.unpack("<II", header[12:20])
    if width <= 0 or height <= 0:
        raise ValueError("invalid DDS dimensions")
    return ImageMetadata(width, height, None, "dds")


def read_with_pillow(path: Path) -> ImageMetadata:
    if Image is None:
        raise RuntimeError("Pillow is unavailable")
    with Image.open(path) as image:
        width, height = image.size
        detected = (image.format or "").casefold()
        if detected == "jpeg":
            detected = "jpg"
        alpha = "A" in image.getbands() or "transparency" in image.info
        if detected == "jpg":
            alpha = False
        return ImageMetadata(width, height, alpha, detected or None)


def read_image_metadata(path: Path, extension: str) -> ImageMetadata:
    try:
        if extension == ".psd":
            return read_psd_header(path)
        if extension == ".dds":
            return read_dds_header(path)
        if extension in RASTER_EXTENSIONS and Image is not None:
            try:
                return read_with_pillow(path)
            except Exception:
                pass
        detected = sniff_format(path)
        if detected == "png":
            return read_png_header(path)
        if detected == "jpg":
            return read_jpeg_header(path)
        if detected == "psd":
            return read_psd_header(path)
        if detected == "dds":
            return read_dds_header(path)
        return ImageMetadata(error="unsupported or unrecognized image payload")
    except (OSError, ValueError, struct.error) as exc:
        return ImageMetadata(error=str(exc))


def scan_entries(
    library_root: Path, excluded_paths: set[Path]
) -> tuple[list[FileEntry], Counter[str], list[str], int]:
    entries: list[FileEntry] = []
    excluded = Counter()
    missing_collections: list[str] = []
    skipped_symlinks = 0

    for collection in COLLECTION_NAMES:
        collection_root = library_root / collection
        if not collection_root.is_dir():
            missing_collections.append(collection)
            continue
        for dirpath, dirnames, filenames in os.walk(collection_root, followlinks=False):
            dirnames[:] = sorted(
                (name for name in dirnames if not (Path(dirpath) / name).is_symlink()),
                key=lambda item: (item.casefold(), item),
            )
            for filename in sorted(filenames, key=lambda item: (item.casefold(), item)):
                path = Path(dirpath) / filename
                if path.is_symlink():
                    skipped_symlinks += 1
                    continue
                try:
                    resolved = path.resolve()
                except OSError:
                    resolved = path.absolute()
                if resolved in excluded_paths:
                    excluded["output"] += 1
                    continue
                extension = path.suffix.casefold()
                if extension in EXCLUDED_EXTENSIONS:
                    excluded[extension.lstrip(".")] += 1
                    continue
                relative_path = path.relative_to(library_root).as_posix()
                entries.append(FileEntry(collection, path, relative_path))

    entries.sort(key=lambda entry: (entry.relative_path.casefold(), entry.relative_path))
    return entries, excluded, missing_collections, skipped_symlinks


def infer_style(entry: FileEntry, aliases: dict[str, Any]) -> str:
    parts = entry.relative_path.split("/")
    normalized_parts = {normalize_text(part) for part in parts}
    if "tfr" in normalized_parts:
        return "tfr"
    if "tno" in normalized_parts:
        return "tno"
    if "赤潮" in normalized_parts:
        return "red-flood"
    if "原版" in normalized_parts:
        return "vanilla"
    if entry.collection == "素材库":
        return "vanilla"
    return infer_alias(aliases["style_aliases"], entry.relative_path, "unknown")


def infer_icon_type(entry: FileEntry, aliases: dict[str, Any]) -> str:
    text = entry.relative_path
    normalized = normalize_text(text)
    parts = set(text.split("/"))
    if {"国家精神底面", "国家精神模板"} & parts:
        return "idea"
    if {"国策图标", "国策底面", "国策模板", "现成素材"} & parts:
        return "focus"
    if "意识形态" in normalized or "ideology" in normalized.split():
        return "ideology"
    if "领导人底面" in parts or "肖像" in normalized or "头像" in normalized:
        return "portrait"
    if "旗帜模板" in parts:
        return "flag"
    if "地图模板" in parts:
        return "map"
    if "超事件" in normalized:
        return "super_event"
    return infer_alias(aliases["icon_type_aliases"], text, "unknown")


def infer_role(entry: FileEntry, aliases: dict[str, Any]) -> str:
    extension = entry.path.suffix.casefold()
    text = entry.relative_path
    normalized = normalize_text(text)
    parts = set(text.split("/"))
    if extension in ARCHIVE_EXTENSIONS:
        return "archive"
    if "现成素材" in parts or "结果" in normalized:
        return "finished"
    if "教程" in normalized or "guide" in normalized.split():
        return "tutorial"
    if any(word in normalized for word in ("调色板", "色卡", "色号")) or "palette" in normalized.split():
        return "palette"
    if "底面" in normalized or "ideology background" in normalized:
        return "background"
    aliased = infer_alias(aliases["role_aliases"], text, "unknown")
    if aliased != "unknown":
        return aliased
    if extension in REFERENCE_EXTENSIONS:
        return "reference"
    if extension in EDITABLE_EXTENSIONS:
        return "editable_source"
    if "国策图标" in parts or "通用 素材合集" in normalized:
        return "component"
    if extension in RENDERABLE_EXTENSIONS:
        return "reference_asset"
    return "reference"


def infer_creator(entry: FileEntry) -> str:
    parts = entry.relative_path.split("/")
    try:
        marker = parts.index("现成素材")
    except ValueError:
        return "unknown"
    if marker + 1 < len(parts) - 1:
        return parts[marker + 1]
    return "unknown"


def load_permissions_index(path: Path | None) -> dict[str, dict[str, Any]]:
    """Read a previously reviewed, hash-bound authorization snapshot."""
    if path is None:
        return {}
    permissions: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        policy = record.get("reuse_policy")
        if policy not in {"approved", "credit_required", "forbidden"}:
            continue
        source = record.get("relative_path")
        evidence = record.get("authorization_evidence")
        content_hash = record.get("content_hash")
        if not isinstance(source, str) or not isinstance(evidence, str) or not evidence.strip():
            continue
        if not isinstance(content_hash, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", content_hash):
            continue
        if policy == "credit_required" and record.get("creator", "unknown") in {"", "unknown", None}:
            continue
        if source in permissions:
            raise ValueError(f"duplicate authorization path: {source}")
        permissions[source] = record
    return permissions


def infer_reuse_policy(
    entry: FileEntry, creator: str, content_hash: str | None = None,
    permissions: dict[str, dict[str, Any]] | None = None,
) -> tuple[str, str]:
    record = (permissions or {}).get(entry.relative_path)
    if record and content_hash and record["content_hash"] == content_hash:
        return record["reuse_policy"], record.get("license_note", "See authorization_evidence")
    return "unknown", "unknown"


def infer_readiness(role: str, reuse_policy: str) -> str:
    if role == "archive":
        return "archive_only"
    if reuse_policy in {"unknown", "forbidden"}:
        return "reference_only"
    if role in {"palette", "reference", "tutorial"}:
        return "reference_only"
    if role == "finished":
        return "direct_with_credit" if reuse_policy == "credit_required" else "direct"
    if role in {"background", "component", "editable_source", "template"}:
        return "composite"
    return "reference_only"


def semantic_tags(entry: FileEntry, aliases: dict[str, Any]) -> set[str]:
    normalized = normalize_text(entry.relative_path)
    tags: set[str] = set()
    for canonical, keywords in aliases["semantic_tags"].items():
        if any(alias_matches(normalized, keyword) for keyword in keywords):
            tags.add(canonical)
    stem = normalize_text(entry.path.stem)
    for token in stem.split():
        if len(token) >= 2 and not token.isdigit():
            tags.add(token)
    return tags


def group_key(entry: FileEntry) -> tuple[str, str]:
    parent = Path(entry.relative_path).parent.as_posix().casefold()
    return parent, entry.path.stem.casefold()


def select_link(
    candidates: Iterable[FileEntry], priorities: dict[str, int]
) -> str | None:
    eligible = [item for item in candidates if item.path.suffix.casefold() in priorities]
    if not eligible:
        return None
    eligible.sort(
        key=lambda item: (
            priorities[item.path.suffix.casefold()],
            item.relative_path.casefold(),
            item.relative_path,
        )
    )
    return eligible[0].relative_path


def normalized_format(value: str | None) -> str | None:
    if value == "jpeg":
        return "jpg"
    return value


def build_record(
    entry: FileEntry,
    aliases: dict[str, Any],
    grouped_entries: dict[tuple[str, str], list[FileEntry]],
    permissions: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    extension = entry.path.suffix.casefold()
    file_format = extension.lstrip(".") or "none"
    metadata = (
        read_image_metadata(entry.path, extension)
        if extension in RENDERABLE_EXTENSIONS | {".psd"}
        else ImageMetadata()
    )
    quality_flags: set[str] = set()
    try:
        content_hash = sha256_file(entry.path)
    except OSError as exc:
        content_hash = None
        quality_flags.add(f"read_error:{exc.__class__.__name__}")

    style = infer_style(entry, aliases)
    icon_type = infer_icon_type(entry, aliases)
    role = infer_role(entry, aliases)
    creator = infer_creator(entry)
    reuse_policy, license_note = infer_reuse_policy(entry, creator, content_hash, permissions)
    authorization_evidence = None
    if reuse_policy != "unknown":
        permission = permissions[entry.relative_path]
        authorization_evidence = permission["authorization_evidence"]
        creator = permission.get("creator", creator)
    readiness = infer_readiness(role, reuse_policy)
    paired = grouped_entries[group_key(entry)]

    editable_source = select_link(paired, EDITABLE_PRIORITY)
    preview_path = select_link(paired, PREVIEW_PRIORITY)
    if extension in EDITABLE_EXTENSIONS:
        editable_source = entry.relative_path
    if extension in PREVIEW_PRIORITY:
        preview_path = entry.relative_path

    # `renderable` means the file can be inspected directly by Codex image tools.
    # DDS remains game-usable source data but requires a non-destructive PNG preview.
    renderable = extension in RASTER_EXTENSIONS and metadata.width is not None
    expected = normalized_format(file_format)
    detected = normalized_format(metadata.detected_format)
    if detected is not None and expected != detected:
        quality_flags.add("extension_payload_mismatch")
    if metadata.error and extension in RENDERABLE_EXTENSIONS | {".psd"}:
        quality_flags.add("image_metadata_error")
    if extension in {".pdn", ".xcf"}:
        quality_flags.add("dimensions_unavailable")
    elif extension in RENDERABLE_EXTENSIONS | {".psd"} and metadata.width is None:
        quality_flags.add("dimensions_unavailable")
    if extension == ".png" and metadata.alpha is False:
        quality_flags.add("opaque_raster")
    if role == "archive":
        quality_flags.add("archive_not_extracted")
    if extension == ".dds" and preview_path is None:
        quality_flags.add("preview_conversion_required")
    if reuse_policy == "unknown":
        quality_flags.add("license_unknown")
    if creator == "unknown" and role == "finished":
        quality_flags.add("creator_unknown")
    if reuse_policy == "credit_required":
        quality_flags.add("credit_required")
    if style == "unknown":
        quality_flags.add("style_unknown")
    if icon_type == "unknown":
        quality_flags.add("icon_type_unknown")
    if "outdated" in normalize_text(entry.relative_path):
        quality_flags.add("outdated")
    if extension in EDITABLE_EXTENSIONS and preview_path is None:
        quality_flags.add("preview_missing")
    if re.search(r"(?i)(?:^|[ _(-])(copy|untitled|image\d*)(?:$|[ _)])", entry.path.stem):
        quality_flags.add("name_needs_normalization")

    tags = semantic_tags(entry, aliases)
    tags.update(value for value in (style, icon_type, role) if value != "unknown")
    asset_key = unicodedata.normalize("NFKC", entry.relative_path).casefold()
    asset_id = f"hoi4ui-{hashlib.sha256(asset_key.encode('utf-8')).hexdigest()[:20]}"

    return {
        "alpha": metadata.alpha,
        "authorization_evidence": authorization_evidence,
        "asset_id": asset_id,
        "collection": entry.collection,
        "content_hash": content_hash,
        "creator": creator,
        "editable_source": editable_source,
        "format": file_format,
        "height": metadata.height,
        "icon_type": icon_type,
        "license_note": license_note,
        "preview_path": preview_path,
        "quality_flags": sorted(quality_flags),
        "readiness": readiness,
        "relative_path": entry.relative_path,
        "renderable": renderable,
        "reuse_policy": reuse_policy,
        "role": role,
        "style": style,
        "tags": sorted(tags, key=lambda item: (item.casefold(), item)),
        "width": metadata.width,
    }


def count_field(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts = Counter(str(record[field]) for record in records)
    return dict(sorted(counts.items(), key=lambda item: (item[0].casefold(), item[0])))


def build_summary(
    records: list[dict[str, Any]],
    excluded: Counter[str],
    missing_collections: list[str],
    skipped_symlinks: int,
) -> dict[str, Any]:
    quality_flags = Counter(
        flag for record in records for flag in record.get("quality_flags", [])
    )
    return {
        "counts": {
            field: count_field(records, field)
            for field in (
                "collection",
                "format",
                "icon_type",
                "readiness",
                "role",
                "style",
            )
        },
        "excluded": dict(sorted(excluded.items())),
        "hash_errors": sum(record["content_hash"] is None for record in records),
        "image_metadata_errors": sum(
            "image_metadata_error" in record["quality_flags"] for record in records
        ),
        "indexed": len(records),
        "missing_collections": sorted(missing_collections),
        "pillow_available": Image is not None,
        "quality_flags": dict(sorted(quality_flags.items())),
        "skipped_symlinks": skipped_symlinks,
    }


def write_jsonl(records: list[dict[str, Any]], destination: str) -> None:
    if destination == "-":
        handle = sys.stdout
        close_handle = False
    else:
        path = Path(destination).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("w", encoding="utf-8", newline="\n")
        close_handle = True
    try:
        for record in records:
            handle.write(
                json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            handle.write("\n")
    finally:
        if close_handle:
            handle.close()


def write_summary(summary: dict[str, Any], destination: str) -> None:
    payload = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if destination == "-":
        sys.stderr.write(payload)
        return
    path = Path(destination).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)


def resolved_output_paths(output: str, summary: str | None) -> set[Path]:
    paths: set[Path] = set()
    for value in (output, summary):
        if value and value != "-":
            paths.add(Path(value).expanduser().resolve())
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_aliases = Path(__file__).resolve().parents[1] / "assets" / "aliases.json"
    parser = argparse.ArgumentParser(
        description="Build a stable JSONL index without modifying source assets."
    )
    parser.add_argument(
        "--library-root",
        required=True,
        type=Path,
        help="Directory containing 素材库 and 秋起美术馆.",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="JSONL output path, or - for stdout (default: -).",
    )
    parser.add_argument(
        "--summary",
        nargs="?",
        const="-",
        help="Optional summary JSON path; omit the value to print it to stderr.",
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=default_aliases,
        help=f"Alias JSON path (default: {default_aliases}).",
    )
    parser.add_argument(
        "--permissions-index", type=Path,
        help="Reviewed JSONL with exact paths, hashes and authorization_evidence; new/changed files remain unknown.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    library_root = args.library_root.expanduser().resolve()
    if not library_root.is_dir():
        raise SystemExit(f"Library root is not a directory: {library_root}")
    aliases = load_aliases(args.aliases.expanduser().resolve())
    permissions = load_permissions_index(args.permissions_index)
    entries, excluded, missing, skipped_symlinks = scan_entries(
        library_root, resolved_output_paths(args.output, args.summary)
    )
    grouped: dict[tuple[str, str], list[FileEntry]] = defaultdict(list)
    for entry in entries:
        grouped[group_key(entry)].append(entry)
    records = [build_record(entry, aliases, grouped, permissions) for entry in entries]
    records.sort(key=lambda record: (record["relative_path"].casefold(), record["relative_path"]))
    write_jsonl(records, args.output)
    if args.summary is not None:
        write_summary(
            build_summary(records, excluded, missing, skipped_symlinks), args.summary
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
