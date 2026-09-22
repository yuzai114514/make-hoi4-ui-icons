---
name: make-hoi4-ui-icons
description: Create or edit Hearts of Iron IV icons, icon materials, and portraits, or GUI concepts explicitly requesting HOI4 mod art styles.
---

# HOI4 图标工坊

把用户的主题或已有图片做成符合目标画风、实际尺寸清楚、可继续编辑的成品。支持原版、TFR、TNO、赤潮；普通玩法代码、通用 UI 编程不属于本 Skill。

## 完成条件

**一次请求内完成必要迭代，首次交付应当是经过自检与返修、在实际显示尺寸下加工效果成立且无明显问题的成品。** 制作前读 [验收与返修](references/acceptance.md) 明确终点；完成制作、实际导出、打开最终文件检查、修复问题并复查受影响部分后再返回。首次生成、首次合成、脚本通过或“比上一版好”都不是停止点。常规构图、素材、蒙版和字效返修自主完成，不等用户逐项指出问题。

用户只要提示词、草案、素材、拆层或评审时，完成该范围即可。工具不可用、必需输入缺失或用户约束确实冲突时，说明具体阻碍与已有成果，不把未完成稿称作成品。用户审美验收与游戏内验证分别记录；等待主观偏好确认不妨碍先完成客观检查和已知问题修复。

## 按任务读取

只读当前分支需要的内容；后续到达某阶段再读对应参考。

| 当前任务 | 去哪里看 |
| --- | --- |
| 输入有歧义、提供国策代码/文案、结构化数据或简短追问 | [输入方式](references/prompt-modes.md)；沿用已知条件，AI 负责缺省美术选择 |
| 制作国策图标 | [设计与文字](references/focus-design.md)；只选目标画风参考 |
| TFR 国策、素材与拼贴返修 | [TFR 风格](references/styles-tfr.md) + [制作与合成](references/layered-tfr.md)；默认在 Photoshop 完成加工、蒙版、排层与统一调整 |
| 其他图标画风 | 只选 [原版](references/styles-vanilla.md)、[TNO](references/styles-tno.md) 或 [赤潮](references/styles-red-flood.md) |
| TFR 领导人、顾问肖像 | [肖像参考](references/tfr-portraits.md)；身份来自本人参考，框内比例、裁切和受光参考同槽位 |
| 整张 GUI 概念图 | 查看实际 GUI 参考，保留用户指定结构与数据；图标画风只指导插画区域，不套用透明图标和国策留白流程 |
| 搜索、复用或生成素材 | [素材工作流](references/asset-workflow.md)；缺少的素材才用 `$imagegen`，先查看每张候选图 |
| 确定画布、透明区或最终导出 | [尺寸表](references/icon-types.md) → [导出与接入](references/export-and-integration.md)；只有请求接入时才读注册步骤 |
| 用 `compose_layers.py` 排版 | [脚本图层包](references/compositor-schema.md)；普通 PS 流程跳过 |

## 制作边界

- 先确定主题与粗构图中的主次、比例、朝向和遮挡，再按独立调整需要准备素材；以最终显示效果决定是否继续拆分或增加元素。
- 国策默认 `170×150`，加宽版 `210×150`，底部 `40px` 完全透明；用户后续明确覆盖时，按目标界面复查名称文字区域并记录依据。其他类型按尺寸表，肖像与整张 GUI 不套国策规格。
- 保留原料、真实提示词与参考角色、可编辑工程和必要旧稿；不覆盖用户原图。原料与同类参考参与验收，不用图层数、效果名称或操作记录代替看图。
- 素材库仅在任务中按 [复用规则](references/reuse-policy.md) 使用；不把素材库打包进 Skill。未请求接入时交付图片与工程；接入只写目标模组，不改依赖模组。

交付最终图片、可编辑工程路径和简短检查结论；预览与过程记录可作为证据，不能代替最终文件。视觉自检、技术检查、用户验收、游戏内验证各自说明真实状态。
