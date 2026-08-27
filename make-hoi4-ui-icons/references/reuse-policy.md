# Asset reuse policy

Prefer a suitable existing asset over generating a near-duplicate. Preserve provenance and authorization at every step.

## Retrieval order

1. Search by exact filename and normalized filename.
2. Filter by icon type, style, subject, format, dimensions, and alpha.
3. Rank a finished, profile-compatible icon above a template; rank a template above loose parts.
4. Use generation only when no authorized match satisfies the brief or when the user explicitly forbids reuse.

Disambiguate repeated names by type and role. For example, `Shield` appears as a national-spirit template, focus background, and loose symbol; never select by basename alone.

## Authorization states

Assign one state to every candidate:

- `approved`: reuse is explicitly supported by local provenance or user permission.
- `credit_required`: reuse only while carrying the creator and required credit into the result manifest.
- `unknown`: set `use = reference_only`. Do not copy, crop, recolor, composite, export, or ship the file.
- `forbidden`: do not inspect beyond what is necessary to identify and exclude it.

Treat missing provenance as `unknown`, never as implied permission.

## Library boundary

Do not copy the library into the Skill, publish it as Skill assets, or expose absolute machine paths. Refer to source files by paths relative to the library root.

Apply these local rules:

- `素材库/README.md` forbids re-uploading the repository assets.
- Finished icons under `素材库/现成素材/<creator>/` require credit to the creator named by the folder.
- `素材库/CREDITS.txt` records contributors but does not replace per-file provenance.
- Tutorial documents and artwork collected under `秋起美术馆/` do not prove redistribution rights; default them to `reference_only` unless a more specific license is recorded.

## Result manifest

Record for every reused or referenced file:

```yaml
asset_id: "indexed asset id"
source: "relative/library/path"
role: finished | finished_icon | component | template | background | symbol | style_reference | subject_reference | reference_asset | editable_source | palette
authorization: approved | credit_required | unknown | forbidden
use: reused | transformed | reference_only | excluded
credit: "creator or null"
```

Write the records as a JSON object or array in a task-local workspace file and pass it to `finalize_icon.py` with `--source-records`. Each object must contain exactly the six fields above; unknown fields are rejected. The finalizer fails closed when `reused` has no authorized direct source, when `unknown` or `forbidden` pixels are marked reused/transformed, or when a directly used `credit_required` source lacks its creator. Do not claim an AI-generated replacement is independent when it traces a restricted asset closely.

The search helper reports `authorization` in this exact vocabulary. Map `recommended_use = direct` to `use = reused`, `composite` to `transformed` only when its pixels are actually used, and `reference` to `reference_only`. Keep `forbidden` as `excluded`.

Evidence paths relative to the library root:

- `素材库/README.md`
- `素材库/CREDITS.txt`
- `素材库/现成素材/`
- `秋起美术馆/更新日志.txt`
