#!/usr/bin/env python3
"""Deterministically search the HOI4 UI icon asset JSONL index.

Examples:
    python search_assets.py --index assets/library-index.jsonl --query "坦克 工业" \
        --style tno --icon-type focus --limit 8
    python search_assets.py --index assets/library-index.jsonl --query "factory" --json
    python search_assets.py --self-test

The script is deliberately dependency-free. It uses filename, stem, path, tags, and
small bilingual alias groups; it does not use a network service, embeddings, or a
vector database.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence


STYLE_ALIASES: dict[str, tuple[str, ...]] = {
    "vanilla": ("vanilla", "original", "base game", "原版", "本体"),
    "tfr": ("tfr", "the fire rises", "fire rises", "烈焰升腾"),
    "tno": ("tno", "the new order", "new order", "新秩序"),
    "red-flood": ("red flood", "red-flood", "red_flood", "rf", "赤潮"),
}

ICON_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "focus": ("focus", "national focus", "focus tree", "国策", "国策树"),
    "idea": (
        "idea",
        "national spirit",
        "national_spirit",
        "country spirit",
        "国家精神",
        "民族精神",
    ),
    "technology": ("technology", "tech", "technology tree", "科技", "科技树"),
    "other-ui": (
        "other ui",
        "other-ui",
        "other_ui",
        "decision",
        "decisions",
        "ideology",
        "portrait",
        "event",
        "super event",
        "super_event",
        "flag",
        "map",
        "law",
        "category",
        "scripted gui",
        "scripted_gui",
        "决议",
        "意识形态",
        "肖像",
        "事件",
        "超事件",
        "旗帜",
        "地图",
        "法律",
        "法案",
        "分类",
        "脚本界面",
    ),
}

ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "finished": ("finished", "final", "ready", "成品", "现成", "现成素材"),
    "component": ("component", "part", "piece", "素材", "部件", "图标素材"),
    "background": ("background", "frame", "base", "底面", "底图", "边框", "背景"),
    "template": ("template", "模板"),
    "palette": ("palette", "color card", "colour card", "调色板", "色卡", "色号"),
    "editable_source": ("editable source", "editable_source", "可编辑源", "工程文件"),
    "tutorial": ("tutorial", "guide", "教程", "指南"),
    "reference": ("reference", "reference asset", "reference_asset", "example", "参考", "示例"),
    "archive": ("archive", "container", "压缩包", "归档"),
}

# These compact groups cover common HOI4 icon subjects. They intentionally remain
# small and auditable; filename/path/tag matching still handles arbitrary subjects.
SUBJECT_ALIASES: dict[str, tuple[str, ...]] = {
    "industry": ("industry", "industrial", "factory", "factories", "工业", "工厂", "制造业"),
    "economy": ("economy", "economic", "finance", "经济", "财政", "金融"),
    "agriculture": ("agriculture", "farm", "farmer", "农业", "农场", "农民"),
    "infrastructure": ("infrastructure", "construction", "基建", "基础设施", "建设"),
    "building": ("building", "architecture", "modern building", "建筑", "大楼", "城市建筑"),
    "transport": ("transport", "railway", "railroad", "road", "交通", "铁路", "公路"),
    "army": ("army", "land force", "infantry", "陆军", "军队", "步兵"),
    "navy": ("navy", "naval", "fleet", "ship", "海军", "舰队", "舰船"),
    "air-force": ("air force", "airforce", "aircraft", "plane", "空军", "飞机", "航空"),
    "tank": ("tank", "tanks", "armor", "armour", "armored", "armoured", "坦克", "装甲"),
    "artillery": ("artillery", "cannon", "gun", "火炮", "大炮", "炮兵"),
    "weapon": ("weapon", "weapons", "rifle", "arms", "武器", "步枪", "军备"),
    "research": ("research", "science", "scientific", "科研", "研究", "科学"),
    "nuclear": ("nuclear", "atomic", "nuke", "核能", "核武", "原子能"),
    "politics": ("politics", "political", "government", "政治", "政府"),
    "diplomacy": ("diplomacy", "diplomatic", "外交"),
    "alliance": ("alliance", "ally", "allies", "faction", "联盟", "盟友", "阵营"),
    "war": ("war", "warfare", "battle", "战争", "战斗"),
    "peace": ("peace", "peaceful", "和平"),
    "law": ("law", "legal", "legislation", "法律", "法案"),
    "propaganda": ("propaganda", "宣传"),
    "revolution": ("revolution", "revolutionary", "革命"),
    "democracy": ("democracy", "democratic", "民主"),
    "communism": ("communism", "communist", "socialism", "共产主义", "社会主义", "共产"),
    "fascism": ("fascism", "fascist", "法西斯"),
    "monarchy": ("monarchy", "monarchist", "king", "crown", "君主", "王室", "王冠"),
    "religion": ("religion", "religious", "church", "宗教", "教会"),
    "leader": ("leader", "portrait", "领导人", "领袖", "肖像"),
    "flag": ("flag", "banner", "国旗", "旗帜"),
    "oil": ("oil", "petroleum", "石油"),
    "steel": ("steel", "metal", "钢铁", "金属"),
    "red": ("red", "crimson", "scarlet", "红色", "赤色"),
    "blue": ("blue", "cyan", "蓝色", "青色"),
    "gold": ("gold", "golden", "金色", "黄金"),
}

ALL_CONCEPT_ALIASES: dict[str, tuple[str, ...]] = {
    **STYLE_ALIASES,
    **ICON_TYPE_ALIASES,
    **ROLE_ALIASES,
    **SUBJECT_ALIASES,
}

QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "hoi4",
    "icon",
    "of",
    "the",
    "ui",
    "with",
    "一个",
    "一张",
    "制作",
    "做",
    "图标",
    "和",
    "与",
    "的",
}

PATH_KEYS = ("path", "relative_path", "source_path", "file_path", "filepath")
TAG_KEYS = ("tags", "keywords", "aliases", "subjects", "concepts", "title", "name")
AUTHOR_KEYS = ("author", "artist", "creator", "credit", "credits")
LICENSE_KEYS = (
    "license",
    "licence",
    "license_name",
    "license_note",
    "usage_note",
    "rights",
)
POLICY_KEYS = ("reuse_policy", "use_policy", "license_status", "reuse")


@dataclass(frozen=True)
class QueryConcept:
    """One requested concept with equivalent Chinese/English spellings."""

    name: str
    variants: tuple[str, ...]


def normalize_text(value: Any) -> str:
    """Normalize user/index text without destroying CJK characters."""

    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).casefold().replace("\\", "/")
    text = re.sub(r"[_\-.]+", " ", text)
    text = re.sub(r"[^\w\u3400-\u9fff/]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def compact_text(value: Any) -> str:
    """Return an alphanumeric/CJK form suited to exact and substring checks."""

    return "".join(character for character in normalize_text(value) if character.isalnum())


def _flatten_strings(value: Any) -> Iterator[str]:
    if value is None:
        return
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
        return
    if isinstance(value, Mapping):
        for nested in value.values():
            yield from _flatten_strings(nested)
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        for nested in value:
            yield from _flatten_strings(nested)
        return
    yield str(value)


def field_strings(record: Mapping[str, Any], keys: Iterable[str]) -> list[str]:
    values: list[str] = []
    for key in keys:
        values.extend(_flatten_strings(record.get(key)))
    return values


def split_index_values(values: Iterable[str]) -> list[str]:
    """Split list-like metadata while retaining meaningful full phrases."""

    result: list[str] = []
    for value in values:
        stripped = value.strip()
        if not stripped:
            continue
        result.append(stripped)
        result.extend(part.strip() for part in re.split(r"[,;|，；]", stripped) if part.strip())
    return list(dict.fromkeys(result))


def first_display_value(record: Mapping[str, Any], keys: Iterable[str], default: str = "unknown") -> str:
    for value in field_strings(record, keys):
        if value:
            return value
    return default


def _query_contains_variant(normalized_query: str, variant: str) -> bool:
    normalized_variant = normalize_text(variant)
    if not normalized_variant:
        return False
    if any("\u3400" <= character <= "\u9fff" for character in normalized_variant):
        return compact_text(normalized_variant) in compact_text(normalized_query)
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(normalized_variant)}(?![a-z0-9])",
            normalized_query,
        )
    )


def build_query_concepts(query: str) -> list[QueryConcept]:
    normalized_query = normalize_text(query)
    concepts: list[QueryConcept] = []
    selected_variants: list[str] = []

    for canonical, variants in ALL_CONCEPT_ALIASES.items():
        expanded = tuple(dict.fromkeys((canonical, *variants)))
        if any(_query_contains_variant(normalized_query, variant) for variant in expanded):
            concepts.append(QueryConcept(canonical, expanded))
            selected_variants.extend(expanded)

    tokens = re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", normalized_query)
    for token in tokens:
        residual = token
        for variant in selected_variants:
            normalized_variant = normalize_text(variant)
            if not normalized_variant or " " in normalized_variant:
                continue
            if residual == normalized_variant:
                residual = ""
                break
            if any("\u3400" <= character <= "\u9fff" for character in normalized_variant):
                residual = residual.replace(normalized_variant, " ")
        for part in residual.split():
            if part in QUERY_STOPWORDS or len(compact_text(part)) < 2:
                continue
            concepts.append(QueryConcept(part, (part,)))

    deduplicated: list[QueryConcept] = []
    seen: set[str] = set()
    for concept in concepts:
        key = compact_text(concept.name)
        if key and key not in seen:
            seen.add(key)
            deduplicated.append(concept)
    return deduplicated


def canonicalize(value: str, aliases: Mapping[str, tuple[str, ...]]) -> str:
    compact_value = compact_text(value)
    if not compact_value:
        return ""
    for canonical, variants in aliases.items():
        if compact_value in {compact_text(item) for item in (canonical, *variants)}:
            return canonical
    return normalize_text(value).replace(" ", "-")


def canonical_field_values(
    record: Mapping[str, Any], keys: Iterable[str], aliases: Mapping[str, tuple[str, ...]]
) -> list[str]:
    raw_values = split_index_values(field_strings(record, keys))
    return list(dict.fromkeys(filter(None, (canonicalize(value, aliases) for value in raw_values))))


def record_path(record: Mapping[str, Any]) -> str:
    for key in PATH_KEYS:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().replace("\\", "/")
    filename = record.get("filename") or record.get("file_name")
    return str(filename).strip().replace("\\", "/") if filename else ""


def record_filename_and_stem(record: Mapping[str, Any], path: str) -> tuple[str, str]:
    explicit_filename = record.get("filename") or record.get("file_name")
    filename = str(explicit_filename).strip() if explicit_filename else path.rsplit("/", 1)[-1]
    explicit_stem = record.get("stem")
    stem = str(explicit_stem).strip() if explicit_stem else filename.rsplit(".", 1)[0]
    return filename, stem


def canonical_reuse_policy(record: Mapping[str, Any]) -> tuple[str, bool]:
    """Return a conservative policy and whether rights permit direct reuse."""

    explicit_direct = record.get("direct_reuse")
    policy_text = " ".join(field_strings(record, POLICY_KEYS)).strip()
    license_text = " ".join(field_strings(record, LICENSE_KEYS)).strip()
    policy_compact = compact_text(policy_text)
    license_compact = compact_text(license_text)

    reference_markers = (
        "referenceonly",
        "noreuse",
        "donotreuse",
        "restricted",
        "forbidden",
        "仅供参考",
        "禁止复用",
        "禁止使用",
    )
    if any(compact_text(marker) in policy_compact for marker in reference_markers):
        return "reference_only", False

    credit_markers = ("creditrequired", "withcredit", "attribution", "ccby", "需要署名", "署名")
    if any(compact_text(marker) in policy_compact for marker in credit_markers):
        return "credit_required", explicit_direct is not False

    allowed_markers = (
        "allowed",
        "approved",
        "permitted",
        "freetouse",
        "publicdomain",
        "cc0",
        "可复用",
        "允许使用",
        "免费使用",
    )
    if any(compact_text(marker) in policy_compact for marker in allowed_markers):
        return "approved", explicit_direct is not False

    # A precise index policy takes precedence over a broad library note. For
    # example, finished AoM icons are credit_required even though the library as
    # a whole must not be re-uploaded.
    if policy_compact:
        if policy_compact in {"unknown", compact_text("未知")}:
            return "unknown", False
        return canonicalize(policy_text, {}) or "unknown", False

    license_reference_markers = (
        *reference_markers,
        "noreupload",
        "禁止转载",
        "禁止重新上传",
    )
    if any(compact_text(marker) in license_compact for marker in license_reference_markers):
        return "reference_only", False
    if any(compact_text(marker) in license_compact for marker in credit_markers):
        return "credit_required", explicit_direct is not False
    if any(compact_text(marker) in license_compact for marker in allowed_markers):
        return "approved", explicit_direct is not False

    if explicit_direct is True:
        return "approved", True
    if explicit_direct is False:
        return "reference_only", False
    return "unknown", False


def canonical_authorization(record: Mapping[str, Any], reuse_policy: str) -> str:
    """Return the authorization vocabulary accepted by finalize_icon.py."""

    if reuse_policy in {"approved", "credit_required"}:
        return reuse_policy
    policy_text = " ".join(field_strings(record, POLICY_KEYS)).strip()
    license_text = " ".join(field_strings(record, LICENSE_KEYS)).strip()
    combined = compact_text(f"{policy_text} {license_text}")
    forbidden_markers = ("forbidden", "禁止使用")
    if any(compact_text(marker) in combined for marker in forbidden_markers):
        return "forbidden"
    return "unknown"


def _safe_contains(haystack: str, needle: str) -> bool:
    if not haystack or not needle:
        return False
    minimum = 2 if any("\u3400" <= character <= "\u9fff" for character in needle) else 3
    return len(needle) >= minimum and needle in haystack


def score_text_match(record: Mapping[str, Any], query: str) -> tuple[int, list[str], int]:
    path = record_path(record)
    filename, stem = record_filename_and_stem(record, path)
    path_compact = compact_text(path)
    filename_compact = compact_text(filename)
    stem_compact = compact_text(stem)
    path_components = [compact_text(component) for component in path.replace("\\", "/").split("/")]
    tag_values = split_index_values(field_strings(record, TAG_KEYS))
    tag_compacts = [compact_text(value) for value in tag_values if compact_text(value)]
    metadata_values = [
        *field_strings(record, ("style", "styles")),
        *field_strings(record, ("icon_type", "icon_types", "type", "category")),
        *field_strings(record, ("role", "asset_role")),
    ]
    metadata_compacts = [compact_text(value) for value in metadata_values if compact_text(value)]

    score = 0
    reasons: list[str] = []
    query_compact = compact_text(query)
    if query_compact:
        if filename_compact == query_compact:
            score += 150
            reasons.append("exact filename match (+150)")
        elif stem_compact == query_compact:
            score += 145
            reasons.append("exact stem match (+145)")
        elif _safe_contains(stem_compact, query_compact):
            score += 65
            reasons.append("full query appears in stem (+65)")
        elif _safe_contains(path_compact, query_compact):
            score += 30
            reasons.append("full query appears in path (+30)")

    concepts = build_query_concepts(query)
    matched_concepts = 0
    for concept in concepts:
        best_score = 0
        best_reason = ""
        for variant in concept.variants:
            needle = compact_text(variant)
            if not needle:
                continue
            candidates: list[tuple[int, str]] = []
            if stem_compact == needle:
                candidates.append((50, f"concept '{concept.name}' exactly matches stem (+50)"))
            elif _safe_contains(stem_compact, needle):
                candidates.append((32, f"concept '{concept.name}' appears in stem (+32)"))
            if needle in tag_compacts:
                candidates.append((30, f"concept '{concept.name}' exactly matches a tag (+30)"))
            elif any(_safe_contains(tag, needle) for tag in tag_compacts):
                candidates.append((18, f"concept '{concept.name}' appears in a tag (+18)"))
            if needle in path_components:
                candidates.append((22, f"concept '{concept.name}' exactly matches a path part (+22)"))
            elif _safe_contains(path_compact, needle):
                candidates.append((11, f"concept '{concept.name}' appears in path (+11)"))
            if needle in metadata_compacts:
                candidates.append((14, f"concept '{concept.name}' matches index metadata (+14)"))
            if candidates:
                candidate_score, candidate_reason = max(candidates, key=lambda item: item[0])
                if candidate_score > best_score:
                    best_score, best_reason = candidate_score, candidate_reason
        if best_score:
            matched_concepts += 1
            score += best_score
            reasons.append(best_reason)

    if len(concepts) > 1 and matched_concepts == len(concepts):
        score += 15
        reasons.append("all query concepts matched (+15)")
    return score, reasons, matched_concepts


def score_preference(
    label: str,
    requested: str | None,
    actual_values: Sequence[str],
    aliases: Mapping[str, tuple[str, ...]],
    match_weight: int,
    mismatch_penalty: int,
) -> tuple[int, list[str], bool]:
    if not requested:
        return 0, [], False
    canonical_requested = canonicalize(requested, aliases)
    if canonical_requested in actual_values:
        return match_weight, [f"{label} matches '{canonical_requested}' (+{match_weight})"], False
    if actual_values:
        found = ", ".join(actual_values)
        return (
            -mismatch_penalty,
            [f"{label} mismatch: wanted '{canonical_requested}', found '{found}' (-{mismatch_penalty})"],
            True,
        )
    return 0, [], False


def score_record(
    record: Mapping[str, Any],
    query: str,
    style: str | None,
    icon_type: str | None,
    role: str | None,
) -> dict[str, Any] | None:
    path = record_path(record)
    filename, stem = record_filename_and_stem(record, path)
    styles = canonical_field_values(record, ("style", "styles"), STYLE_ALIASES)
    icon_types = canonical_field_values(
        record, ("icon_type", "icon_types", "type", "category"), ICON_TYPE_ALIASES
    )
    roles = canonical_field_values(record, ("role", "asset_role"), ROLE_ALIASES)

    text_score, reasons, matched_concepts = score_text_match(record, query)
    if query.strip() and text_score <= 0:
        return None

    score = text_score
    metadata_mismatch = False
    for preference in (
        score_preference("style", style, styles, STYLE_ALIASES, 34, 14),
        score_preference("icon type", icon_type, icon_types, ICON_TYPE_ALIASES, 30, 12),
        score_preference("role", role, roles, ROLE_ALIASES, 24, 10),
    ):
        delta, preference_reasons, mismatched = preference
        score += delta
        reasons.extend(preference_reasons)
        metadata_mismatch = metadata_mismatch or mismatched

    reuse_policy, rights_allow_direct = canonical_reuse_policy(record)
    readiness = first_display_value(record, ("readiness",), default="unknown")
    readiness_blocks_direct = compact_text(readiness) in {
        "referenceonly",
        "archiveonly",
    }
    is_finished = "finished" in roles
    direct_reuse = (
        is_finished
        and rights_allow_direct
        and not metadata_mismatch
        and not readiness_blocks_direct
    )
    composite_reuse = (
        not is_finished
        and rights_allow_direct
        and not metadata_mismatch
        and not readiness_blocks_direct
    )
    if direct_reuse:
        score += 28
        reasons.append("finished asset is eligible for direct reuse (+28)")
    elif is_finished:
        score += 8
        if reuse_policy == "reference_only":
            reasons.append("finished asset is reference-only; direct reuse disabled (+8)")
        else:
            reasons.append("finished asset has unverified direct-reuse suitability (+8)")
    if reuse_policy == "reference_only":
        score -= 4
        reasons.append("reference-only policy penalty (-4)")

    author = first_display_value(record, AUTHOR_KEYS)
    license_value = first_display_value(record, LICENSE_KEYS)
    authorization = canonical_authorization(record, reuse_policy)
    return {
        "id": record.get("id") or record.get("asset_id"),
        "path": path,
        "filename": filename,
        "stem": stem,
        "score": score,
        "reasons": reasons,
        "author": author,
        "license": license_value,
        "authorization": authorization,
        "reuse_policy": reuse_policy,
        "readiness": readiness,
        "direct_reuse": direct_reuse,
        "recommended_use": "direct" if direct_reuse else "composite" if composite_reuse else "reference",
        "style": styles[0] if styles else None,
        "icon_type": icon_types[0] if icon_types else None,
        "role": roles[0] if roles else None,
        "matched_concepts": matched_concepts,
    }


def load_jsonl(index_path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with index_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                value = json.loads(stripped)
            except json.JSONDecodeError as error:
                print(f"warning: skipped malformed JSONL line {line_number}: {error}", file=sys.stderr)
                continue
            if not isinstance(value, dict):
                print(f"warning: skipped non-object JSONL line {line_number}", file=sys.stderr)
                continue
            records.append(value)
    return records


def search_records(
    records: Iterable[Mapping[str, Any]],
    query: str = "",
    style: str | None = None,
    icon_type: str | None = None,
    role: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for record in records:
        result = score_record(record, query, style, icon_type, role)
        if result is not None:
            results.append(result)
    results.sort(
        key=lambda result: (
            -int(result["score"]),
            not bool(result["direct_reuse"]),
            normalize_text(result["path"]),
        )
    )
    return results[:limit]


def print_plain(results: Sequence[Mapping[str, Any]]) -> None:
    if not results:
        print("No matching assets.")
        return
    for position, result in enumerate(results, start=1):
        print(f"{position}. [{result['score']}] {result['path'] or '<missing path>'}")
        print(
            "   "
            f"use={result['recommended_use']} "
            f"style={result['style'] or 'unknown'} "
            f"icon_type={result['icon_type'] or 'unknown'} "
            f"role={result['role'] or 'unknown'}"
        )
        print(
            "   "
            f"author={result['author']} "
            f"license={result['license']} "
            f"authorization={result['authorization']} "
            f"reuse_policy={result['reuse_policy']}"
        )
        print(f"   reasons: {'; '.join(result['reasons']) or 'metadata-only result'}")


def run_self_test() -> int:
    sample_records = [
        {
            "asset_id": "direct-tank",
            "relative_path": "TNO/finished/tank.png",
            "style": "tno",
            "icon_type": "focus",
            "role": "finished",
            "tags": ["装甲", "军队"],
            "creator": "Artist A",
            "license_note": "Free to use with credit; do not re-upload the source library.",
            "reuse_policy": "credit_required",
            "readiness": "direct_with_credit",
        },
        {
            "id": "reference-tank",
            "path": "TNO/reference/tank.png",
            "style": "tno",
            "icon_type": "focus",
            "role": "finished",
            "tags": ["tank"],
            "author": "Artist B",
            "license": "reference only",
            "reuse_policy": "reference_only",
            "direct_reuse": True,
        },
        {
            "id": "factory-zh",
            "relative_path": "素材库/国策图标/工厂.png",
            "tags": ["工业", "生产"],
            "role": "component",
            "reuse_policy": "approved",
            "readiness": "composite",
        },
        {
            "id": "red-flood-ideology",
            "relative_path": "赤潮/意识形态/acceleratism.png",
            "style": "red-flood",
            "icon_type": "ideology",
            "role": "component",
            "tags": ["意识形态"],
        },
        {"path": "misc/unknown.png"},
    ]

    with tempfile.TemporaryDirectory(prefix="hoi4-icon-search-") as temporary_directory:
        index_path = Path(temporary_directory) / "sample.jsonl"
        with index_path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in sample_records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        loaded = load_jsonl(index_path)

    tank_results = search_records(
        loaded, query="坦克", style="TNO", icon_type="国策", role="finished", limit=10
    )
    assert tank_results, "bilingual tank query returned no results"
    assert tank_results[0]["id"] == "direct-tank", "direct finished asset was not ranked first"
    reference_result = next(result for result in tank_results if result["id"] == "reference-tank")
    assert reference_result["direct_reuse"] is False, "reference_only asset was marked direct"
    assert reference_result["recommended_use"] == "reference"
    assert reference_result["authorization"] == "unknown"
    assert tank_results[0]["authorization"] == "credit_required"

    factory_results = search_records(loaded, query="factory", limit=10)
    assert factory_results and factory_results[0]["id"] == "factory-zh", "English-to-Chinese alias failed"
    assert factory_results[0]["authorization"] == "approved"
    assert factory_results[0]["recommended_use"] == "composite"

    missing_field_results = search_records(loaded, query="unknown", limit=10)
    assert missing_field_results, "record with missing metadata was not handled"
    assert missing_field_results[0]["reuse_policy"] == "unknown"
    assert missing_field_results[0]["direct_reuse"] is False

    other_ui_results = search_records(
        loaded, query="意识形态", style="red-flood", icon_type="other-ui", limit=10
    )
    assert other_ui_results and other_ui_results[0]["id"] == "red-flood-ideology"
    assert other_ui_results[0]["icon_type"] == "other-ui", "other-ui umbrella mapping failed"

    print("self-test: ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search a HOI4 UI icon JSONL index with deterministic bilingual scoring."
    )
    parser.add_argument("--index", type=Path, help="Path to the JSONL asset index.")
    parser.add_argument("--query", default="", help="Chinese/English filename, subject, path, or tag query.")
    parser.add_argument("--style", help="Preferred style, e.g. vanilla, tfr, tno, or red-flood.")
    parser.add_argument("--icon-type", help="Preferred icon type: focus, idea, technology, or other-ui.")
    parser.add_argument("--role", help="Preferred asset role, e.g. finished, component, frame, or template.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum result count (default: 10).")
    parser.add_argument("--json", action="store_true", help="Write a UTF-8 JSON array instead of text.")
    parser.add_argument("--self-test", action="store_true", help="Run the built-in dependency-free smoke test.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_test()
    if args.index is None:
        parser.error("--index is required unless --self-test is used")
    if args.limit <= 0:
        parser.error("--limit must be greater than zero")
    if not any((args.query.strip(), args.style, args.icon_type, args.role)):
        parser.error("provide --query or at least one of --style/--icon-type/--role")
    if not args.index.is_file():
        parser.error(f"index file does not exist: {args.index}")

    records = load_jsonl(args.index)
    results = search_records(
        records,
        query=args.query,
        style=args.style,
        icon_type=args.icon_type,
        role=args.role,
        limit=args.limit,
    )
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print_plain(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
