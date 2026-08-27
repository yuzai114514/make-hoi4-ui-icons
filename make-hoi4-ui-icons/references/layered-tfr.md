# Layered TFR focus workflow

Use this workflow only for `style=tfr` and `icon_type=focus`. It produces a
PSD-like package of transparent PNG layers and deterministic composition data;
it does not write a PSD file.

## Derive the brief

For human input, extract a focus name and description from ordinary prose when
they are present. The name supplies the core metaphor and mood; the description
supplies events, actors, objects, causal relationships, and setting. When only
one is present, use the available text conservatively instead of inventing the
missing field.

For AI input, preserve the existing schema. Accept these optional additions:

```yaml
focus_name: "..."
focus_description: "..."
themes: # optional strict override; otherwise derive 2-4 themes
  - id: "ascii-safe-id"
    name: "..."
    role: primary | secondary | background | context
    evidence: "exact phrase or concise paraphrase grounded in the input"
    subject: "..."
    motifs: ["..."]
    placement: "..."
    palette: "..."
    prompt: "one-layer generation prompt"
```

Legacy AI briefs without the new fields remain valid. Derive themes only from
their existing `subject`, `symbols`, and `composition` fields and record that
the name or description was unavailable. When `themes` is supplied, preserve
every explicit theme field and reject invalid counts, duplicate IDs, empty
evidence, or ungrounded extra narrative objects.

Write the resolved request to `brief.json` using schema version 1. This is the
validated internal contract for both input modes, not a copy of the incoming AI
object:

```json
{
  "schema_version": 1,
  "input_mode": "human",
  "style": "tfr",
  "icon_type": "focus",
  "profile": "focus-tfr",
  "focus_name": "国策名，缺失时为 null",
  "focus_description": "国策描述，缺失时为 null",
  "input_basis": {
    "focus_name": "provided|derived|missing",
    "focus_description": "provided|derived|missing"
  },
  "themes": [
    {
      "id": "ascii-safe-id",
      "name": "主题名",
      "role": "primary|secondary|background|context",
      "evidence": "可追溯到输入的原文或简洁转述",
      "subject": "单层主体",
      "motifs": ["至少一个视觉母题"],
      "placement": "构图位置与层级",
      "palette": "该层配色",
      "prompt": "只生成这一层的提示词"
    }
  ],
  "effects": [
    {
      "id": "ascii-safe-id",
      "name": "特效名",
      "kind": "narrative",
      "evidence": "可追溯到输入的依据",
      "subject": "独立特效主体",
      "placement": "覆盖位置",
      "palette": "特效配色",
      "prompt": "只生成这一特效层的提示词"
    }
  ],
  "constraints": ["请求级约束"]
}
```

For a TFR focus, `themes` must contain two to four entries. Every theme needs a
unique ID and all fields above. Narrative effects such as radar sweeps, smoke,
explosions, scanlines, or lens flashes are not themes and do not satisfy the
two-theme minimum. `composition.json` must contain exactly the same theme and
effect IDs; theme names, roles, and evidence plus effect names and kinds must
match the resolved brief. If human input cannot support two grounded themes,
ask for the missing description. Reject an AI brief with a field-level error
instead of filling a required field silently.

## Prepare independent layers

Search the library once per theme instead of only once for the whole icon.
Keep authorization and provenance rules unchanged. Generate one independent
opaque cutout per missing theme and one independent cutout per narrative effect
that cannot be produced deterministically. Do not bake outlines, drop shadows,
feathering, relief, rim light, global color grading, text, or a frame into a
theme source. Use the normal chroma-key removal workflow and inspect each
transparent result before composition.

Use this task-local package layout:

```text
layers/themes/       independent transparent theme sources
layers/effects/      generated structural effects and narrative-effect sources
brief.json           semantic decomposition and per-layer prompts
composition.json     deterministic layout and effect instructions
composite-source.png composed target-size source
composite-source.layers.json  rendered layer report
qa/materials/        transformed source previews without structural effects
qa/final/            isolated finished layers, layer map, and light/dark previews
final.png             finalized icon
```

## Composition schema

`composition.json` uses schema version 1:

