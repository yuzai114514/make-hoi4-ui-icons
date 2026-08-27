# Icon types and technical profiles

Select a technical profile before composing art. Never treat one observed size as a universal HOI4 rule.

## Profile priority

Resolve width, height, safe area, edge behavior, alpha treatment, naming, destination, and sprite convention in this order:

1. Inspect the target project's script reference, matching `interface/*.gfx`, and neighboring loaded assets.
2. Inspect an existing icon from the same target tree, screen, type, and style.
3. Use a matching local template or finished reference from the paths below.
4. If no reliable profile exists, make a conservative PNG preview and mark game dimensions and placement `需要人工校验`.

Do not resize a wide technology or oversized focus into a square merely because another subtype is square.

## National focus

- Trace `focus.icon` or its dynamic icon block to an exact `GFX_*` sprite.
- Place the PNG under the target project's established focus-icon path, commonly `gfx/interface/goals/`.
- Register it in `interface/*.gfx` under `spriteTypes = {}`.
- Preserve title-safe space and intentional frame breaks defined by the selected style/profile.

Local evidence: `素材库/国策模板/`, `素材库/国策底面/`, and `素材库/国策图标/`. These contain repeated `100x88` examples, but also many other dimensions.

## National spirit or idea

- Trace `picture = token` to the matching `GFX_idea_<token>` sprite used by the project.
- Place the PNG under the project's established idea path, commonly `gfx/interface/ideas/`.
- Keep the silhouette readable at the actual idea-slot scale and prevent overlap with adjacent slots.

Local evidence: `素材库/国家精神模板/` and `素材库/国家精神底面/`. They contain repeated `60x68` examples plus other profiles.

## Technology

- Identify the subtype before sizing: standard node, equipment/wide art, doctrine, special project, or custom GUI technology.
- Trace the target technology's sprite token and use the same suffix and path convention as its neighbors, often `GFX_<token>_medium` and `gfx/interface/technologies/`.
- Copy the exact dimensions and composition envelope of the nearest same-subtype project asset.

Treat square and wide technology textures as distinct profiles. The library does not provide a complete verified technology profile set; inspect the target project and never force every technology into one square size.

## Other UI icons

For decisions, ideologies, laws, categories, or scripted GUI icons, derive the profile only from the target script, `.gui`, `.gfx`, and adjacent texture. Do not reuse focus or idea profiles by analogy.

## PNG and GFX chain

Deliver an 8-bit RGBA PNG unless the target project proves another format is required. Keep transparent areas genuinely transparent and inspect the result on light and dark backgrounds.

```txt
spriteTypes = {
    spriteType = {
        name = "GFX_mod_icon_name"
        texturefile = "gfx/interface/<project-folder>/mod_icon_name.png"
    }
}
```

Use forward slashes in `texturefile`. Require an exact chain:

`script or GUI reference -> GFX sprite name -> interface/*.gfx -> existing PNG`

After changing a PNG or `.gfx` file, require a complete HOI4 restart for final verification. A local preview proves appearance only; it does not prove that HOI4 loaded the sprite. Inspect fresh logs for `Could not find sprite`, `Could not find texture`, and `Unknown GUI`.

Evidence paths relative to the library root:

- `素材库/国策模板/`
- `素材库/国策底面/`
- `素材库/国策图标/`
- `素材库/国家精神模板/`
- `素材库/国家精神底面/`
- `秋起美术馆/TFR/TFR官方教程及素材合集/标准画布大小参考.psd`
- `秋起美术馆/赤潮/图标 Icons/EXAMPLE 1.psd`
- `秋起美术馆/赤潮/图标 Icons/EXAMPLE IDEAS.psd`
