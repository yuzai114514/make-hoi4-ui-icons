# Icon types and technical profiles

尺寸严格按用户提供的《各类图标画布尺寸参考》执行，单位为像素（宽 × 高）。

| 类型 | 画布尺寸 |
| --- | --- |
| 国策 | 170×150；加宽版 210×150 |
| 意识形态 | 66×68 |
| 民族精神及法律 | 68×68 |
| 地区修正 | 68×68 或 32×32，按所用槽位选择 |
| 权力平衡 | 72×88 |
| 阵营图标 | 65×65 |
| 军工组织 | 48×48 |
| 决议图标 | 35×35 |

国策默认用 170×150；需要加宽时用 210×150，不取中间尺寸。两种画布底部 40px（y=110–149）均完全透明，阴影、发光和文字也不得进入。

脚本中 `focus`、`focus-tfr` 默认对应 170×150，加宽时传 `--width 210`；`idea` 对应 68×68。其余表内类型用 `custom --width W --height H` 填入表中尺寸即可。

## Profile priority

上表尺寸与国策留白是本 Skill 的制作规格，旧教程、相邻素材或风格示例不能自动覆盖。用户后续明确指定其他尺寸时按新指令执行；科技、肖像及整张 GUI 等未列类型，再从目标项目确定尺寸。路径、命名和 sprite 约定仍按以下依据核对：

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

Local composition references: `素材库/国策模板/`, `素材库/国策底面/`, and `素材库/国策图标/`. Their source dimensions do not change the canvas sizes above.

### Standalone lettering in focus icons

独立文字的频率、长度、选词和排版统一见 [国策设计参考](../SKILL.md#国策设计参考)。书封、文件封面、铭牌、标牌等物件自身的文字与商标按真实性与可读性判断，不因独立加字比例自动删除。

在游戏实际尺寸下，同时检查图内文字与下方国策名称是否清晰可读、是否互相挤压。下方名称只用于预览核对，独立图标导出仍保留标题安全区；本地预览不等于游戏内验证。

## National spirit or idea

- Trace `picture = token` to the matching `GFX_idea_<token>` sprite used by the project.
- Place the PNG under the project's established idea path, commonly `gfx/interface/ideas/`.
- Keep the silhouette readable at the actual idea-slot scale and prevent overlap with adjacent slots.

Local composition references: `素材库/国家精神模板/` and `素材库/国家精神底面/`. Export national spirits and laws at 68×68 as listed above.

## Technology

- Identify the subtype before sizing: standard node, equipment/wide art, doctrine, special project, or custom GUI technology.
- Trace the target technology's sprite token and use the same suffix and path convention as its neighbors, often `GFX_<token>_medium` and `gfx/interface/technologies/`.
- Copy the exact dimensions and composition envelope of the nearest same-subtype project asset.

Treat square and wide technology textures as distinct profiles. The library does not provide a complete verified technology profile set; inspect the target project and never force every technology into one square size.

## Other UI icons

For decisions, ideologies, laws and other types listed above, use the exact table dimensions. Only unlisted types derive their profile from the target script, `.gui`, `.gfx`, and adjacent texture.

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
