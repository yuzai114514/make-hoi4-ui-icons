---
name: make-hoi4-ui-icons
description: Retrieve, reuse, generate, layer, finalize, and optionally register Hearts of Iron IV UI icons and leader portraits in vanilla, The Fire Rises (TFR), The New Order (TNO), and Red Flood/赤潮 styles. Use for focus, idea, technology, portraits, and other UI artwork, or when explicitly asked to borrow these styles for a GUI concept; a GUI concept is not a game-ready icon package.
---

# Make HOI4 UI Icons

**TFR 国策图标一句话流程：从已有代码与文案理解主题，参考邻图并试排构图，再找或生成素材，在 Photoshop 中按官方教程加工、合成与统一调整，分别检查实际尺寸下的主题表达与 TFR 观感，合格后保留 PSD 并导出透明 PNG。**

**画布尺寸严格按 [尺寸表](references/icon-types.md)：国策 170×150 或加宽版 210×150，底部 40px 完全透明；其余类型按表，不另改尺寸。**

Produce attractive artwork that fits the target project. Search available local material before generating missing assets; preserve originals and provenance. For TFR focus icons, Photoshop is the default finishing tool. Prioritize the artwork's appearance over preset values: substantial shadow, vivid gradients and a slight visible bevel should support material volume and readability. Read [material processing](references/tfr-material-processing.md) for the Photoshop workflow.

用户可直接提供国策代码与文案。AI 负责主题提炼、视觉设计、素材选择、风格加工与返修，不要求用户具备美术知识或逐步指导构图；输入解析见 [输入方式](references/prompt-modes.md)。

## 国策设计参考

以下建议按主题、目标界面和编辑需要灵活采用；数量与示例是设计起点，不是配额或验收门槛。

