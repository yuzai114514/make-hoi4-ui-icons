#!/usr/bin/env python3
"""Finalize and validate transparent HOI4 UI icons.

This script is intentionally deterministic. It does not create artwork or edit
the source asset in place; it only trims, scales, pads, validates, and can emit
an optional spriteTypes snippet for a confirmed mod root.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - environment-dependent
    raise SystemExit(
        "Pillow is required. Run this script with the Codex bundled Python "
        "runtime or install Pillow in the active environment."
    ) from exc


PROFILES: dict[str, dict[str, int]] = {
    "focus": {
        "width": 170,
        "height": 150,
        "padding": 4,
        "safe_bottom": 40,
        "required_safe_bottom": 40,
        "safe_bottom_alpha_max": 0,
    },
    "focus-tfr": {
        "width": 170,
        "height": 150,
        "padding": 6,
        "safe_bottom": 40,
        "required_safe_bottom": 40,
        "safe_bottom_alpha_max": 0,
    },
    "idea": {"width": 68, "height": 68, "padding": 3, "safe_bottom": 0},
    "technology": {"width": 64, "height": 64, "padding": 3, "safe_bottom": 0},
}

PROFILE_ALIASES = {
    "focus-vanilla": "focus",
    "national-focus": "focus",
    "national_spirit": "idea",
    "national-spirit": "idea",
    "idea-vanilla": "idea",
    "technology-standard": "technology",
    "tech": "technology",
}

SPRITE_RE = re.compile(r"^GFX_[A-Za-z0-9_]+$")
SOURCE_AUTHORIZATIONS = {"approved", "credit_required", "unknown", "forbidden"}
SOURCE_USES = {"reused", "transformed", "reference_only", "excluded"}
SOURCE_ROLES = {
    "finished",
    "finished_icon",
    "component",
    "template",
    "background",
    "symbol",
    "style_reference",
    "subject_reference",
    "reference_asset",
    "editable_source",
    "palette",
}
SOURCE_RECORD_FIELDS = {"asset_id", "source", "role", "authorization", "use", "credit"}
ASSET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
LAYER_KINDS = {"theme", "structural-effect", "narrative-effect"}
LAYER_BLENDS = {"normal", "screen", "multiply"}


def resolve_profile(args: argparse.Namespace) -> dict[str, int]:
    profile_name = PROFILE_ALIASES.get(args.profile, args.profile)
    if profile_name == "custom":
        if not args.width or not args.height:
            raise ValueError("custom profile requires --width and --height")
        base = {"width": args.width, "height": args.height, "padding": 0, "safe_bottom": 0}
    else:
        if profile_name not in PROFILES:
            raise ValueError(f"unknown profile: {args.profile}")
        base = dict(PROFILES[profile_name])

    if args.width:
        base["width"] = args.width
    if args.height:
        base["height"] = args.height
    if args.padding is not None:
        base["padding"] = args.padding
    if args.safe_bottom is not None:
        base["safe_bottom"] = args.safe_bottom

    required_safe_bottom = base.get("required_safe_bottom", 0)
    if base["safe_bottom"] < required_safe_bottom:
        raise ValueError(
            f"{profile_name} requires --safe-bottom of at least "
            f"{required_safe_bottom}"
        )

    if profile_name in {"focus", "focus-tfr"} and (
        base["width"] not in {170, 210}
        or base["height"] != 150
        or base["safe_bottom"] != 40
    ):
        raise ValueError("focus canvas must be 170x150 or 210x150 with safe_bottom 40")
    if profile_name == "idea" and (base["width"], base["height"]) != (68, 68):
        raise ValueError("idea canvas must be 68x68")

    if base["width"] <= 0 or base["height"] <= 0:
        raise ValueError("width and height must be positive")
    if base["padding"] < 0 or base["safe_bottom"] < 0:
        raise ValueError("padding and safe-bottom cannot be negative")
    if 2 * base["padding"] >= base["width"]:
        raise ValueError("padding leaves no horizontal content area")
    if 2 * base["padding"] + base["safe_bottom"] >= base["height"]:
        raise ValueError("padding/safe-bottom leave no vertical content area")
    return base


def alpha_bbox(image: Image.Image, threshold: int) -> tuple[int, int, int, int] | None:
    alpha = image.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > threshold else 0)
    return mask.getbbox()


def choose_output_path(requested: Path, overwrite: bool) -> Path:
    if overwrite or not requested.exists():
        return requested
    stem, suffix = requested.stem, requested.suffix
    version = 2
    while True:
        candidate = requested.with_name(f"{stem}-v{version}{suffix}")
        if not candidate.exists():
            return candidate
        version += 1


def with_version(path: Path, version: int) -> Path:
    suffixes = "".join(path.suffixes)
    base_name = path.name[: -len(suffixes)] if suffixes else path.name
    return path.with_name(f"{base_name}-v{version}{suffixes}")


def choose_output_pair(
    requested_output: Path, requested_manifest: Path, overwrite: bool
) -> tuple[Path, Path]:
    if overwrite:
        return requested_output, requested_manifest
    if not requested_output.exists() and not requested_manifest.exists():
        return requested_output, requested_manifest
    version = 2
    while True:
        output = with_version(requested_output, version)
        manifest = with_version(requested_manifest, version)
        if not output.exists() and not manifest.exists():
            return output, manifest
        version += 1


def relative_manifest_path(path: Path, root: Path, label: str) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError(f"{label} must be inside --manifest-root: {path}") from exc


def load_source_records(
    records_path_value: str | None, manifest_root: Path, creation_mode: str
) -> tuple[list[dict[str, Any]], list[str]]:
    if records_path_value is None:
        raw_records: list[Any] = []
    else:
        records_path = Path(records_path_value).resolve()
        relative_manifest_path(records_path, manifest_root, "source records file")
        if not records_path.is_file():
            raise ValueError(f"source records file does not exist: {records_path}")
        try:
            payload = json.loads(records_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"source records file is not valid JSON: {exc.msg}") from exc
        raw_records = [payload] if isinstance(payload, dict) else payload
        if not isinstance(raw_records, list):
            raise ValueError("source records file must contain a JSON object or array")

    records: list[dict[str, Any]] = []
    credits: list[str] = []
    direct_pixel_uses = 0

    for position, raw_record in enumerate(raw_records, start=1):
        if not isinstance(raw_record, dict):
            raise ValueError(f"source record {position} must be a JSON object")
        record = dict(raw_record)

        missing = sorted(SOURCE_RECORD_FIELDS - record.keys())
        extra = sorted(record.keys() - SOURCE_RECORD_FIELDS)
        if missing:
            raise ValueError(
                f"source record {position} is missing required fields: {', '.join(missing)}"
            )
        if extra:
            raise ValueError(f"source record {position} has unknown fields: {', '.join(extra)}")

        for key in ("asset_id", "source", "role", "authorization", "use"):
            if not isinstance(record[key], str) or not record[key].strip():
                raise ValueError(f"source record {position} field '{key}' must be a non-empty string")
        if not ASSET_ID_RE.fullmatch(record["asset_id"]):
            raise ValueError(f"source record {position} asset_id has an invalid format")
        if record["role"] not in SOURCE_ROLES:
            raise ValueError(
                f"source record {position} role must be one of: "
                + ", ".join(sorted(SOURCE_ROLES))
            )

        source = record["source"].replace("\\", "/")
        source_path = PurePosixPath(source)
        if source_path.is_absolute() or ".." in source_path.parts or ":" in source_path.parts[0]:
            raise ValueError(f"source record {position} source must be library-root relative")
        record["source"] = source

        authorization = record["authorization"]
        use = record["use"]
        if authorization not in SOURCE_AUTHORIZATIONS:
            raise ValueError(
                f"source record {position} authorization must be one of: "
                + ", ".join(sorted(SOURCE_AUTHORIZATIONS))
            )
        if use not in SOURCE_USES:
            raise ValueError(
                f"source record {position} use must be one of: "
                + ", ".join(sorted(SOURCE_USES))
            )

        if authorization in {"unknown", "forbidden"} and use in {"reused", "transformed"}:
            raise ValueError(
                f"source record {position} cannot {use} an {authorization} source"
            )
        if authorization == "forbidden" and use != "excluded":
            raise ValueError(f"source record {position} forbidden sources must use 'excluded'")

        credit = record["credit"]
        if credit is not None and (not isinstance(credit, str) or not credit.strip()):
            raise ValueError(f"source record {position} credit must be a non-empty string or null")
        if authorization == "credit_required" and use in {"reused", "transformed"} and not credit:
            raise ValueError(f"source record {position} requires a creator credit")
        if credit and credit not in credits:
            credits.append(credit)
        if use in {"reused", "transformed"}:
            direct_pixel_uses += 1
        records.append(record)

    if creation_mode == "reused" and direct_pixel_uses == 0:
        raise ValueError("creation-mode reused requires an authorized reused/transformed source record")
    if creation_mode in {"generated", "reference_guided"} and direct_pixel_uses:
        raise ValueError(f"creation-mode {creation_mode} cannot include reused/transformed source pixels")
    return records, credits


def load_optional_json_file(
    path_value: str | None, manifest_root: Path, label: str
) -> tuple[str | None, dict[str, Any] | None]:
    if path_value is None:
        return None, None
    raw_path = Path(path_value)
    path = raw_path.resolve() if raw_path.is_absolute() else (manifest_root / raw_path).resolve()
    relative = relative_manifest_path(path, manifest_root, label)
    if not path.is_file():
        raise ValueError(f"{label} does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return relative, payload


def sanitize_layer_report(
    payload: dict[str, Any] | None, manifest_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    if payload is None:
        return [], None
    raw_layers = payload.get("layers")
    validation = payload.get("validation")
    if not isinstance(raw_layers, list):
        raise ValueError("layer report field 'layers' must be an array")
    if not isinstance(validation, dict):
        raise ValueError("layer report field 'validation' must be an object")

    layers: list[dict[str, Any]] = []
    for position, raw_layer in enumerate(raw_layers, start=1):
        if not isinstance(raw_layer, dict):
            raise ValueError(f"layer report entry {position} must be an object")
        layer_id = raw_layer.get("id")
        owner_id = raw_layer.get("owner_id")
        kind = raw_layer.get("kind")
        role = raw_layer.get("role")
        blend = raw_layer.get("blend")
        z = raw_layer.get("z")
        path = raw_layer.get("path")
        for key, value in {
            "id": layer_id,
            "owner_id": owner_id,
            "kind": kind,
            "role": role,
            "blend": blend,
        }.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"layer report entry {position} field '{key}' must be a string")
        if kind not in LAYER_KINDS:
            raise ValueError(f"layer report entry {position} has an invalid kind")
        if blend not in LAYER_BLENDS:
            raise ValueError(f"layer report entry {position} has an invalid blend mode")
        if isinstance(z, bool) or not isinstance(z, int):
            raise ValueError(f"layer report entry {position} field 'z' must be an integer")
        if path is not None:
            if not isinstance(path, str) or not path.strip():
                raise ValueError(f"layer report entry {position} field 'path' is invalid")
            normalized = path.replace("\\", "/")
            source_path = PurePosixPath(normalized)
            if source_path.is_absolute() or ".." in source_path.parts or ":" in source_path.parts[0]:
                raise ValueError(f"layer report entry {position} path must be workspace-relative")
            resolved_path = (manifest_root / Path(*source_path.parts)).resolve()
            try:
                resolved_path.relative_to(manifest_root)
            except ValueError as exc:
                raise ValueError(
                    f"layer report entry {position} path must remain inside the manifest root"
                ) from exc
            if not resolved_path.is_file():
                raise ValueError(f"layer report entry {position} path does not exist")
            path = normalized
        layers.append(
            {
                "id": layer_id,
                "owner_id": owner_id,
                "kind": kind,
                "role": role,
                "z": z,
                "blend": blend,
                "path": path,
            }
        )

    allowed_validation = {
        "ok",
        "theme_count",
        "narrative_effect_count",
        "structural_effect_count",
        "safe_bottom_alpha_max",
        "key_green_pixels",
        "key_magenta_pixels",
        "errors",
        "warnings",
    }
    sanitized_validation = {
        key: validation[key] for key in allowed_validation if key in validation
    }
    if sanitized_validation.get("ok") is not True:
        raise ValueError("layer report validation must be successful")
    return layers, sanitized_validation


def count_key_colors(
    image: Image.Image, alpha_threshold: int
) -> tuple[int, int]:
    pixels = image.load()
    green = 0
    magenta = 0
    for y in range(image.height):
        for x in range(image.width):
            red, value_green, blue, alpha = pixels[x, y]
            if alpha <= alpha_threshold:
                continue
            if value_green > 200 and red < 24 and blue < 24:
                green += 1
            if red > 200 and blue > 200 and value_green < 24:
                magenta += 1
    return green, magenta


def validate_image(
    path: Path, expected: dict[str, int] | None, alpha_threshold: int,
    chroma_key: str = "none",
) -> dict[str, Any]:
    if chroma_key not in {"none", "green", "magenta"}:
        raise ValueError("chroma-key must be none, green, or magenta")
    errors: list[str] = []
    warnings: list[str] = []
    if not path.is_file():
        return {"ok": False, "path": str(path), "errors": ["file does not exist"], "warnings": []}

    try:
        with Image.open(path) as raw:
            raw.load()
            mode = raw.mode
            width, height = raw.size
            image = raw.convert("RGBA")
    except Exception as exc:
        return {"ok": False, "path": str(path), "errors": [f"image cannot be decoded: {exc}"], "warnings": []}

    if mode != "RGBA":
        errors.append(f"final image mode must be RGBA, got {mode}")
    if expected and (width != expected["width"] or height != expected["height"]):
        errors.append(
            f"dimensions must be {expected['width']}x{expected['height']}, got {width}x{height}"
        )

    alpha = image.getchannel("A")
    minimum, maximum = alpha.getextrema()
    bbox = alpha_bbox(image, alpha_threshold)
    if maximum == 0 or bbox is None:
        errors.append("image contains no visible pixels")
        coverage = 0.0
    else:
        visible = sum(alpha.histogram()[alpha_threshold + 1 :])
        coverage = visible / float(width * height)
        if coverage < 0.03:
            warnings.append(f"visible subject coverage is very small ({coverage:.1%})")
        if coverage > 0.92:
            warnings.append(f"visible subject coverage is very high ({coverage:.1%})")
        left, top, right, bottom = bbox
        if left == 0 or top == 0 or right == width or bottom == height:
            warnings.append("visible subject touches a canvas edge; inspect intentional break-frame art")

    if minimum > 0:
        errors.append("image has no fully transparent pixels")
    corners = [
        image.getpixel((0, 0))[3],
        image.getpixel((width - 1, 0))[3],
        image.getpixel((0, height - 1))[3],
        image.getpixel((width - 1, height - 1))[3],
    ]
    if any(value > alpha_threshold for value in corners):
        warnings.append("one or more canvas corners are not transparent")

    key_green_pixels, key_magenta_pixels = count_key_colors(
        image, alpha_threshold
    )
    if chroma_key == "green" and key_green_pixels:
        errors.append(
            f"image contains {key_green_pixels} visible chroma-key-green pixels"
        )
    if chroma_key == "magenta" and key_magenta_pixels:
        errors.append(
            f"image contains {key_magenta_pixels} visible chroma-key-magenta pixels"
        )

    safe_bottom_alpha_max: int | None = None
    if expected and expected.get("safe_bottom", 0) and (width, height) == (
        expected["width"],
        expected["height"],
    ):
        safe_bottom = max(
            expected["safe_bottom"], expected.get("required_safe_bottom", 0)
        )
        safe_bottom_alpha_max = alpha.crop((0, height - safe_bottom, width, height)).getextrema()[1]
        safe_bottom_limit = expected.get("safe_bottom_alpha_max", alpha_threshold)
        if safe_bottom_alpha_max > safe_bottom_limit:
            errors.append(
                f"bottom {safe_bottom}px title-safe area contains visible pixels "
                f"(alpha max {safe_bottom_alpha_max})"
            )

    return {
        "ok": not errors,
        "path": str(path),
        "mode": mode,
        "width": width,
        "height": height,
        "alpha_min": minimum,
        "alpha_max": maximum,
        "visible_bbox": list(bbox) if bbox else None,
        "visible_coverage": round(coverage, 6),
        "safe_bottom_alpha_max": safe_bottom_alpha_max,
        "key_green_pixels": key_green_pixels,
        "key_magenta_pixels": key_magenta_pixels,
        "chroma_key": chroma_key,
        "errors": errors,
        "warnings": warnings,
    }


def finalize(args: argparse.Namespace) -> int:
    source = Path(args.input).resolve()
    if not source.is_file():
        raise ValueError(f"input does not exist: {source}")
    profile = resolve_profile(args)
    manifest_root = Path(args.manifest_root).resolve()
    if not manifest_root.is_dir():
        raise ValueError(f"manifest root does not exist: {manifest_root}")
    source_records, record_credits = load_source_records(
        args.source_records, manifest_root, args.creation_mode
    )
    brief_path, _ = load_optional_json_file(args.brief, manifest_root, "brief file")
    composition_path, _ = load_optional_json_file(
        args.composition, manifest_root, "composition file"
    )
    layer_report_path, layer_report_payload = load_optional_json_file(
        args.layer_report, manifest_root, "layer report"
    )
    layers, layer_validation = sanitize_layer_report(layer_report_payload, manifest_root)
    source_manifest_path = relative_manifest_path(source, manifest_root, "input")
    requested_output = Path(args.output).resolve()
    requested_manifest = (
        Path(args.manifest).resolve()
        if args.manifest
        else requested_output.with_suffix(".manifest.json")
    )
    relative_manifest_path(requested_output, manifest_root, "output")
    relative_manifest_path(requested_manifest, manifest_root, "manifest")
    output, manifest_path = choose_output_pair(
        requested_output, requested_manifest, args.overwrite
    )
    output_manifest_path = relative_manifest_path(output, manifest_root, "output")
    relative_manifest_path(manifest_path, manifest_root, "manifest")

    with Image.open(source) as raw:
        raw.load()
        image = raw.convert("RGBA")

    if image.getchannel("A").getextrema()[0] > 0:
        raise ValueError("input has no fully transparent pixels; remove its background before finalizing")

    bbox = alpha_bbox(image, args.alpha_threshold)
    if bbox is None:
        raise ValueError("input contains no visible pixels")
    if args.layout == "preserve-canvas":
        if image.size != (profile["width"], profile["height"]):
            raise ValueError(
                "preserve-canvas input dimensions must exactly match the selected profile"
            )
        if profile["safe_bottom"]:
            safe_bottom = max(
                profile["safe_bottom"], profile.get("required_safe_bottom", 0)
            )
            alpha = image.getchannel("A")
            bottom_alpha_max = alpha.crop(
                (
                    0,
                    profile["height"] - safe_bottom,
                    profile["width"],
                    profile["height"],
                )
            ).getextrema()[1]
            safe_bottom_limit = profile.get(
                "safe_bottom_alpha_max", args.alpha_threshold
            )
            if bottom_alpha_max > safe_bottom_limit:
                raise ValueError(
                    f"preserve-canvas input has visible pixels in the bottom "
                    f"{safe_bottom}px title-safe area"
                )
        canvas = image.copy()
    else:
        if not args.no_trim:
            image = image.crop(bbox)

        content_width = profile["width"] - 2 * profile["padding"]
        content_height = profile["height"] - 2 * profile["padding"] - profile["safe_bottom"]
        scale = min(content_width / image.width, content_height / image.height)
        if not args.allow_upscale:
            scale = min(scale, 1.0)
        new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        if new_size != image.size:
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        canvas = Image.new("RGBA", (profile["width"], profile["height"]), (0, 0, 0, 0))
        x = (profile["width"] - image.width) // 2
        content_top = profile["padding"]
        content_bottom = profile["height"] - profile["padding"] - profile["safe_bottom"]
        y = content_top + max(0, (content_bottom - content_top - image.height) // 2)
        canvas.alpha_composite(image, (x, y))

    key_green_pixels, key_magenta_pixels = count_key_colors(
        canvas, args.alpha_threshold
    )
    key_errors: list[str] = []
    if args.chroma_key == "green" and key_green_pixels:
        key_errors.append(
            f"{key_green_pixels} visible chroma-key-green pixels"
        )
    if args.chroma_key == "magenta" and key_magenta_pixels:
        key_errors.append(
            f"{key_magenta_pixels} visible chroma-key-magenta pixels"
        )
    if key_errors:
        raise ValueError("final image contains " + " and ".join(key_errors))

    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)

    report = validate_image(output, profile, args.alpha_threshold, args.chroma_key)
    manifest_report = dict(report)
    manifest_report["path"] = output_manifest_path
    credits = list(dict.fromkeys([*record_credits, *args.credit]))
    manifest = {
        "creation_mode": args.creation_mode,
        "style": args.style,
        "icon_type": args.icon_type,
        "profile": args.profile,
        "layout": args.layout,
        "chroma_key": args.chroma_key,
        "user_prompt": args.prompt,
        "normalized_prompt": args.normalized_prompt,
        "source_assets": source_records,
        "credits": credits,
        "source_image": source_manifest_path,
        "output_image": output_manifest_path,
        "width": profile["width"],
        "height": profile["height"],
        "padding": profile["padding"],
        "safe_bottom": profile["safe_bottom"],
        "validation": manifest_report,
    }
    if brief_path is not None:
        manifest["brief_file"] = brief_path
    if composition_path is not None:
        manifest["composition_file"] = composition_path
    if layer_report_path is not None:
        manifest["layer_report_file"] = layer_report_path
        manifest["layers"] = layers
        manifest["layer_validation"] = layer_validation
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"output": str(output), "manifest": str(manifest_path), "validation": report}, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def validate_command(args: argparse.Namespace) -> int:
    expected = resolve_profile(args) if args.profile else None
    report = validate_image(Path(args.input).resolve(), expected, args.alpha_threshold, args.chroma_key)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def gfx_command(args: argparse.Namespace) -> int:
    if not SPRITE_RE.fullmatch(args.sprite_name):
        raise ValueError("sprite name must match GFX_[A-Za-z0-9_]+")
    texture_path = args.texture_path.replace("\\", "/")
    if not texture_path.startswith("gfx/") or ":" in texture_path or ".." in texture_path.split("/"):
        raise ValueError("texture path must be a safe mod-relative path beginning with gfx/")
    output = choose_output_path(Path(args.output).resolve(), args.overwrite)
    output.parent.mkdir(parents=True, exist_ok=True)
    text = (
        "spriteTypes = {\n"
        "    spriteType = {\n"
        f'        name = "{args.sprite_name}"\n'
        f'        texturefile = "{texture_path}"\n'
        "    }\n"
        "}\n"
    )
    output.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output), "sprite_name": args.sprite_name, "texturefile": texture_path}, indent=2))
    return 0


def add_profile_arguments(parser: argparse.ArgumentParser, *, optional: bool = False) -> None:
    parser.add_argument(
        "--profile",
        required=not optional,
        choices=sorted(set(PROFILES) | set(PROFILE_ALIASES) | {"custom"}),
        help="Verified output profile. Use custom with explicit width/height for target-mod dimensions.",
    )
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--padding", type=int)
    parser.add_argument("--safe-bottom", type=int)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    finalize_parser = subparsers.add_parser("finalize", help="Trim, fit, pad, save, and validate a PNG")
    finalize_parser.add_argument("--input", required=True)
    finalize_parser.add_argument("--output", required=True)
    finalize_parser.add_argument("--manifest")
    finalize_parser.add_argument("--manifest-root", required=True)
    add_profile_arguments(finalize_parser)
    finalize_parser.add_argument("--allow-upscale", action="store_true")
    finalize_parser.add_argument("--no-trim", action="store_true")
    finalize_parser.add_argument(
        "--layout",
        choices=["fit-content", "preserve-canvas"],
        default="fit-content",
        help="Preserve an exact target-size layered composition or use the legacy trim-and-fit layout.",
    )
    finalize_parser.add_argument("--alpha-threshold", type=int, default=4)
    finalize_parser.add_argument("--chroma-key", choices=["none", "green", "magenta"], default="none",
                                 help="Actual removed background color; none for native alpha or reused art.")
    finalize_parser.add_argument("--overwrite", action="store_true")
    finalize_parser.add_argument("--creation-mode", choices=["reused", "generated", "reference_guided"], default="generated")
    finalize_parser.add_argument("--style", default="vanilla")
    finalize_parser.add_argument("--icon-type", default="focus")
    finalize_parser.add_argument("--prompt", default="")
    finalize_parser.add_argument("--normalized-prompt", default="")
    finalize_parser.add_argument(
        "--source-records",
        help="Workspace-local JSON object/array with asset_id/source/role/authorization/use/credit.",
    )
    finalize_parser.add_argument("--brief", help="Optional workspace-local layered brief JSON.")
    finalize_parser.add_argument(
        "--composition", help="Optional workspace-local layered composition JSON."
    )
    finalize_parser.add_argument(
        "--layer-report", help="Optional workspace-local report emitted by compose_layers.py."
    )
    finalize_parser.add_argument("--credit", action="append", default=[])
    finalize_parser.set_defaults(handler=finalize)

    validate_parser = subparsers.add_parser("validate", help="Validate an existing final icon")
    validate_parser.add_argument("--input", required=True)
    add_profile_arguments(validate_parser, optional=True)
    validate_parser.add_argument("--alpha-threshold", type=int, default=4)
    validate_parser.add_argument("--chroma-key", choices=["none", "green", "magenta"], default="none")
    validate_parser.set_defaults(handler=validate_command)

    gfx_parser = subparsers.add_parser("gfx", help="Emit a minimal additive spriteTypes file")
    gfx_parser.add_argument("--sprite-name", required=True)
    gfx_parser.add_argument("--texture-path", required=True)
    gfx_parser.add_argument("--output", required=True)
    gfx_parser.add_argument("--overwrite", action="store_true")
    gfx_parser.set_defaults(handler=gfx_command)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    sys.exit(main())
