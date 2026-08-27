# Prompt modes

Resolve every request into one internal brief. Keep the two input modes distinct.

## Human mode

Accept one natural-language request. Extract explicit facts, then complete omitted fields automatically. Do not require the user to fill a schema.

Resolve, in order:

1. `icon_type`
2. `style`
3. `focus_name` and `focus_description` when present
4. `subject` and intended meaning
5. `symbols`
6. `composition`
7. `palette` and `mood`
8. `reuse`
9. `target_profile`
10. `output_name` and requested deliverables

Give explicit user wording priority over inference. Use `vanilla` only when no style is stated or implied. Use the nearest target-project icon type when context identifies one; otherwise use `focus` and disclose that resolution in the brief. Set `reuse = prefer` unless the user requires or forbids reuse. Resolve the technical profile by the priority in `icon-types.md`.

For `style=tfr` and `icon_type=focus`, read [layered-tfr.md](layered-tfr.md).
Treat the focus name as metaphor and mood evidence and the description as event,
object, causal, and setting evidence. Write a task-local `brief.json` with two
to four grounded themes. If either the name or description is missing, use the
available input conservatively and record the missing field as `null` with an
`input_basis` value of `missing`. Ask only when the available sentence cannot
support two grounded semantic themes.

Ask only when a contradiction prevents a valid deliverable. Otherwise choose the smallest coherent interpretation and proceed.

## AI mode

Accept a strict structured object from another AI or pipeline. Require every
legacy field below; `focus_name` and `focus_description` are the only optional
fields shown in the base schema. Reject unknown enums, empty required strings,
and unresolved placeholders instead of inferring them silently.

```yaml
mode: ai
icon_type: focus | idea | technology | other-ui
style: vanilla | tfr | tno | red-flood
focus_name: "optional; accepted for layered TFR focus requests"
focus_description: "optional; accepted for layered TFR focus requests"
subject: "..."
symbols: ["..."]
composition: "..."
palette: "..."
mood: "..."
reuse: prefer | require | forbid
target_profile:
  source: project | library_reference | bundled_fallback
  reference: "relative/inspected asset path, or focus|focus-tfr|idea|technology for bundled_fallback"
output:
  basename: "ascii_safe_name"
  png: true
  gfx: true | false
gfx_target: # required only when output.gfx is true
  mod_root: "confirmed target mod root"
  sprite_name: "GFX_unique_name"
  texture_path: "gfx/interface/.../icon.png"
  definition_path: "interface/mod_prefix_icons.gfx"
```

Layered TFR AI input may also provide a strict `themes` array using the schema
in [layered-tfr.md](layered-tfr.md). These three additions are optional so
existing AI briefs remain valid. When both `focus_name` and
`focus_description` are absent, derive themes only from the existing `subject`,
`symbols`, and `composition` fields. When `themes` is present, preserve it and
reject invalid or ungrounded entries instead of silently rewriting them.
Always normalize a valid incoming AI object into the complete resolved
`brief.json` contract in `layered-tfr.md`; incoming optional fields do not make
resolved brief fields optional.

Preserve all valid AI fields verbatim. Apply only technical constraints required by the resolved profile, transparency, HOI4 paths, and PNG/GFX wiring. Return a field-level error when the object is incomplete.

Use `bundled_fallback` only when no target-project or library profile is available. Enforce these cross-field mappings: `idea -> idea`, `technology -> technology`, and `focus -> focus` except that `style=tfr` uses `focus-tfr`. Reject a mismatched profile with a field-level error. `other-ui` still requires target-project or verified library evidence.

When `output.gfx` is `true`, require all four `gfx_target` fields and confirm that `mod_root` is the active target before writing. When it is `false`, omit `gfx_target`. Never infer a sprite name or mod destination in strict AI mode.

## Shared output contract

Record the resolved brief, reused source paths, authorization state, selected technical profile, final PNG path, and optional GFX snippet. Never hide inferred values.

Evidence paths relative to the library root:

- `秋起美术馆/TFR/TFR官方教程及素材合集/TFR 图标教程 Icon Guide CN.docx`
- `秋起美术馆/TNO/文档类/译文_如何制作tno风格图标（注：可能过时）.docx`
- `秋起美术馆/赤潮/图标 Icons/赤潮风图标教程 RF Icon Guide CN.docx`