**改编参考图时，先识别决定其主题、动作与情绪的视觉关系，再拆分和加工。** 风格处理应保留这些关系的表现力；交付前按接近的主体显示大小比较原图、加工版与目标风格参考，分别检查视觉表达、风格表现与文件规格。拆图方法见 [素材制作与合成](references/layered-tfr.md)，视觉检查见 [素材加工](references/tfr-material-processing.md#保留工程与检查成品)。

1. **先理解主题，让图标讲述国策。** 从国策名、文案与分支语境提炼核心政策、动作或变化，通过主体、动作、隐喻及相互关系把它画出来。看过国策名再看图，应能理解画面为何对应这个名称；从图标反向看，也应能联想到国策的核心含义，并与相近节点区分。故事感来自画面中可读的关系，不靠堆放相关物件或照抄标题补足；以核心语义相符为准，不要求逐字猜中名称，也不为叙事强加多个主体或复杂场景。
2. **自由选择画面表达。** 按主题选择或创造人物、物件、符号、动作、隐喻和场景，不局限于固定构图或示例，以主题清楚、画面有吸引力为准。
3. **按表达与编辑需要分层。** 主要素材层通常以 2～4 层为起点，简单主体可用 1 层，复杂构图可用 5～6 层，按需增减；文字、光效、阴影和调整层不计入。不为凑层数添加素材，连贯场景也不必逐个物件拆开。
4. **有选择地加入独立文字。** 默认每 4～6 张图标约选 1 张，优先用于总纲、转折或成果节点；通常写 2～6 个汉字的关键词、行动短语或口号，不照抄完整国策名称。文字融入画面，字体清楚、色彩协调，可适量添加描边、阴影或发光，不遮挡主体。物件自带文字和商标不计入比例，具体频率按设计需要调整，单张也不必为凑比例加字。
5. **协调同分支，区分各节点。** 优先参考同一路线、同一子分支的邻图，协调配色、质感和视觉密度，同时通过主体、动作和构图区分节点，避免整条线重复套用同一模板。
6. **检查实际显示效果。** 遵循现有尺寸与留白规格，在实际显示尺寸下检查主体和文字的辨识度。

## Choose the deliverable first

- `icon`: a finished standalone icon; follow the icon workflow below.
- `material` (legacy alias `theme`): one editable material unit for a layered icon; it may contain a single object or a related group. For TFR, follow [layered-tfr.md](references/layered-tfr.md).
- `portrait`: a leader or advisor portrait. For TFR, read [tfr-portraits.md](references/tfr-portraits.md) and match neighboring portraits in lighting, head scale, and the anatomical point at the bottom crop. Use their actual portrait profile; skip focus layering, title-safe areas, and automatic transparent-icon finalization.
- `gui-concept`: a whole interface screenshot or panel concept. Preserve the canvas, UI structure, text, and data; inspect an actual GUI reference for panels, typography, spacing, borders, and controls. Apply icon styling only within illustration areas. Keep the intended opaque canvas; skip icon profiles, chroma-key removal, focus layering, and GFX registration for the whole image.
- A request for prompts alone returns request-specific prompt text without generating an image.

Do not assume a whole interface is a focus icon. A focus-icon reference can guide a local illustration, but cannot establish the appearance of panels, buttons, text, or the entire screen.

## Resolve the request

1. Read [prompt-modes.md](references/prompt-modes.md).
2. Treat ordinary natural language as `human` mode. Resolve short follow-ups against the established deliverable and constraints using [prompt-modes.md](references/prompt-modes.md); infer omitted fields without changing explicit requirements.
3. Treat a JSON/YAML-like brief marked `ai` as structured input. Preserve explicit requirements and resolve omitted creative choices; use strict validation when the caller requests a strict contract.
4. Normalize style aliases to `vanilla`, `tfr`, `tno`, or `red-flood`. Use `vanilla` only when neither the current request nor the established context identifies a style.
5. Normalize icon type with [icon-types.md](references/icon-types.md). If type is absent, use `focus`. For focus icons, follow its standalone-lettering guidance; distinguish added typography from text belonging to depicted objects.
6. Apply the design references above while preserving specified identities, facts, and user invariants; distinguish creative choices from factual requirements.
7. For `style=tfr` and `icon_type=focus`, read [styles-tfr.md](references/styles-tfr.md) and the production steps in [layered-tfr.md](references/layered-tfr.md). Prepare usable materials, then process and compose them in Photoshop. Read the optional script-package schema only when using the compositor.

## Resolve the Python runtime

Resolve `<PYTHON>` once before running the bundled scripts. Use the active `python` when it can import Pillow. If `python -c "from PIL import Image"` fails, call the available workspace dependency discovery (`codex_app__load_workspace_dependencies`) and use the bundled Python path it returns. Do not install Pillow when a bundled runtime is available. If neither runtime has Pillow, search for an existing safe local runtime before asking to install anything.

## Resolve the library

Use the first directory that contains `素材库/` or `秋起美术馆/`:

1. An explicit path from the user.
2. `HOI4_ICON_LIBRARY_ROOT` when set.
3. The active workspace or its parent.

If no library root is available, continue with generation only. Ask for a path only when the user explicitly requires reuse of local material.

An explicit official-tutorial directory can be read directly as style evidence even when it lacks those library folders. See [TFR guide notes](references/tfr-guide-notes.md) for filenames and source distinctions; do not force a library rebuild to read a supplied guide.

Use `<SKILL_DIR>/assets/library-index.jsonl` by default. When rebuilding is necessary, write a task-local index under the workspace instead of mutating an installed Skill, then use that path as `<INDEX>` for the rest of the request:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/build_index.py" `
  --library-root "<LIBRARY_ROOT>" `
  --permissions-index "<SKILL_DIR>/assets/library-index.jsonl" `
  --output "<WORKSPACE>/output/.make-hoi4-ui-icons/library-index.jsonl" `
  --summary "<WORKSPACE>/output/.make-hoi4-ui-icons/library-summary.json"
```

Never execute `.exe` or `.lnk` files. Record archives but do not extract them automatically.

The permissions index is a reviewed snapshot, not a directory-wide license. Only matching relative paths and SHA-256 hashes with `authorization_evidence` retain authorization. New or changed files become `unknown`. Before reusing a candidate directly from a prebuilt index, verify its content hash against the current file; rebuild or reassess changed files.

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

1. Resolve the search result's `path` (the index's `relative_path`) against the library root.
2. Inspect every renderable candidate with `view_image` before selecting it.
3. Prefer a relevant permitted finished icon, then a matching template/frame/component, then a style exemplar.
4. Do not treat search score as visual proof.
5. Do not directly reuse `reference_only` or `unknown` assets.

Choose exactly one route:

- `reused`: the output uses authorized library pixels. Copy a permitted finished raster directly, or transform/composite permitted components; record finished pixels as `use=reused` and transformed components as `use=transformed`.
- `reference_guided`: use one to three inspected assets as visual references, then generate a new icon.
- `generated`: generate from the normalized brief when no useful local reference exists.

