---
name: make-hoi4-ui-icons
description: Retrieve, reuse, generate, layer, finalize, and optionally register Hearts of Iron IV UI icons from a local material library. Use when Codex needs HOI4 national-focus, national-spirit/idea, technology, decision, ideology, or related UI icon artwork in vanilla, The Fire Rises (TFR), The New Order (TNO), Red Flood/赤潮, or a user-supplied reference style, including one-line human prompts, structured AI prompts, layered TFR focus packages, transparent PNG delivery, asset provenance, and GFX sprite wiring.
---

# Make HOI4 UI Icons

Produce one finished, validated icon from one prompt. Search the local library before generating new art. Keep source assets in place and preserve provenance.

## Resolve the request

1. Read [prompt-modes.md](references/prompt-modes.md).
2. Treat ordinary natural language as `human` mode. Infer omitted fields without changing explicit requirements.
3. Treat a JSON/YAML-like brief marked `ai` as strict structured input. Preserve all explicit fields.
4. Normalize style aliases to `vanilla`, `tfr`, `tno`, or `red-flood`. If style is absent, use `vanilla`.
5. Normalize icon type with [icon-types.md](references/icon-types.md). If type is absent, use `focus`.
6. Do not invent people, slogans, flags, text, or extra narrative objects. Add only composition and technical constraints needed for a readable icon.
7. For `style=tfr` and `icon_type=focus`, read [layered-tfr.md](references/layered-tfr.md) and use its layered workflow by default. Keep legacy flat inputs valid, but resolve them into grounded layers when enough subject information exists.

## Resolve the Python runtime

Resolve `<PYTHON>` once before running the bundled scripts. Use the active `python` when it can import Pillow. If `python -c "from PIL import Image"` fails, call the available workspace dependency discovery (`codex_app__load_workspace_dependencies`) and use the bundled Python path it returns. Do not install Pillow when a bundled runtime is available. If neither runtime has Pillow, search for an existing safe local runtime before asking to install anything.

## Resolve the library

Use the first directory that contains `素材库/` or `秋起美术馆/`:

1. An explicit path from the user.
2. `HOI4_ICON_LIBRARY_ROOT` when set.
3. The active workspace or its parent.

If no library root is available, continue with generation only. Ask for a path only when the user explicitly requires reuse of local material.

Use `<SKILL_DIR>/assets/library-index.jsonl` by default. When rebuilding is necessary, write a task-local index under the workspace instead of mutating an installed Skill, then use that path as `<INDEX>` for the rest of the request:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/build_index.py" `
  --library-root "<LIBRARY_ROOT>" `
  --output "<WORKSPACE>/output/.make-hoi4-ui-icons/library-index.jsonl" `
  --summary "<WORKSPACE>/output/.make-hoi4-ui-icons/library-summary.json"
```

Never execute `.exe` or `.lnk` files. Record archives but do not extract them automatically.

## Load only the needed rules

- Read [icon-types.md](references/icon-types.md) for canvas, safe-area, and target-project precedence.
- Read [reuse-policy.md](references/reuse-policy.md) before copying or compositing any asset.
- Read exactly one built-in style reference:
  - [styles-vanilla.md](references/styles-vanilla.md)
  - [styles-tfr.md](references/styles-tfr.md)
  - [styles-tno.md](references/styles-tno.md)
  - [styles-red-flood.md](references/styles-red-flood.md)
- For another style, inspect the user-provided reference image and create a request-local style brief. Do not add a permanent style profile unless asked.

## Search before generating

Search with the normalized subject, symbols, style, icon type, and bilingual aliases:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/search_assets.py" --index "<INDEX>" --query "<KEYWORDS>" --style <STYLE> --icon-type <TYPE> --limit 5 --json
```

For the best candidates:

1. Resolve `relative_path` against the library root.
2. Inspect every renderable candidate with `view_image` before selecting it.
3. Prefer a relevant permitted finished icon, then a matching template/frame/component, then a style exemplar.
4. Do not treat search score as visual proof.
5. Do not directly reuse `reference_only` or `unknown` assets.

Choose exactly one route:

- `reused`: the output uses authorized library pixels. Copy a permitted finished raster directly, or transform/composite permitted components; record finished pixels as `use=reused` and transformed components as `use=transformed`.
- `reference_guided`: use one to three inspected assets as visual references, then generate a new icon.
- `generated`: generate from the normalized brief when no useful local reference exists.

