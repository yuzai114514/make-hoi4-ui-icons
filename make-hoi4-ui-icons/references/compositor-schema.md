# 可选的脚本图层包

仅在使用 `compose_layers.py` 时读取。Photoshop 直接制作与导出无需这套 JSON。


以下仅供使用 `compose_layers.py` 时查阅。PS 流程保留原料、PSD、最终 PNG 和必要的提示词及来源记录即可，不必另建这套 JSON 图层包；需要脚本排布或导出预览时，再导出所需透明素材。

使用脚本时保留兼容字段名 `themes`，其含义为**可编辑素材单元**，至少一个，没有固定上限。`effects` 放需要独立编辑的画面效果，可以为空。同一题材可拆成多块素材；一个素材也可包含多个相互关联的物体。

建议目录：
```text
layers/raw/           生成或获准复用的原料，保留不覆盖
layers/processed/     修整后的透明 PNG，作为 composition 的 source
layers/effects/       独立画面效果及脚本导出的结构效果
brief.json            意图、设计选择与素材记录
generation.json       实际工具提示词、参考角色、输出版本与视觉检查
composition.json      布局与可选图层效果
composite-source.png  合成结果
composite-source.layers.json  技术报告
qa/materials/         输入素材变换后的预览，不含脚本新增边缘效果
qa/final/             添加脚本效果后的预览、层级图和整图
final.png             最终图标
```

已有包的 `layers/themes/` 路径继续有效。目录名称不是构图约束；`qa/materials/` 反映传入脚本的素材，如果 source 已做调色或蒙版，它也会反映这些处理。

下面是一份完整的单素材示例，展示脚本字段，不限定其他主题的构图。写入 `brief.json`：
```json
{
  "schema_version": 1,
  "input_mode": "human",
  "style": "tfr",
  "icon_type": "focus",
  "profile": "focus-tfr",
  "focus_name": "恢复生产",
  "focus_description": null,
  "input_basis": {"focus_name": "provided", "focus_description": "missing"},
  "themes": [{
    "id": "machine",
    "name": "机床",
    "role": "primary",
    "evidence": "以运转的机床表现恢复生产，是构图选择",
    "subject": "现代工业机床",
    "motifs": ["机床"],
    "placement": "中部主视觉",
    "palette": "钢灰与暖光",
    "prompt": "填写实际素材提示词；复用时说明无需生成"
  }],
  "effects": [],
  "constraints": ["国策画布底部 40px 透明"]
}
```

这些是脚本内部的记录字段，不是给用户的问卷。`input_mode` 为 `human|ai`；名字或描述缺失时用 `null` 和 `missing`，其余情况记录 `provided|derived`。`role` 可为 `primary|secondary|background|context`。`evidence` 记录输入依据或设计理由，并不声称自动核验事实。不要编造从未发送的提示词；实际工具调用放在 `generation.json`，素材计划变化时同步更新记录。

`composition.json`：
```json
{
  "schema_version": 1,
  "style": "tfr",
  "icon_type": "focus",
  "profile": "focus-tfr",
  "brief": "brief.json",
  "canvas": {"width": 170, "height": 150, "safe_bottom": 40},
  "themes": [{
    "id": "machine",
    "name": "机床",
    "role": "primary",
    "evidence": "以运转的机床表现恢复生产，是构图选择",
    "source": "layers/processed/machine.png",
    "chroma_key": "none",
    "source_asset_ids": [],
    "z": 10,
    "transform": {"x": 35, "y": 12, "width": 110, "height": 82, "rotation": 0},
    "opacity": 1.0,
    "blend": "normal"
  }],
  "effects": []
}
```

示例没有新增边缘效果，仅适合已完成风格加工的素材；不代表原始抠图无需加工就可以交付。按素材加工方法记录效果完成在哪一步。增加素材时同步 `brief.json` 和 `composition.json` 的 ID、名称、角色与设计理由；独立效果的 ID、名称与 kind 也要匹配。唯一 ID 和匹配校验用于防止丢层及记录错配，不判断艺术是否合格。

独立效果的 brief 条目使用 `id, name, kind: narrative, evidence, subject, placement, palette, prompt`；composition 条目使用 `id, name, kind: narrative, source, z, transform`，以及可选的 `chroma_key, source_asset_ids, opacity, blend`。`narrative` 是沿用的格式标识，可包括烟雾、闪光等画面效果，不要求每个效果另成一个主题。

## 可选的脚本效果