For a layered TFR focus, choose the route for each editable material and search
for the missing material types. The final route remains `reused` when any authorized
library pixels are included; otherwise use `reference_guided` or `generated` as
before. Record every directly used or referenced asset in the shared
`sources.json`.

## Generate only when needed

Use the installed `$imagegen` skill and its built-in image tool path. Do not create a custom API client.

1. Write a request-specific prompt from the actual subject, composition, palette, lighting, output type, reference roles, and user constraints. Use the selected style guidance and inspected references; there is no fixed prompt template or recipe ID. A style name alone or a long collection of unrelated prohibitions will not define the intended image.
2. Label each input image as style reference, subject reference, or edit target.
3. Use a small set of relevant references within the tool's limits. Give each a clear purpose and avoid mixing incompatible styles.
4. For an icon or material cutout, request native transparency through the installed `$imagegen` skill and inspect the actual alpha. If a chroma-key workflow is needed, choose `#00ff00` or `#ff00ff` that does not occur in the subject, remove it with the installed `remove_chroma_key.py` helper, and record `chroma_key = green|magenta`. Use `none` for native alpha or reused transparent art. Whole GUI concepts retain an opaque canvas.
5. Copy the selected generated source into the task workspace. In its `generation.json`, record the exact prompt sent, reference roles and paths, output path, chroma key, and visual observations for each call. Preserve revisions; use `pending` until the image has actually been inspected, then record observed problems or acceptance. These task records are separate from the Skill files.
6. Inspect the actual output for technical validity, subject accuracy, and visual quality. Repair the affected material or processing stage; regenerate a whole composition only when the overall concept needs revision.
7. Use the installed imagegen rules for any CLI/API fallback.

For TFR focuses, use generation to supply missing materials or repair observed
structural problems. Perform the main tonal, layer-style, mask and composition
work in Photoshop, keeping originals and an editable PSD. Suitable finished
materials can be reused without repeating treatments. Describe observed defects
directly when a specific generative repair is needed; there is no mandatory raw/edit/composite sequence.
The bundled compositor is an optional layout helper; it does not provide Camera
Raw, gradient grading or a Photoshop-equivalent bevel. Use its JSON package only
when actually composing with the script; a Photoshop workflow does not need it.

Preserve user invariants on every edit. Do not modify the original source asset.

## Finalize the icon

Use the exact canvas sizes in [icon-types.md](references/icon-types.md). Consult target-project dimensions only for unlisted types or a later explicit user override; follow the target project's sprite convention.

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
  --chroma-key <none|green|magenta> `
  --source-records "<WORKSPACE>/output/icons/<SLUG>/sources.json"
```

When using the scripted layered package, finalize the compositor output with
`--layout preserve-canvas --brief <BRIEF> --composition <SPEC> --layer-report <REPORT>`.
Do not send the same composition through the legacy trim-and-fit layout because
that would change layer positions and title-safe spacing.

For a Photoshop export already at the target dimensions, also use `--layout preserve-canvas` to keep the PSD layout; no script brief, composition or layer report is needed.

The finalizer rejects unstructured provenance, source files outside the workspace, direct use of `unknown`/`forbidden` assets, and missing creator credit. It writes workspace-relative image paths to the manifest. Use `--credit "<ADDITIONAL_CREDIT>"` only for non-library attribution not already present in a source record.

Use `custom --width <W> --height <H>` for table entries without a named profile or verified sizes of unlisted types. For a 210×150 focus, use `focus` or `focus-tfr` with `--width 210`, including during validation. Do not silently force every technology icon into one square profile.

Validate the result:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" validate --input "<FINAL_PNG>" --profile <PROFILE> --chroma-key <none|green|magenta>
```

Require a decodable RGBA PNG, exact profile dimensions, visible subject, transparent canvas, no accidental clipping, no key-color fringe, and readable subject and lettering at actual UI display size. Visually inspect warnings; deliberate TNO break-frame art may touch an edge.

Pass the same recorded chroma key to finalization and standalone validation. Color counts are diagnostic; only the selected removed background color is rejected. Layered packages validate each source against its own key and use `none` on the final composite, since another layer may intentionally use that color.

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
- For TFR focuses processed in Photoshop, the editable PSD and source materials.
  When using the optional compositor, include its composition package and report.
- Style, icon type, dimensions, and creation route.
- The task-local `generation.json` path for generated artwork.
- Source asset IDs and required credits.
- Validation result and any remaining manual/in-game check.
- The GFX path and sprite name only when registration was requested.

Never claim generation, transparency, licensing, or in-game success without direct evidence.