For a layered TFR focus, choose the route for each semantic theme and search
each theme separately. The final route remains `reused` when any authorized
library pixels are included; otherwise use `reference_guided` or `generated` as
before. Record every directly used or referenced asset in the shared
`sources.json`.

## Generate only when needed

Use the installed `$imagegen` skill and its built-in image tool path. Do not create a custom API client.

1. Label each input image as style reference, subject reference, or edit target.
2. Use at most three relevant reference images; avoid mixing unrelated styles.
3. Request a simple opaque subject on a perfectly flat chroma-key background with no shadow, floor, text, or watermark unless explicitly requested.
4. Use `#00ff00` by default and `#ff00ff` for green subjects.
5. Copy the selected generated source into the workspace.
6. Run the installed `remove_chroma_key.py` helper with soft matte and despill.
7. Inspect the transparent result. Retry only one targeted defect at a time.
8. Ask before switching to the CLI/API fallback or true model-native transparency.

For a layered TFR focus, generate or retrieve one independent transparent PNG
per theme. Generate narrative effects separately when they cannot be produced
deterministically. Theme sources must not contain baked outlines, shadows,
feathering, relief, rim light, frames, or global grading. Follow
[layered-tfr.md](references/layered-tfr.md) to write `brief.json`,
`composition.json`, structural effect layers, QA previews, and the composed
target-size source.

Preserve user invariants on every edit. Do not modify the original source asset.

## Finalize the icon

Prefer the target project’s existing neighboring icon dimensions and sprite convention. Use a bundled profile only when no target-project evidence exists.

Copy the selected reused or generated source into a task-local workspace path before finalizing. Write a task-local `sources.json` array with one object for every reused or referenced library asset using the exact fields in [reuse-policy.md](references/reuse-policy.md). Omit `--source-records` only when no library asset was used.

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" finalize `
  --input "<TRANSPARENT_SOURCE>" `
  --output "<WORKSPACE>/output/icons/<SLUG>/<SLUG>.png" `
  --manifest "<WORKSPACE>/output/icons/<SLUG>/manifest.json" `
  --manifest-root "<WORKSPACE>" `
  --profile <PROFILE> `
  --style <STYLE> `
  --icon-type <TYPE> `
  --creation-mode <reused|reference_guided|generated> `
  --prompt "<USER_PROMPT>" `
  --normalized-prompt "<NORMALIZED_BRIEF>" `
  --source-records "<WORKSPACE>/output/icons/<SLUG>/sources.json"
```

For a layered TFR focus, finalize the compositor output with
`--layout preserve-canvas --brief <BRIEF> --composition <SPEC> --layer-report <REPORT>`.
Do not send the same composition through the legacy trim-and-fit layout because
that would change layer positions and title-safe spacing.

The finalizer rejects unstructured provenance, source files outside the workspace, direct use of `unknown`/`forbidden` assets, and missing creator credit. It writes workspace-relative image paths to the manifest. Use `--credit "<ADDITIONAL_CREDIT>"` only for non-library attribution not already present in a source record.

Use `custom --width <W> --height <H>` for a verified target-mod size. Do not silently force every technology icon into one square profile.

Validate the result:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" validate --input "<FINAL_PNG>" --profile <PROFILE>
```

Require a decodable RGBA PNG, exact profile dimensions, visible subject, transparent canvas, no accidental clipping, no key-color fringe, and readable subject at 1:1 UI size. Visually inspect warnings; deliberate TNO break-frame art may touch an edge.

## Register in a mod only when requested

Confirm the active mod root before writing. Place the PNG under the target mod’s `gfx/` tree and use a unique `GFX_` name. Emit a minimal additive file only when the user supplies the target texture path:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" gfx `
  --sprite-name GFX_<UNIQUE_NAME> `
  --texture-path "gfx/interface/<PATH>/<ICON>.png" `
  --output "<MOD_ROOT>/interface/<MOD_PREFIX>_icons.gfx"
```

Confirm `spriteTypes = {}`, forward slashes, matching script reference, unique sprite name, and existing texture. State that UI/GFX verification requires a full HOI4 restart and fresh logs; do not launch the game unless explicitly asked.

## Deliver

Return:

- The final PNG inline and its workspace path.
- For layered TFR focuses, the `brief.json`, `composition.json`, theme/effect
  layer directories, and layer validation report.
- Style, icon type, dimensions, and creation route.
- Source asset IDs and required credits.
- Validation result and any remaining manual/in-game check.
- The GFX path and sprite name only when registration was requested.

Never claim generation, transparency, licensing, or in-game success without direct evidence.
