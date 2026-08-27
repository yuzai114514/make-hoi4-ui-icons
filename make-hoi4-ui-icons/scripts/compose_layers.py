#!/usr/bin/env python3
"""Compose and validate PSD-like layered HOI4 UI icon packages."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError as exc:  # pragma: no cover - environment-dependent
    raise SystemExit(
        "Pillow is required. Run this script with the Codex bundled Python runtime."
    ) from exc


SCHEMA_VERSION = 1
BLEND_MODES = {"normal", "screen", "multiply"}
THEME_ROLES = {"primary", "secondary", "background", "context"}
BOUNDARY_TYPES = {"outline", "feather", "shadow", "relief"}
EFFECT_KINDS = {"narrative"}
BRIEF_INPUT_MODES = {"human", "ai"}
INPUT_BASIS_VALUES = {"provided", "derived", "missing"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ASSET_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
QA_LOGICAL_NAME_RE = re.compile(
    r"^(?:layer-map|light|dark|contact-sheet|"
    r"(?:theme|material-theme|material-effect)-[a-z0-9][a-z0-9-]*)$"
)


@dataclass
class Component:
    component_id: str
    owner_id: str
    kind: str
    role: str
    z: int
    order: int
    blend: str
    image: Image.Image
    filename: str | None = None


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return payload


def safe_relative_path(value: Any, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or not path.parts or ":" in path.parts[0]:
        raise ValueError(f"{label} must be a safe manifest-root-relative path")
    return path


def resolve_inside(root: Path, value: str | Path, label: str, *, must_exist: bool = False) -> Path:
    if isinstance(value, Path):
        candidate = value.resolve() if value.is_absolute() else (root / value).resolve()
    else:
        relative = safe_relative_path(value, label)
        candidate = (root / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must be inside --manifest-root") from exc
    if must_exist and not candidate.is_file():
        raise ValueError(f"{label} does not exist: {candidate}")
    return candidate


def resolve_spec_relative(
    root: Path, spec_dir: Path, value: Any, label: str, *, must_exist: bool = False
) -> Path:
    relative = safe_relative_path(value, label)
    candidate = (spec_dir / Path(*relative.parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} must remain inside --manifest-root") from exc
    if must_exist and not candidate.is_file():
        raise ValueError(f"{label} does not exist: {candidate}")
    return candidate


def relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def require_int(value: Any, label: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if minimum is not None and value < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    return value


def require_number(
    value: Any, label: str, *, minimum: float | None = None, maximum: float | None = None
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    if minimum is not None and result < minimum:
        raise ValueError(f"{label} must be at least {minimum}")
    if maximum is not None and result > maximum:
        raise ValueError(f"{label} must be at most {maximum}")
    return result


def parse_color(value: Any, label: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise ValueError(f"{label} must use #RRGGBB")
    return tuple(int(value[position : position + 2], 16) for position in (1, 3, 5))  # type: ignore[return-value]


def validate_asset_ids(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    result: list[str] = []
    for position, asset_id in enumerate(value, start=1):
        if not isinstance(asset_id, str) or not ASSET_ID_RE.fullmatch(asset_id):
            raise ValueError(f"{label}[{position}] has an invalid asset ID")
        result.append(asset_id)
    return result


def require_string_array(
    value: Any, label: str, *, minimum: int = 0
) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if len(value) < minimum:
        raise ValueError(f"{label} must contain at least {minimum} item(s)")
    result: list[str] = []
    for position, item in enumerate(value, start=1):
        result.append(require_string(item, f"{label}[{position}]"))
    return result


def multiply_alpha(image: Image.Image, opacity: float) -> Image.Image:
    if opacity >= 1.0:
        return image.copy()
    result = image.copy()
    alpha = result.getchannel("A").point(lambda value: round(value * opacity))
    result.putalpha(alpha)
    return result


def shift_channel(channel: Image.Image, dx: int, dy: int) -> Image.Image:
    shifted = Image.new("L", channel.size, 0)
    source_left = max(0, -dx)
    source_top = max(0, -dy)
    source_right = min(channel.width, channel.width - dx)
    source_bottom = min(channel.height, channel.height - dy)
    if source_right <= source_left or source_bottom <= source_top:
        return shifted
    crop = channel.crop((source_left, source_top, source_right, source_bottom))
    shifted.paste(crop, (source_left + dx, source_top + dy))
    return shifted


def color_layer(mask: Image.Image, color: tuple[int, int, int], opacity: float) -> Image.Image:
    alpha = mask.point(lambda value: round(value * opacity))
    layer = Image.new("RGBA", mask.size, (*color, 0))
    layer.putalpha(alpha)
    return layer


def blend_onto(base: Image.Image, layer: Image.Image, mode: str) -> Image.Image:
    if mode == "normal":
        result = base.copy()
        result.alpha_composite(layer)
        return result

    base_rgb = base.convert("RGB")
    layer_rgb = layer.convert("RGB")
    if mode == "screen":
        mixed_rgb = ImageChops.screen(base_rgb, layer_rgb)
    elif mode == "multiply":
        mixed_rgb = ImageChops.multiply(base_rgb, layer_rgb)
    else:  # validated before rendering
        raise ValueError(f"unsupported blend mode: {mode}")

    mixed_rgb = Image.composite(mixed_rgb, layer_rgb, base.getchannel("A"))
    mixed = mixed_rgb.convert("RGBA")
    mixed.putalpha(layer.getchannel("A"))
    result = base.copy()
    result.alpha_composite(mixed)
    return result


def transform_source(image: Image.Image, transform: dict[str, Any], label: str) -> tuple[Image.Image, int, int]:
    required = {"x", "y", "width", "height"}
    missing = sorted(required - transform.keys())
    if missing:
        raise ValueError(f"{label} transform is missing: {', '.join(missing)}")
    x = require_int(transform["x"], f"{label}.transform.x")
    y = require_int(transform["y"], f"{label}.transform.y")
    width = require_int(transform["width"], f"{label}.transform.width", minimum=1)
    height = require_int(transform["height"], f"{label}.transform.height", minimum=1)
    rotation = require_number(transform.get("rotation", 0), f"{label}.transform.rotation")

    transformed = image.resize((width, height), Image.Resampling.LANCZOS)
    if rotation:
        transformed = transformed.rotate(-rotation, resample=Image.Resampling.BICUBIC, expand=True)
    return transformed, x, y


def validate_source(path: Path, label: str) -> Image.Image:
    try:
        with Image.open(path) as raw:
            raw.load()
            mode = raw.mode
            image = raw.convert("RGBA")
    except Exception as exc:
        raise ValueError(f"{label} cannot be decoded: {exc}") from exc
    if mode != "RGBA":
        raise ValueError(f"{label} must be an RGBA PNG, got {mode}")
    if path.suffix.lower() != ".png":
        raise ValueError(f"{label} must be a PNG")
    if image.getchannel("A").getbbox() is None:
        raise ValueError(f"{label} contains no visible pixels")
    return image


def parse_effect(effect: Any, label: str, *, allowed: set[str]) -> tuple[str, dict[str, Any]]:
    if not isinstance(effect, dict):
        raise ValueError(f"{label} must be an object")
    effect_type = require_string(effect.get("type"), f"{label}.type")
    if effect_type not in allowed:
        raise ValueError(f"{label}.type must be one of: {', '.join(sorted(allowed))}")
    return effect_type, effect


def boundary_margin(boundary: dict[str, Any], finish: dict[str, Any], label: str) -> int:
    unknown_boundary = set(boundary) - {"primary", "support"}
    if unknown_boundary:
        raise ValueError(
            f"{label}.boundary has unknown entries: {', '.join(sorted(unknown_boundary))}"
        )
    margins = [0]
    primary_type, primary = parse_effect(boundary.get("primary"), f"{label}.boundary.primary", allowed=BOUNDARY_TYPES)
    support_raw = boundary.get("support")
    effects = [(primary_type, primary)]
    if support_raw is not None:
        support_type, support = parse_effect(
            support_raw, f"{label}.boundary.support", allowed=BOUNDARY_TYPES
        )
        if support_type == primary_type:
            raise ValueError(f"{label} boundary primary and support must use different types")
        effects.append((support_type, support))

    for effect_type, config in effects:
        if effect_type == "outline":
            margins.append(require_int(config.get("width"), f"{label}.outline.width", minimum=1) + 1)
            parse_color(config.get("color"), f"{label}.outline.color")
            require_number(config.get("opacity", 1), f"{label}.outline.opacity", minimum=0, maximum=1)
        elif effect_type == "feather":
            margins.append(math.ceil(require_number(config.get("radius"), f"{label}.feather.radius", minimum=0.1, maximum=20) * 3))
        elif effect_type == "shadow":
            offset = config.get("offset")
            if not isinstance(offset, list) or len(offset) != 2:
                raise ValueError(f"{label}.shadow.offset must be [x, y]")
            dx = require_int(offset[0], f"{label}.shadow.offset[0]")
            dy = require_int(offset[1], f"{label}.shadow.offset[1]")
            blur = require_number(config.get("blur"), f"{label}.shadow.blur", minimum=0, maximum=30)
            margins.append(math.ceil(max(abs(dx), abs(dy)) + blur * 3 + 1))
            parse_color(config.get("color"), f"{label}.shadow.color")
            require_number(config.get("opacity", 1), f"{label}.shadow.opacity", minimum=0, maximum=1)
        elif effect_type == "relief":
            margins.append(require_int(config.get("depth"), f"{label}.relief.depth", minimum=1) + 1)
            require_number(config.get("opacity", 0.2), f"{label}.relief.opacity", minimum=0, maximum=1)

    if not isinstance(finish, dict):
        raise ValueError(f"{label}.finish must be an object")
    unknown_finish = set(finish) - {"relief", "rim"}
    if unknown_finish:
        raise ValueError(f"{label}.finish has unknown entries: {', '.join(sorted(unknown_finish))}")
    if "relief" in finish:
        config = finish["relief"]
        if not isinstance(config, dict):
            raise ValueError(f"{label}.finish.relief must be an object")
        margins.append(require_int(config.get("depth"), f"{label}.finish.relief.depth", minimum=1) + 1)
        require_number(config.get("opacity", 0.15), f"{label}.finish.relief.opacity", minimum=0, maximum=0.35)
    if "rim" in finish:
        config = finish["rim"]
        if not isinstance(config, dict):
            raise ValueError(f"{label}.finish.rim must be an object")
        margins.append(require_int(config.get("width"), f"{label}.finish.rim.width", minimum=1) + 1)
        parse_color(config.get("color"), f"{label}.finish.rim.color")
        require_number(config.get("opacity", 0.12), f"{label}.finish.rim.opacity", minimum=0, maximum=0.3)
    return max(margins)


def build_relief(alpha: Image.Image, depth: int, opacity: float) -> Image.Image:
    edge_size = depth * 2 + 1
    dilated = alpha.filter(ImageFilter.MaxFilter(edge_size))
    eroded = alpha.filter(ImageFilter.MinFilter(edge_size))
    edge = ImageChops.subtract(dilated, eroded)
    highlight_mask = shift_channel(edge, -depth, -depth)
    shadow_mask = shift_channel(edge, depth, depth)
    highlight = color_layer(highlight_mask, (255, 238, 232), opacity)
    shadow = color_layer(shadow_mask, (26, 4, 10), opacity * 0.9)
    result = Image.new("RGBA", alpha.size, (0, 0, 0, 0))
    result.alpha_composite(shadow)
    result.alpha_composite(highlight)
    return result


def render_theme(
    theme: dict[str, Any],
    root: Path,
    spec_dir: Path,
    canvas_size: tuple[int, int],
    safe_bottom: int,
    index: int,
) -> tuple[list[Component], dict[str, Any], Image.Image, Image.Image]:
    label = f"themes[{index}]"
    theme_id = require_string(theme.get("id"), f"{label}.id")
    if not ID_RE.fullmatch(theme_id):
        raise ValueError(f"{label}.id must use lowercase ASCII letters, digits, and hyphens")
    name = require_string(theme.get("name"), f"{label}.name")
    role = require_string(theme.get("role"), f"{label}.role")
    if role not in THEME_ROLES:
        raise ValueError(f"{label}.role must be one of: {', '.join(sorted(THEME_ROLES))}")
    evidence = require_string(theme.get("evidence"), f"{label}.evidence")
    source_value = require_string(theme.get("source"), f"{label}.source")
    source_path = resolve_spec_relative(
        root, spec_dir, source_value, f"{label}.source", must_exist=True
    )
    source_asset_ids = validate_asset_ids(theme.get("source_asset_ids", []), f"{label}.source_asset_ids")
    z = require_int(theme.get("z"), f"{label}.z")
    opacity = require_number(theme.get("opacity", 1), f"{label}.opacity", minimum=0, maximum=1)
    blend = require_string(theme.get("blend", "normal"), f"{label}.blend")
    if blend not in BLEND_MODES:
        raise ValueError(f"{label}.blend must be one of: {', '.join(sorted(BLEND_MODES))}")
    transform = theme.get("transform")
    if not isinstance(transform, dict):
        raise ValueError(f"{label}.transform must be an object")
    boundary = theme.get("boundary")
    if not isinstance(boundary, dict):
        raise ValueError(f"{label}.boundary must be an object")
    finish = theme.get("finish", {})
    margin = boundary_margin(boundary, finish, label)

    source = validate_source(source_path, f"{label}.source")
    transformed, x, y = transform_source(source, transform, label)
    local = Image.new(
        "RGBA", (transformed.width + 2 * margin, transformed.height + 2 * margin), (0, 0, 0, 0)
    )
    local.alpha_composite(transformed, (margin, margin))
    base_alpha = local.getchannel("A")

    primary_type, primary = parse_effect(boundary["primary"], f"{label}.boundary.primary", allowed=BOUNDARY_TYPES)
    selected: list[tuple[str, dict[str, Any]]] = [(primary_type, primary)]
    if boundary.get("support") is not None:
        support_type, support = parse_effect(
            boundary["support"], f"{label}.boundary.support", allowed=BOUNDARY_TYPES
        )
        selected.append((support_type, support))

    effect_components: list[tuple[str, Image.Image, str, int]] = []
    processed_base = local.copy()
    for effect_type, config in selected:
        if effect_type == "feather":
            radius = require_number(config.get("radius"), f"{label}.feather.radius", minimum=0.1, maximum=20)
            blurred = base_alpha.filter(ImageFilter.GaussianBlur(radius))
            feathered = ImageChops.multiply(base_alpha, blurred)
            processed_base.putalpha(feathered)
            mask_layer = Image.new("RGBA", local.size, (255, 255, 255, 0))
            mask_layer.putalpha(feathered)
            effect_components.append(("feather-mask", mask_layer, "normal", 1))
            base_alpha = feathered
        elif effect_type == "outline":
            width = require_int(config.get("width"), f"{label}.outline.width", minimum=1)
            color = parse_color(config.get("color"), f"{label}.outline.color")
            effect_opacity = require_number(config.get("opacity", 1), f"{label}.outline.opacity", minimum=0, maximum=1)
            expanded = base_alpha.filter(ImageFilter.MaxFilter(width * 2 + 1))
            mask = ImageChops.subtract(expanded, base_alpha)
            effect_components.append(("outline", color_layer(mask, color, effect_opacity), "normal", 1))
        elif effect_type == "shadow":
            offset = config["offset"]
            dx, dy = int(offset[0]), int(offset[1])
            blur = require_number(config.get("blur"), f"{label}.shadow.blur", minimum=0, maximum=30)
            color = parse_color(config.get("color"), f"{label}.shadow.color")
            effect_opacity = require_number(config.get("opacity", 1), f"{label}.shadow.opacity", minimum=0, maximum=1)
            mask = base_alpha.filter(ImageFilter.GaussianBlur(blur)) if blur else base_alpha
            mask = shift_channel(mask, dx, dy)
            effect_components.append(("shadow", color_layer(mask, color, effect_opacity), "multiply", 0))
        elif effect_type == "relief":
            depth = require_int(config.get("depth"), f"{label}.relief.depth", minimum=1)
            effect_opacity = require_number(config.get("opacity", 0.2), f"{label}.relief.opacity", minimum=0, maximum=1)
            effect_components.append(("relief", build_relief(base_alpha, depth, effect_opacity), "normal", 3))

    if "relief" in finish:
        config = finish["relief"]
        depth = require_int(config.get("depth"), f"{label}.finish.relief.depth", minimum=1)
        effect_opacity = require_number(config.get("opacity", 0.15), f"{label}.finish.relief.opacity", minimum=0, maximum=0.35)
        effect_components.append(("finish-relief", build_relief(base_alpha, depth, effect_opacity), "normal", 3))
    if "rim" in finish:
        config = finish["rim"]
        width = require_int(config.get("width"), f"{label}.finish.rim.width", minimum=1)
        color = parse_color(config.get("color"), f"{label}.finish.rim.color")
        effect_opacity = require_number(config.get("opacity", 0.12), f"{label}.finish.rim.opacity", minimum=0, maximum=0.3)
        expanded = base_alpha.filter(ImageFilter.MaxFilter(width * 2 + 1))
        mask = ImageChops.subtract(expanded, base_alpha)
        effect_components.append(("finish-rim", color_layer(mask, color, effect_opacity), "screen", 4))

    all_local_images = [processed_base, *(entry[1] for entry in effect_components)]
    combined_alpha = Image.new("L", local.size, 0)
    for local_image in all_local_images:
        combined_alpha = ImageChops.lighter(combined_alpha, local_image.getchannel("A"))
    local_bbox = combined_alpha.getbbox()
    if local_bbox is None:
        raise ValueError(f"{label} contains no visible pixels after boundary processing")

    origin_x = x - margin
    origin_y = y - margin
    left = origin_x + local_bbox[0]
    top = origin_y + local_bbox[1]
    right = origin_x + local_bbox[2]
    bottom = origin_y + local_bbox[3]
    content_bottom = canvas_size[1] - safe_bottom
    if left < 0 or top < 0 or right > canvas_size[0] or bottom > content_bottom:
        raise ValueError(
            f"{label} rendered bounds {(left, top, right, bottom)} exceed content area "
            f"(0, 0, {canvas_size[0]}, {content_bottom})"
        )

    def place(local_image: Image.Image) -> Image.Image:
        canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        canvas.alpha_composite(multiply_alpha(local_image, opacity), (origin_x, origin_y))
        return canvas

    material_canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    material_canvas.alpha_composite(transformed, (x, y))

    components: list[Component] = []
    for sequence, (effect_name, effect_image, effect_blend, internal_order) in enumerate(
        effect_components, start=1
    ):
        components.append(
            Component(
                component_id=f"{theme_id}-{effect_name}",
                owner_id=theme_id,
                kind="structural-effect",
                role=effect_name,
                z=z,
                order=index * 100 + internal_order * 10 + sequence,
                blend=effect_blend,
                image=place(effect_image),
                filename=f"{z:04d}-{theme_id}-{effect_name}.png",
            )
        )
    components.append(
        Component(
            component_id=theme_id,
            owner_id=theme_id,
            kind="theme",
            role=role,
            z=z,
            order=index * 100 + 25,
            blend=blend,
            image=place(processed_base),
        )
    )

    map_layer = Image.new("L", canvas_size, 0)
    map_layer.paste(base_alpha, (origin_x, origin_y))
    report = {
        "id": theme_id,
        "name": name,
        "role": role,
        "evidence": evidence,
        "source": relative_path(source_path, root),
        "source_asset_ids": source_asset_ids,
        "z": z,
        "blend": blend,
        "rendered_bbox": [left, top, right, bottom],
        "boundary": boundary,
        "finish": finish,
    }
    return components, report, map_layer, material_canvas


def render_narrative_effect(
    effect: dict[str, Any],
    root: Path,
    spec_dir: Path,
    canvas_size: tuple[int, int],
    safe_bottom: int,
    index: int,
) -> tuple[Component, dict[str, Any], Image.Image]:
    label = f"effects[{index}]"
    effect_id = require_string(effect.get("id"), f"{label}.id")
    if not ID_RE.fullmatch(effect_id):
        raise ValueError(f"{label}.id must use lowercase ASCII letters, digits, and hyphens")
    name = require_string(effect.get("name"), f"{label}.name")
    kind = require_string(effect.get("kind"), f"{label}.kind")
    if kind not in EFFECT_KINDS:
        raise ValueError(f"{label}.kind must be narrative")
    source_value = require_string(effect.get("source"), f"{label}.source")
    source_path = resolve_spec_relative(
        root, spec_dir, source_value, f"{label}.source", must_exist=True
    )
    source_asset_ids = validate_asset_ids(effect.get("source_asset_ids", []), f"{label}.source_asset_ids")
    z = require_int(effect.get("z"), f"{label}.z")
    opacity = require_number(effect.get("opacity", 1), f"{label}.opacity", minimum=0, maximum=1)
    blend = require_string(effect.get("blend", "screen"), f"{label}.blend")
    if blend not in BLEND_MODES:
        raise ValueError(f"{label}.blend must be one of: {', '.join(sorted(BLEND_MODES))}")
    transform = effect.get("transform")
    if not isinstance(transform, dict):
        raise ValueError(f"{label}.transform must be an object")
    source = validate_source(source_path, f"{label}.source")
    transformed, x, y = transform_source(source, transform, label)
    bbox = transformed.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError(f"{label} contains no visible pixels after transform")
    rendered_bbox = [x + bbox[0], y + bbox[1], x + bbox[2], y + bbox[3]]
    content_bottom = canvas_size[1] - safe_bottom
    if (
        rendered_bbox[0] < 0
        or rendered_bbox[1] < 0
        or rendered_bbox[2] > canvas_size[0]
        or rendered_bbox[3] > content_bottom
    ):
        raise ValueError(
            f"{label} rendered bounds {tuple(rendered_bbox)} exceed content area "
            f"(0, 0, {canvas_size[0]}, {content_bottom})"
        )
    material_canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    material_canvas.alpha_composite(transformed, (x, y))
    canvas = multiply_alpha(material_canvas, opacity)
    component = Component(
        component_id=effect_id,
        owner_id=effect_id,
        kind="narrative-effect",
        role=kind,
        z=z,
        order=10000 + index,
        blend=blend,
        image=canvas,
    )
    report = {
        "id": effect_id,
        "name": name,
        "kind": kind,
        "source": relative_path(source_path, root),
        "source_asset_ids": source_asset_ids,
        "z": z,
        "blend": blend,
        "rendered_bbox": rendered_bbox,
    }
    return component, report, material_canvas


def count_key_colors(image: Image.Image) -> tuple[int, int]:
    pixels = image.load()
    green = 0
    magenta = 0
    for y in range(image.height):
        for x in range(image.width):
            red, value_green, blue, alpha = pixels[x, y]
            if alpha <= 4:
                continue
            if value_green > 200 and red < 24 and blue < 24:
                green += 1
            if red > 200 and blue > 200 and value_green < 24:
                magenta += 1
    return green, magenta


def count_key_green(image: Image.Image) -> int:
    return count_key_colors(image)[0]


def build_layer_map(masks: list[tuple[str, Image.Image]], canvas_size: tuple[int, int]) -> Image.Image:
    palette = [
        (255, 70, 86),
        (54, 210, 230),
        (255, 196, 76),
        (174, 102, 255),
    ]
    output = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    for position, (_, mask) in enumerate(masks):
        color = palette[position % len(palette)]
        layer = Image.new("RGBA", canvas_size, (*color, 0))
        layer.putalpha(mask.point(lambda value: round(value * 0.72)))
        output.alpha_composite(layer)
    return output


def checker_preview(image: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    background = Image.new("RGBA", image.size, (*color, 255))
    background.alpha_composite(image)
    return background.convert("RGB")


def light_dark_preview(image: Image.Image) -> Image.Image:
    light = checker_preview(image, (238, 238, 238))
    dark = checker_preview(image, (22, 24, 28))
    preview = Image.new("RGB", (image.width * 2, image.height), (24, 24, 24))
    preview.paste(light, (0, 0))
    preview.paste(dark, (image.width, 0))
    return preview


def contact_sheet(light: Image.Image, dark: Image.Image, layer_map: Image.Image) -> Image.Image:
    width, height = light.size
    sheet = Image.new("RGB", (width * 3, height), (24, 24, 24))
    sheet.paste(light, (0, 0))
    sheet.paste(dark, (width, 0))
    map_preview = checker_preview(layer_map, (32, 34, 38))
    sheet.paste(map_preview, (width * 2, 0))
    return sheet


def choose_output_pair(output: Path, report: Path, overwrite: bool) -> tuple[Path, Path]:
    if overwrite or (not output.exists() and not report.exists()):
        return output, report
    version = 2
    while True:
        output_candidate = output.with_name(f"{output.stem}-v{version}{output.suffix}")
        report_suffixes = "".join(report.suffixes)
        report_base = report.name[: -len(report_suffixes)] if report_suffixes else report.name
        report_candidate = report.with_name(f"{report_base}-v{version}{report_suffixes}")
        if not output_candidate.exists() and not report_candidate.exists():
            return output_candidate, report_candidate
        version += 1


def choose_component_path(path: Path, overwrite: bool) -> Path:
    if overwrite or not path.exists():
        return path
    version = 2
    while True:
        candidate = path.with_name(f"{path.stem}-v{version}{path.suffix}")
        if not candidate.exists():
            return candidate
        version += 1


def matches_qa_output_name(filename: str, logical_name: str) -> bool:
    if filename == f"{logical_name}.png":
        return True
    prefix = f"{logical_name}-v"
    if not filename.startswith(prefix) or not filename.endswith(".png"):
        return False
    version_text = filename[len(prefix) : -len(".png")]
    return (
        version_text.isascii()
        and version_text.isdigit()
        and not version_text.startswith("0")
        and int(version_text) >= 2
    )


def legacy_root_qa_names(
    root: Path,
    qa_dir: Path,
    report_path: Path,
    current_names: set[str],
) -> set[str]:
    names = {
        name for name in current_names if QA_LOGICAL_NAME_RE.fullmatch(name)
    }
    if not report_path.is_file():
        return names
    try:
        previous_report = load_json(report_path, "existing layer report")
    except (OSError, ValueError):
        return names
    previous_qa = previous_report.get("qa")
    if not isinstance(previous_qa, dict):
        return names
    for logical_name, path_value in previous_qa.items():
        if (
            not isinstance(logical_name, str)
            or not QA_LOGICAL_NAME_RE.fullmatch(logical_name)
            or not isinstance(path_value, str)
        ):
            continue
        try:
            previous_path = resolve_inside(
                root, Path(path_value), "existing QA preview"
            )
        except (OSError, ValueError):
            continue
        if previous_path.parent == qa_dir and matches_qa_output_name(
            previous_path.name, logical_name
        ):
            names.add(logical_name)
    return names


def cleanup_legacy_qa_root(
    root: Path,
    qa_dir: Path,
    report_path: Path,
    current_names: set[str],
) -> None:
    if not qa_dir.is_dir():
        return
    logical_names = legacy_root_qa_names(
        root, qa_dir, report_path, current_names
    )
    for candidate in qa_dir.iterdir():
        if not (candidate.is_file() or candidate.is_symlink()):
            continue
        if any(
            matches_qa_output_name(candidate.name, logical_name)
            for logical_name in logical_names
        ):
            candidate.unlink()


def validate_resolved_brief(brief: dict[str, Any], spec: dict[str, Any]) -> None:
    version = require_int(brief.get("schema_version"), "brief.schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"brief.schema_version must be {SCHEMA_VERSION}")

    input_mode = require_string(brief.get("input_mode"), "brief.input_mode")
    if input_mode not in BRIEF_INPUT_MODES:
        raise ValueError(
            "brief.input_mode must be one of: "
            + ", ".join(sorted(BRIEF_INPUT_MODES))
        )
    for field in ("style", "icon_type", "profile"):
        value = require_string(brief.get(field), f"brief.{field}")
        if value != spec.get(field):
            raise ValueError(f"brief.{field} must match composition.{field}")

    input_basis = brief.get("input_basis")
    if not isinstance(input_basis, dict):
        raise ValueError("brief.input_basis must be an object")
    required_basis = {"focus_name", "focus_description"}
    missing_basis = sorted(required_basis - input_basis.keys())
    extra_basis = sorted(input_basis.keys() - required_basis)
    if missing_basis:
        raise ValueError(
            "brief.input_basis is missing: " + ", ".join(missing_basis)
        )
    if extra_basis:
        raise ValueError(
            "brief.input_basis has unknown entries: " + ", ".join(extra_basis)
        )
    for field in ("focus_name", "focus_description"):
        if field not in brief:
            raise ValueError(f"brief is missing required field: {field}")
        value = brief[field]
        if value is not None:
            require_string(value, f"brief.{field}")
        status = require_string(input_basis[field], f"brief.input_basis.{field}")
        if status not in INPUT_BASIS_VALUES:
            raise ValueError(
                f"brief.input_basis.{field} must be one of: "
                + ", ".join(sorted(INPUT_BASIS_VALUES))
            )
        if value is None and status != "missing":
            raise ValueError(
                f"brief.input_basis.{field} must be 'missing' when brief.{field} is null"
            )
        if value is not None and status == "missing":
            raise ValueError(
                f"brief.input_basis.{field} cannot be 'missing' when brief.{field} is present"
            )

    themes = brief.get("themes")
    if not isinstance(themes, list):
        raise ValueError("brief.themes must be an array")
    if not 2 <= len(themes) <= 4:
        raise ValueError("brief.themes must contain two to four semantic themes")
    seen_theme_ids: set[str] = set()
    for position, raw_theme in enumerate(themes, start=1):
        label = f"brief.themes[{position}]"
        if not isinstance(raw_theme, dict):
            raise ValueError(f"{label} must be an object")
        theme_id = require_string(raw_theme.get("id"), f"{label}.id")
        if not ID_RE.fullmatch(theme_id):
            raise ValueError(
                f"{label}.id must use lowercase ASCII letters, digits, and hyphens"
            )
        if theme_id in seen_theme_ids:
            raise ValueError(f"brief contains duplicate theme ID: {theme_id}")
        seen_theme_ids.add(theme_id)
        require_string(raw_theme.get("name"), f"{label}.name")
        role = require_string(raw_theme.get("role"), f"{label}.role")
        if role not in THEME_ROLES:
            raise ValueError(
                f"{label}.role must be one of: "
                + ", ".join(sorted(THEME_ROLES))
            )
        for field in ("evidence", "subject", "placement", "palette", "prompt"):
            require_string(raw_theme.get(field), f"{label}.{field}")
        require_string_array(raw_theme.get("motifs"), f"{label}.motifs", minimum=1)

    effects = brief.get("effects")
    if not isinstance(effects, list):
        raise ValueError("brief.effects must be an array")
    seen_effect_ids: set[str] = set()
    for position, raw_effect in enumerate(effects, start=1):
        label = f"brief.effects[{position}]"
        if not isinstance(raw_effect, dict):
            raise ValueError(f"{label} must be an object")
        effect_id = require_string(raw_effect.get("id"), f"{label}.id")
        if not ID_RE.fullmatch(effect_id):
            raise ValueError(
                f"{label}.id must use lowercase ASCII letters, digits, and hyphens"
            )
        if effect_id in seen_effect_ids:
            raise ValueError(f"brief contains duplicate effect ID: {effect_id}")
        seen_effect_ids.add(effect_id)
        require_string(raw_effect.get("name"), f"{label}.name")
        kind = require_string(raw_effect.get("kind"), f"{label}.kind")
        if kind not in EFFECT_KINDS:
            raise ValueError(f"{label}.kind must be narrative")
        for field in ("evidence", "subject", "placement", "palette", "prompt"):
            require_string(raw_effect.get(field), f"{label}.{field}")

    require_string_array(brief.get("constraints"), "brief.constraints")


def validate_spec_header(
    spec: dict[str, Any], root: Path, spec_dir: Path
) -> tuple[tuple[int, int], int, dict[str, Any] | None]:
    version = require_int(spec.get("schema_version"), "schema_version")
    if version != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    style = require_string(spec.get("style"), "style")
    icon_type = require_string(spec.get("icon_type"), "icon_type")
    require_string(spec.get("profile"), "profile")
    canvas = spec.get("canvas")
    if not isinstance(canvas, dict):
        raise ValueError("canvas must be an object")
    width = require_int(canvas.get("width"), "canvas.width", minimum=1)
    height = require_int(canvas.get("height"), "canvas.height", minimum=1)
    safe_bottom = require_int(canvas.get("safe_bottom", 0), "canvas.safe_bottom", minimum=0)
    if safe_bottom >= height:
        raise ValueError("canvas.safe_bottom must be smaller than canvas.height")
    if style == "tfr" and icon_type == "focus" and spec.get("profile") == "focus-tfr":
        if (width, height, safe_bottom) != (180, 150, 40):
            raise ValueError("focus-tfr canvas must be 180x150 with safe_bottom 40")
    brief_payload: dict[str, Any] | None = None
    if "brief" in spec:
        brief_path = resolve_spec_relative(
            root, spec_dir, require_string(spec["brief"], "brief"), "brief", must_exist=True
        )
        brief_payload = load_json(brief_path, "brief")
        validate_resolved_brief(brief_payload, spec)
    elif style == "tfr" and icon_type == "focus":
        raise ValueError("a layered TFR focus composition requires a brief file")
    return (width, height), safe_bottom, brief_payload


def validate_brief_alignment(
    themes: list[Any], effects: list[Any], brief: dict[str, Any] | None
) -> None:
    if brief is None:
        return
    brief_themes = brief.get("themes")
    if not isinstance(brief_themes, list):
        raise ValueError("brief field 'themes' must be an array")
    theme_contracts: dict[str, dict[str, Any]] = {}
    for position, raw_theme in enumerate(brief_themes, start=1):
        if not isinstance(raw_theme, dict):
            raise ValueError(f"brief themes[{position}] must be an object")
        theme_id = require_string(raw_theme.get("id"), f"brief themes[{position}].id")
        evidence = require_string(
            raw_theme.get("evidence"), f"brief themes[{position}].evidence"
        )
        if theme_id in theme_contracts:
            raise ValueError(f"brief contains duplicate theme ID: {theme_id}")
        theme_contracts[theme_id] = raw_theme

    composition_theme_ids: list[str] = []
    for position, raw_theme in enumerate(themes, start=1):
        if not isinstance(raw_theme, dict):
            continue
        theme_id = require_string(raw_theme.get("id"), f"themes[{position}].id")
        composition_theme_ids.append(theme_id)
        evidence = require_string(raw_theme.get("evidence"), f"themes[{position}].evidence")
        if theme_id not in theme_contracts:
            raise ValueError(f"themes[{position}] is not grounded in brief.json: {theme_id}")
        brief_theme = theme_contracts[theme_id]
        for field in ("name", "role", "evidence"):
            composition_value = require_string(
                raw_theme.get(field), f"themes[{position}].{field}"
            )
            if composition_value != brief_theme[field]:
                raise ValueError(
                    f"themes[{position}] {field} does not match brief.json"
                )
    missing_theme_ids = sorted(set(theme_contracts) - set(composition_theme_ids))
    if missing_theme_ids:
        raise ValueError(
            "composition is missing themes declared in brief.json: "
            + ", ".join(missing_theme_ids)
        )

    brief_effects = brief.get("effects", [])
    if not isinstance(brief_effects, list):
        raise ValueError("brief field 'effects' must be an array")
    effect_contracts: dict[str, dict[str, Any]] = {}
    for position, raw_effect in enumerate(brief_effects, start=1):
        if not isinstance(raw_effect, dict):
            raise ValueError(f"brief effects[{position}] must be an object")
        effect_id = require_string(raw_effect.get("id"), f"brief effects[{position}].id")
        evidence = require_string(
            raw_effect.get("evidence"), f"brief effects[{position}].evidence"
        )
        if effect_id in effect_contracts:
            raise ValueError(f"brief contains duplicate effect ID: {effect_id}")
        effect_contracts[effect_id] = raw_effect
    composition_effect_ids: list[str] = []
    for position, raw_effect in enumerate(effects, start=1):
        if not isinstance(raw_effect, dict):
            continue
        effect_id = require_string(raw_effect.get("id"), f"effects[{position}].id")
        composition_effect_ids.append(effect_id)
        if effect_id not in effect_contracts:
            raise ValueError(f"effects[{position}] is not grounded in brief.json: {effect_id}")
        brief_effect = effect_contracts[effect_id]
        for field in ("name", "kind"):
            composition_value = require_string(
                raw_effect.get(field), f"effects[{position}].{field}"
            )
            if composition_value != brief_effect[field]:
                raise ValueError(
                    f"effects[{position}] {field} does not match brief.json"
                )
    missing_effect_ids = sorted(set(effect_contracts) - set(composition_effect_ids))
    if missing_effect_ids:
        raise ValueError(
            "composition is missing effects declared in brief.json: "
            + ", ".join(missing_effect_ids)
        )


def render_spec(spec_path: Path, root: Path) -> tuple[Image.Image, dict[str, Any], list[Component], dict[str, Image.Image]]:
    spec = load_json(spec_path, "composition spec")
    spec_dir = spec_path.parent
    canvas_size, safe_bottom, brief_payload = validate_spec_header(spec, root, spec_dir)
    themes = spec.get("themes")
    if not isinstance(themes, list):
        raise ValueError("themes must be an array")
    style = spec["style"]
    icon_type = spec["icon_type"]
    if style == "tfr" and icon_type == "focus" and not 2 <= len(themes) <= 4:
        raise ValueError("a layered TFR focus requires two to four semantic themes")
    if not themes:
        raise ValueError("at least one theme is required")

    effects = spec.get("effects", [])
    if not isinstance(effects, list):
        raise ValueError("effects must be an array")
    validate_brief_alignment(themes, effects, brief_payload)

    components: list[Component] = []
    theme_reports: list[dict[str, Any]] = []
    map_masks: list[tuple[str, Image.Image]] = []
    material_previews: dict[str, Image.Image] = {}
    seen_ids: set[str] = set()
    for position, raw_theme in enumerate(themes, start=1):
        if not isinstance(raw_theme, dict):
            raise ValueError(f"themes[{position}] must be an object")
        theme_components, theme_report, map_mask, material_canvas = render_theme(
            raw_theme, root, spec_dir, canvas_size, safe_bottom, position
        )
        if theme_report["id"] in seen_ids:
            raise ValueError(f"duplicate layer ID: {theme_report['id']}")
        seen_ids.add(theme_report["id"])
        components.extend(theme_components)
        theme_reports.append(theme_report)
        map_masks.append((theme_report["id"], map_mask))
        material_previews[f"material-theme-{theme_report['id']}"] = (
            light_dark_preview(material_canvas)
        )

    effect_reports: list[dict[str, Any]] = []
    for position, raw_effect in enumerate(effects, start=1):
        if not isinstance(raw_effect, dict):
            raise ValueError(f"effects[{position}] must be an object")
        component, effect_report, material_canvas = render_narrative_effect(
            raw_effect, root, spec_dir, canvas_size, safe_bottom, position
        )
        if effect_report["id"] in seen_ids:
            raise ValueError(f"duplicate layer ID: {effect_report['id']}")
        seen_ids.add(effect_report["id"])
        components.append(component)
        effect_reports.append(effect_report)
        material_previews[f"material-effect-{effect_report['id']}"] = (
            light_dark_preview(material_canvas)
        )

    composite = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    for component in sorted(components, key=lambda item: (item.z, item.order)):
        if component.kind == "structural-effect" and component.role == "feather-mask":
            continue
        composite = blend_onto(composite, component.image, component.blend)

    alpha = composite.getchannel("A")
    safe_bottom_alpha_max = 0
    if safe_bottom:
        safe_bottom_alpha_max = max(
            alpha.crop((0, canvas_size[1] - safe_bottom, canvas_size[0], canvas_size[1])).getextrema()
        )
    key_green_pixels, key_magenta_pixels = count_key_colors(composite)
    errors: list[str] = []
    if alpha.getbbox() is None:
        errors.append("composite contains no visible pixels")
    safe_bottom_limit = (
        0
        if style == "tfr"
        and icon_type == "focus"
        and spec.get("profile") == "focus-tfr"
        else 4
    )
    if safe_bottom_alpha_max > safe_bottom_limit:
        errors.append("composite has visible pixels in the title-safe area")
    if key_green_pixels:
        errors.append(f"composite contains {key_green_pixels} visible chroma-key-green pixels")
    if key_magenta_pixels:
        errors.append(
            f"composite contains {key_magenta_pixels} visible chroma-key-magenta pixels"
        )
    if errors:
        raise ValueError("; ".join(errors))

    layer_map = build_layer_map(map_masks, canvas_size)
    light = checker_preview(composite, (238, 238, 238))
    dark = checker_preview(composite, (22, 24, 28))
    qa_images = {
        "layer-map": layer_map,
        "light": light,
        "dark": dark,
        "contact-sheet": contact_sheet(light, dark, layer_map),
        **material_previews,
    }
    for theme_report in theme_reports:
        isolated = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        for component in sorted(
            (item for item in components if item.owner_id == theme_report["id"]),
            key=lambda item: (item.z, item.order),
        ):
            if component.kind == "structural-effect" and component.role == "feather-mask":
                continue
            isolated = blend_onto(isolated, component.image, component.blend)
        qa_images[f"theme-{theme_report['id']}"] = checker_preview(
            isolated, (22, 24, 28)
        )
    report = {
        "schema_version": SCHEMA_VERSION,
        "spec": relative_path(spec_path, root),
        "canvas": {
            "width": canvas_size[0],
            "height": canvas_size[1],
            "safe_bottom": safe_bottom,
        },
        "themes": theme_reports,
        "effects": effect_reports,
        "layers": [],
        "qa": {},
        "validation": {
            "ok": True,
            "theme_count": len(theme_reports),
            "narrative_effect_count": len(effect_reports),
            "structural_effect_count": sum(
                1 for component in components if component.kind == "structural-effect"
            ),
            "safe_bottom_alpha_max": safe_bottom_alpha_max,
            "key_green_pixels": key_green_pixels,
            "key_magenta_pixels": key_magenta_pixels,
            "errors": [],
            "warnings": [],
        },
    }
    return composite, report, components, qa_images


def write_outputs(
    composite: Image.Image,
    report: dict[str, Any],
    components: list[Component],
    qa_images: dict[str, Image.Image],
    root: Path,
    output: Path,
    report_path: Path,
    effects_dir: Path,
    qa_dir: Path,
    overwrite: bool,
) -> tuple[Path, Path]:
    if overwrite:
        cleanup_legacy_qa_root(
            root, qa_dir, report_path, set(qa_images)
        )

    output, report_path = choose_output_pair(output, report_path, overwrite)
    effect_paths: dict[str, Path] = {}
    for component in components:
        if component.filename:
            path = choose_component_path(effects_dir / component.filename, overwrite)
            effect_paths[component.component_id] = path
    qa_paths = {}
    for name in qa_images:
        group = "materials" if name.startswith("material-") else "final"
        qa_paths[name] = choose_component_path(
            qa_dir / group / f"{name}.png", overwrite
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    effects_dir.mkdir(parents=True, exist_ok=True)
    qa_dir.mkdir(parents=True, exist_ok=True)
    for path in qa_paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    composite.save(output, format="PNG", optimize=True)

    layer_records: list[dict[str, Any]] = []
    theme_sources = {entry["id"]: entry["source"] for entry in report["themes"]}
    narrative_sources = {entry["id"]: entry["source"] for entry in report["effects"]}
    for component in sorted(components, key=lambda item: (item.z, item.order)):
        path_value: str | None = None
        if component.filename:
            component_path = effect_paths[component.component_id]
            component.image.save(component_path, format="PNG", optimize=True)
            path_value = relative_path(component_path, root)
        elif component.kind == "theme":
            path_value = theme_sources[component.owner_id]
        elif component.kind == "narrative-effect":
            path_value = narrative_sources[component.owner_id]
        layer_records.append(
            {
                "id": component.component_id,
                "owner_id": component.owner_id,
                "kind": component.kind,
                "role": component.role,
                "z": component.z,
                "blend": component.blend,
                "path": path_value,
            }
        )

    for name, image in qa_images.items():
        image.save(qa_paths[name], format="PNG", optimize=True)

    report["output"] = relative_path(output, root)
    report["layers"] = layer_records
    report["qa"] = {name: relative_path(path, root) for name, path in qa_paths.items()}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output, report_path


def command_validate(args: argparse.Namespace) -> int:
    root = Path(args.manifest_root).resolve()
    if not root.is_dir():
        raise ValueError("--manifest-root must be an existing directory")
    spec_path = resolve_inside(root, Path(args.spec), "composition spec", must_exist=True)
    _, report, _, _ = render_spec(spec_path, root)
    print(json.dumps({"ok": True, "validation": report["validation"]}, ensure_ascii=False, indent=2))
    return 0


def command_compose(args: argparse.Namespace) -> int:
    root = Path(args.manifest_root).resolve()
    if not root.is_dir():
        raise ValueError("--manifest-root must be an existing directory")
    spec_path = resolve_inside(root, Path(args.spec), "composition spec", must_exist=True)
    output = resolve_inside(root, Path(args.output), "output")
    report_path = resolve_inside(root, Path(args.report), "report")
    effects_dir = resolve_inside(root, Path(args.effects_dir), "effects directory")
    qa_dir = resolve_inside(root, Path(args.qa_dir), "QA directory")
    composite, report, components, qa_images = render_spec(spec_path, root)
    output, report_path = write_outputs(
        composite,
        report,
        components,
        qa_images,
        root,
        output,
        report_path,
        effects_dir,
        qa_dir,
        args.overwrite,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "output": str(output),
                "report": str(report_path),
                "validation": report["validation"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a composition and all layer sources")
    validate.add_argument("--spec", required=True)
    validate.add_argument("--manifest-root", required=True)
    validate.set_defaults(handler=command_validate)

    compose = subparsers.add_parser("compose", help="Render a validated layered composition")
    compose.add_argument("--spec", required=True)
    compose.add_argument("--manifest-root", required=True)
    compose.add_argument("--output", required=True)
    compose.add_argument("--effects-dir", required=True)
    compose.add_argument("--qa-dir", required=True)
    compose.add_argument("--report", required=True)
    compose.add_argument("--overwrite", action="store_true")
    compose.set_defaults(handler=command_compose)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
