# 素材检索与生成

仅在寻找或生成素材时读取；使用已有任务素材做局部修订可跳过。文中的 `<SKILL_DIR>` 为当前 Skill 目录。

## Resolve the Python runtime

Resolve `<PYTHON>` once before running the bundled scripts. Use the active `python` when it can import Pillow. If `python -c "from PIL import Image"` fails, call the available workspace dependency discovery (`codex_app__load_workspace_dependencies`) and use the bundled Python path it returns. Do not install Pillow when a bundled runtime is available. If neither runtime has Pillow, search for an existing safe local runtime before asking to install anything.

## Resolve the library

Use the first directory that contains `素材库/` or `秋起美术馆/`:

1. An explicit path from the user.
2. `HOI4_ICON_LIBRARY_ROOT` when set.
3. The active workspace or its parent.

If no library root is available, continue with generation only. Ask for a path only when the user explicitly requires reuse of local material.

An explicit official-tutorial directory can be read directly as style evidence even when it lacks those library folders. See [TFR guide notes](tfr-guide-notes.md) for filenames and source distinctions; do not force a library rebuild to read a supplied guide.

Use `<SKILL_DIR>/assets/library-index.jsonl` by default. When rebuilding is necessary, write a task-local index under the workspace instead of mutating an installed Skill, then use that path as `<INDEX>` for the rest of the request:

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/build_index.py" `
  --library-root "<LIBRARY_ROOT>" `
  --permissions-index "<SKILL_DIR>/assets/library-index.jsonl" `
  --output "<WORKSPACE>/output/.make-hoi4-ui-icons/library-index.jsonl" `
  --summary "<WORKSPACE>/output/.make-hoi4-ui-icons/library-summary.json"
```

Do not execute `.exe` or `.lnk` files encountered in the material library; they are not artwork inputs. Record library archives but do not extract them automatically. This does not prohibit using the resolved Python runtime or the intended image editor.

The permissions index is a reviewed snapshot, not a directory-wide license. Only matching relative paths and SHA-256 hashes with `authorization_evidence` retain authorization. New or changed files become `unknown`. Before reusing a candidate directly from a prebuilt index, verify its content hash against the current file; rebuild or reassess changed files.

## Search before generating

Before copying or compositing library assets, read [reuse-policy.md](reuse-policy.md). Keep the output type and style selected through the entrypoint; asset retrieval does not turn portraits or GUI concepts into transparent focus icons. For an unlisted style, inspect the supplied reference and record a task-local style brief instead of changing this Skill.

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
