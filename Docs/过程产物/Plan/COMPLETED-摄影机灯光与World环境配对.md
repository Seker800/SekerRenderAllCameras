# 摄影机灯光与 World 环境配对实施计划

- 状态：COMPLETED
- 日期：2026-09-16
- 目标版本：0.4.0
- 入口：Domain 渲染计划、Blender Scene Reader/Render Adapter/State Transaction、Presentation 配对 UI、RenderInfo、测试与文档
- 权威来源：`domain/models.py::RenderPlan`、`blender/scene_reader.py`、`blender/render_adapter.py`、`blender/state_transaction.py`
- 依赖：Blender Object/Collection/World RNA，现有 BatchCoordinator 与辅助 Scene 路径
- 阻塞：无

## 用户可观察结果

- 插件面板中可新建多条“摄影机 + 灯光 Collection + World”配对。
- 渲染已配对摄影机时，只启用配对 Collection 及子 Collection 内的 Light，其他 Light 临时忽略；同时临时切换到配对 World。
- Light Collection 可留空，表示不改灯光；World 可留空，表示不改 World。
- 没有配对的摄影机保持现有行为，旧文件和旧工作流不受影响。
- 正常完成、失败、取消、异常和卸载后，`Scene.world` 与 Light `hide_render` 恢复为任务前值。

## 范围与非目标

- 范围：单 Camera 的可选 Light Collection/World 覆盖，配对 UI，不可变计划 DTO，渲染时切换，状态恢复，清单记录和回归测试。
- 非目标：同一 Camera 一次渲染多套环境；改输出文件名；自动保存 `.blend`；编辑 World 节点；隐藏同 Collection 内的非 Light 对象。

## 当前实现与责任所有者

- `Presentation` 只收集 Blender 指针并交给 Blender 边界冻结，不实现渲染规则。
- `scene_reader` 是 Blender 数据块转为 Domain DTO 的唯一边界，负责验证重复 Camera 并冻结 Collection 中的 Light 稳定键。
- `RenderPlan` 继续是批次输入的唯一真相源，Domain/Application 不引入 `bpy`。
- `BlenderRenderAdapter` 幂等应用环境；`BlenderStateTransaction` 唯一负责最终恢复。

## 方案比较与决策

### 方案 A：切换 Collection/View Layer 排除状态

- 优点：接近 Outliner 手工切换整组的思路。
- 缺点：嵌套 LayerCollection、多 View Layer 和辅助 Scene 恢复复杂，还会误伤同 Collection 内模型。
- 结论：拒绝。

### 方案 B：冻结 Collection 中的 Light，只切换 Light.hide_render 与 Scene.world

- 优点：只影响灯光，容易快照和恢复，不依赖渲染中途 UI 变化。
- 后续修正：0.4.1 将 Collection `hide_render` 和 LayerCollection `exclude` 也纳入快照/恢复，被隐藏或排除的配对灯组不再被拒绝。
- 结论：采用。

## 反打洞审查

- 不在 Panel 回调中直接改 `hide_render` 或 `Scene.world`。
- 不用显示名字作为唯一身份；计划冻结本地/链接库键。
- 不建第二条渲染循环；环境切换仍经 Coordinator → RenderAdapter。
- 辅助 Scene 仍由 Adapter 清理，最终由 Transaction 恢复宿主状态。

## 里程碑与验收

### M1：配对模型与 Scene 边界

- 新增纯 Python 环境 DTO，RenderPlan 可按 Camera key 查到冻结环境。
- 收集嵌套 Collection 内 Light，重复 Camera 配对被拒绝，空字段继承场景。

### M2：渲染切换与完整恢复

- Beauty 受配对 Light/World 影响；Alpha 使用同一 Camera 状态；Object ID 保持环境无关。
- 同 Camera 多通道重复准备不累积副作用，切换 Camera 后正确套用下一组。
- 成功、失败、取消、load/unregister 均恢复 World 和 Light 可见性。

### M3：UI、清单、文档与验证

- 两个面板共用配对列表，可增删并选 Camera、Collection、World。
- RenderInfo 每个 Camera 记录环境名称与 Light 数量，以可选字段扩展 schema 2。
- 更新产品基线、实现现状、边界登记、README/CHANGELOG 和测试说明。

## 验证矩阵

- 纯 Python：DTO 查询、空配对、稳定键和现有输出路径不变。
- 架构：Domain/Application 不引入 `bpy`；Presentation 不实现隔离规则。
- Blender 后台：两 Camera、两组灯、两个 World；证明每 Camera 使用正确组合；未配对 Camera 沿用默认。
- GUI：配对增删/选择可用，模态批次不停顿，取消后可再次启动。
- 失败/恢复：配对数据块消失、单项失败、取消、异常和卸载。
- 性能/兼容：Light 列表只在 session 建立时冻结；不使用 Blender 4.0.2 之后才有的 API。

## 幂等、失败恢复与回滚

- 每次 prepare 都从任务开始的 Light 基线重算目标状态，不依赖上个 Camera 留下的值。
- 环境应用失败则当前 action 失败，Transaction 最终恢复所有已捕获状态。
- 配对 PropertyGroup 保存在 `.blend` 中，插件不会自动保存文件。
- 代码回滚可恢复 0.3.0 路径；输出图和 `.blend` 不自动迁移或删除。

## 进度

- [x] M1 配对模型与 Scene 边界
- [x] M2 渲染切换与完整恢复
- [x] M3 UI、清单、文档与验证
- [x] 完成复盘并转为 COMPLETED

## 发现与决策

- 同 Camera 配多套环境会让现有稳定输出名互相覆盖，本版因此明确“一个 Camera 最多一套环境”。
- `Object.hide_render` 能隔离 Light 而不误伤同 Collection 内模型，比切换整个 Collection/View Layer 更符合功能边界。
- Alpha 由 source Scene 浅拷贝时，必须先应用 Camera 环境，才能和 Beauty 使用同一可见性状态。

## 结果复盘

- 面板已支持 Camera + Light Collection + World 增删和指针选择，空 Light/World 保持 Scene 默认，重复 Camera 和无效 Collection 会在任务开始前拒绝。
- 计划冻结嵌套 Collection 中的 Light 稳定键，渲染 Adapter 通过统一状态事务按 Camera 切换；未配对 Camera 会先恢复任务基线。
- RenderInfo schema 2 添加可选 `environment`、`light_collection`、`light_count` 和 `world`，现有文件名和覆盖/保留语义不变。
- 21 个纯 Python 单测、5 个架构门禁和 Ruff 通过；Blender 5.2.1 后台全通道与 GUI 模态/取消测试通过，已覆盖配对切换、未配对回基线、成功/取消/失败恢复。
- 0.4.0 Extension 清单验证、Extension/Legacy 双包构建和 Legacy 隔离安装通过。Extension SHA-256：`C141DB0BC89726297E499C4A7DD6A846042A2574C8AB700E8F913857421CD58F`；Legacy SHA-256：`0B937A75D2F6DCB4625B107A6949A8ACE80A86C284FCA4928EAF1273B5B38F19`。
- 0.4.1 缺陷回归补充了被排除/隐藏 Collection 的自动启用与恢复，以及面板配对行的 Camera/Light/World 即时预览。
