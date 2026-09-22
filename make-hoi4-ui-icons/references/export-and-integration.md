# 导出与模组接入

导出透明图标时读定稿部分；只有用户要求接入模组时才读注册部分。先按 [尺寸表](icon-types.md) 确定规格，再执行下列命令。`<PYTHON>` 的解析见 [素材工具运行时](asset-workflow.md#resolve-the-python-runtime)。以下透明图标定稿器不用于整张 GUI 或保留背景的肖像。

## Finalize the icon

Use the exact canvas sizes in [icon-types.md](icon-types.md). Consult target-project dimensions only for unlisted types or a later explicit user override; follow the target project's sprite convention.

Copy the selected reused or generated source into a task-local workspace path before finalizing. Write a task-local `sources.json` array with one object for every reused or referenced library asset using the exact fields in [reuse-policy.md](reuse-policy.md). Omit `--source-records` only when no library asset was used.

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

用户明确覆盖国策尺寸或透明区时，使用 `--profile custom --width <W> --height <H> --safe-bottom <N>` 并保留 `--layout preserve-canvas`。定稿与校验传相同尺寸、透明区和色键参数，不为通过默认校验偷偷改变用户指定布局。需要完全透明时同时用 `--alpha-threshold 0`；保留覆盖依据并检查目标名称字形区域。

Validate the result:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" validate --input "<FINAL_PNG>" --profile <PROFILE> --chroma-key <none|green|magenta>
```

Require a decodable RGBA PNG, exact profile dimensions, visible subject, transparent canvas, no accidental clipping, no key-color fringe, and readable subject and lettering at actual UI display size. Visually inspect warnings; deliberate TNO break-frame art may touch an edge.

Pass the same recorded chroma key to finalization and standalone validation. Color counts are diagnostic; only the selected removed background color is rejected. Layered packages validate each source against its own key and use `none` on the final composite, since another layer may intentionally use that color.

这些命令给出技术结果。完成后仍需按 [验收与返修](acceptance.md) 查看当前导出；不让打包脚本赋予或继承视觉通过状态。

## Register in a mod only when requested

Confirm the active mod root before writing; change only that mod, not its dependencies. Place the PNG under the mod’s `gfx/` tree and use a unique `GFX_` name. Follow an explicit texture path, or derive it from the active mod's conventions when integration is requested; do not ask the user to invent a routine path. Emit a minimal additive definition:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" gfx `
  --sprite-name GFX_<UNIQUE_NAME> `
  --texture-path "gfx/interface/<PATH>/<ICON>.png" `
  --output "<MOD_ROOT>/interface/<MOD_PREFIX>_icons.gfx"
```

Confirm `spriteTypes = {}`, forward slashes, matching script reference, unique sprite name, and existing texture. State that UI/GFX verification requires a full HOI4 restart and fresh logs; do not launch the game unless explicitly asked.

## Deliver

只有请求范围内的 [完成条件](acceptance.md#什么才算完成) 满足后，才将下面的文件作为成品交付。用户审美验收或未请求的游戏验证可以待确认；已发现且未修复的明显问题不能以“待用户验收”代替。

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