`boundary` 可省略或设为 `{}`。可用的 `primary`、`support` 是两个兼容配置槽，均不必填写，不代表每层必须有一个“主要边界”。例如按需要给上述素材添加：
```json
{
  "boundary": {
    "primary": {"type": "shadow", "offset": [2, 2], "blur": 2, "color": "#20151a", "opacity": 0.7}
  },
  "finish": {
    "relief": {"depth": 1, "opacity": 0.18}
  }
}
```

参数是试用起点；在 1:1 下判断后再调整。成品阴影应厚重、渐变应鲜艳、倒角应轻微可见；人物、舰船、建筑没有固定数值配方。脚本的 relief 只是简化浮雕，不等于官方倒角已完成。

脚本支持以下字段：
- `outline`：`width`（正整数）、`color`（#RRGGBB）、`opacity`。
- `feather`：`radius`（0.1–20），适合整体轻度柔化；局部蒙版请在素材处理阶段完成。
- `shadow`：`offset: [x,y]`、`blur`（0–30）、`color`、`opacity`。这是以 multiply 合成的阴影，不能替代所有发光效果。
- `outer_glow`：`spread`（0–20 整数）、`blur`（0.1–30）、`color`、`opacity`、`blend`（normal/screen/multiply）。按轮廓扩张、柔化并排除主体内部，生成独立外部光晕。深色可补厚阴影，亮色可发光；不是细描边。
- `relief`：`depth`（正整数）、`opacity`，仅为简化浮雕。
- `finish.relief`：`depth`、`opacity`；`finish.rim`：`width`、`color`、`opacity`。
- 所有 opacity 为 0–1，没有美术强度上限。两个 boundary 槽不能重复同一种类型，因为当前导出名按类型区分。

这些是脚本能力范围，不是 TFR 风格允许的全部技法。渐变映射、Camera Raw 式调整、局部蒙版、多重发光、组效果可在图像编辑阶段完成，保存处理版作为 source。脚本不自动调色，也不自动清除标题范围内的像素；它会拒绝越界结果，便于回到素材或布局修正。

## 运行与导出

composition 内路径相对于该文件，解析后仍须位于 `--manifest-root` 内。源图是可解码、非空、有真实透明区域的 RGBA PNG。`transform` 指效果扩展前的左上角、宽高与旋转；尽量保持比例，用素材裁切解决长宽不合，而不是拉伸人物。`z` 从小到大合成，支持 `normal|screen|multiply`。

`chroma_key` 记录该层实际去掉的背景色 `green|magenta`；原生透明或透明复用素材用 `none`。每层单独检查残留，不禁止其他层有意使用绿色或品红。

```powershell
& "<PYTHON>" "<SKILL_DIR>/scripts/compose_layers.py" validate `
  --spec "<TASK>/composition.json" --manifest-root "<WORKSPACE>"

& "<PYTHON>" "<SKILL_DIR>/scripts/compose_layers.py" compose `
  --spec "<TASK>/composition.json" --manifest-root "<WORKSPACE>" `
  --output "<TASK>/composite-source.png" `
  --effects-dir "<TASK>/layers/effects" --qa-dir "<TASK>/qa" `
  --report "<TASK>/composite-source.layers.json"

& "<PYTHON>" "<SKILL_DIR>/scripts/finalize_icon.py" finalize `
  --input "<TASK>/composite-source.png" --output "<TASK>/final.png" `
  --manifest "<TASK>/manifest.json" --manifest-root "<WORKSPACE>" `
  --profile focus-tfr --style tfr --icon-type focus `
  --creation-mode generated --chroma-key none `
  --layout preserve-canvas --brief "<TASK>/brief.json" `
  --composition "<TASK>/composition.json" `
  --layer-report "<TASK>/composite-source.layers.json"
```

按实际情况更换 creation mode；用过库内素材或参考时同时传 `--source-records <TASK>/sources.json`，参见 [reuse-policy.md](reuse-policy.md)。若后续编辑了合成结果，先保存新版本，重新检查最终 PNG；原脚本报告只代表编辑前的版本，不把它冒充成编辑后逐像素一致的分层报告。

`focus-tfr` 默认 `170×150 / safe_bottom=40`，加宽版用 `210×150`，底部 alpha 必须为零。加宽时 composition 的 `canvas.width` 写 `210`，finalizer 的定稿与校验命令均传 `--width 210`。保留目标画布使用 `preserve-canvas`，避免 trim-and-fit 改变已经确定的布局。

默认输出自动保留版本。明确使用 `--overwrite` 时，脚本只清理登记过的旧 QA 文件，不递归删除未知文件。该工具输出 PNG 图层和 JSON，不导出 PSD；使用支持 PSD 的编辑器时可同时保留其工程文件。