```json
{
  "schema_version": 1,
  "style": "tfr",
  "icon_type": "focus",
  "profile": "focus-tfr",
  "brief": "brief.json",
  "canvas": {"width": 180, "height": 150, "safe_bottom": 40},
  "themes": [
    {
      "id": "blockade-fleet",
      "name": "封锁舰队",
      "role": "primary",
      "evidence": "舰队与封锁",
      "source": "layers/themes/02-blockade-fleet.png",
      "source_asset_ids": [],
      "z": 20,
      "transform": {"x": 58, "y": 18, "width": 104, "height": 82, "rotation": 0},
      "opacity": 1.0,
      "blend": "normal",
      "boundary": {
        "primary": {"type": "outline", "width": 1, "color": "#d83447", "opacity": 0.55},
        "support": {"type": "shadow", "offset": [2, 2], "blur": 3, "color": "#16070b", "opacity": 0.65}
      },
      "finish": {
        "relief": {"depth": 1, "opacity": 0.18},
        "rim": {"width": 1, "color": "#ffd7d7", "opacity": 0.06}
      }
    }
  ],
  "effects": [
    {
      "id": "radar-approach",
      "name": "雷达逼近",
      "kind": "narrative",
      "source": "layers/effects/radar-approach.png",
      "source_asset_ids": [],
      "z": 30,
      "transform": {"x": 12, "y": 8, "width": 154, "height": 94, "rotation": 0},
      "opacity": 0.8,
      "blend": "screen"
    }
  ]
}
```

Paths stored inside `composition.json` are relative to that file's directory;
all resolved paths must remain under the manifest root. Theme source PNGs must
be non-empty RGBA images. `transform` coordinates describe the
top-left of the transformed source before structural-effect expansion.
Supported blend modes are `normal`, `screen`, and `multiply`.

## Assign boundaries

Every TFR theme requires one primary boundary technique and no more than one
supporting technique:

- Maps, buildings, and vehicles: outline plus a light directional shadow.
- People: feather plus directional shadow. Put very weak relief and a weak
  light-pollution rim under `finish`; these are material finishing, not extra
  boundary techniques.
- Photographs and terrain: feather plus directional shadow.
- Machinery, metal, and hard objects: relief plus a narrow outline or rim.
- Background and environment: feather or fade; never use a coarse outline.

The compositor exports feather masks, outlines, shadows, relief, and rim light
as separate transparent PNGs. Use one dominant separation cue; finishing must
stay subtle and may not obscure facial features or object silhouettes.
Judge outlines at the final 1:1 icon size, not on the large source cutout. For a
large vehicle or ship that already has a readable silhouette, start near 1px
and 0.45–0.65 opacity; use 2px only when the subject otherwise collapses into
the background. The outline must separate the subject, not become its main
visual motif.

## Compose and finalize

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/compose_layers.py" validate `
  --spec "<TASK>/composition.json" `
  --manifest-root "<WORKSPACE>"

& "<PYTHON>" "<SKILL_DIR>/scripts/compose_layers.py" compose `
  --spec "<TASK>/composition.json" `
  --manifest-root "<WORKSPACE>" `
  --output "<TASK>/composite-source.png" `
  --effects-dir "<TASK>/layers/effects" `
  --qa-dir "<TASK>/qa" `
  --report "<TASK>/composite-source.layers.json"
```

Finalize the exact composition with `--layout preserve-canvas` and pass
`--brief`, `--composition`, and `--layer-report` so the final manifest records
the layered package. The compositor and finalizer both reject visible pixels in
the configured title-safe area. For `focus-tfr`, every Alpha value in the bottom
40 pixels must be exactly zero; the normal visibility threshold does not apply,
and `--safe-bottom` cannot reduce this minimum. Validation also rejects visible
green `#00ff00` and magenta `#ff00ff` key-color residue before final output.

Visually inspect every theme alone, the layer map, and the final icon on light
and dark backgrounds at 1:1. Confirm that each theme remains recognizable when
other themes are hidden and that narrative effects do not provide the only
separation between semantic themes. Keep raw transformed-source previews under
`qa/materials/` and post-boundary/composite previews under `qa/final/`; do not
mix them in one preview gallery. When explicitly recomposing a pre-split
package with `--overwrite`, the compositor removes only reserved generated PNG
names from the `qa/` root before writing the two galleries. Without
`--overwrite`, prior files remain untouched and new outputs are versioned.
