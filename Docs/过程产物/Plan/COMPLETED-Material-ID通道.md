# Material ID 通道实施计划

## 元数据

- 状态：`COMPLETED`
- 日期：2026-09-16
- 目标版本：0.5.0
- 用户入口：`3D Viewport → N → Batch Render` 与 `Output Properties → Render All Cameras`
- 权威来源：根 `PLAN.md`、`Docs/architecture/`、本计划；落地事实完成后回写 `Docs/reference/实现现状.md`
- 目标 Blender：最低 4.0.2；开发与真实验收使用 Blender 5.2.1 LTS
- 前置依赖：现有 `Channel`、`BatchCoordinator`、`BlenderRenderAdapter`、临时辅助 Scene、稳定调色板、原子输出与统一清理路径
- 阻塞：无

## 用户可观察结果

- UI 新增 `Render Material ID` 开关。
- 勾选后，每台摄影机额外输出 `{Blend}_{Camera}_MaterialID_{宽}x{高}_Material.png`。
- 同一个 Blender Material 在不同对象、摄影机和重复运行中保持同一颜色；不同 Material 使用不同的非黑色纯色。
- 同一网格的不同材质面在一张 Material ID 图中显示不同颜色。
- 黑色只表示背景；没有分配材质的表面使用一个明确的非黑色 `Unassigned` 标签。
- 输出目录新增 `{Blend}_MaterialID.json`，记录材质稳定键、显示名、RGB 与十六进制颜色及跳过项。
- 新图成功后覆盖同名旧图；未生成的旧图保留。取消或失败不得破坏旧图。

## 范围与非目标

### 范围

- Domain 通道枚举、命名、任务冻结输入与进度计算。
- Blender 临时 Material ID Scene、材质槽/多边形索引保留、纯色 Workbench 渲染与清理。
- UI、RenderInfo、MaterialID JSON、后台与 GUI 测试、文档和版本号。

### 非目标

- 不实现 Cryptomatte Material、节点级材质分层、材质实例 UUID 或跨重命名永久身份。
- 不把纹理、Base Color、透明度或材质节点结果烘焙进 ID 图。
- 不修改、保存或写入用户 Material、Object、Scene 或 `.blend`。
- Volume 材质仍不纳入辅助 ID 渲染。

## 当前实现与所有权

- `domain.models.Channel` 是通道身份真相源。
- `domain.naming.output_filename` 是输出命名真相源。
- `application.BatchCoordinator` 是动作顺序、进度、取消和结果真相源。
- `blender.scene_reader.build_render_plan` 冻结用户开关与通道列表。
- `blender.render_adapter.BlenderRenderAdapter` 是 Beauty/Alpha/Object ID/Material ID 的唯一调度边界。
- `blender.auxiliary` 拥有临时辅助 Scene 和宿主数据块清理。
- `infrastructure.AtomicJsonWriter` 负责 MaterialID JSON 原子写入。
- Presentation 只收集 `include_material_id` 意图，不持有材质映射规则。

依赖方向保持 `Presentation → Blender 组合根/Adapter → Application/Domain → Infrastructure`；Domain 不导入 `bpy`。

## 方案比较与决策

### 方案 A：临时 Workbench Scene，按 Material 数据块替换临时材质

- 从 evaluated depsgraph 生成临时 Mesh，保留每个 polygon 的 `material_index`。
- 收集材质稳定键，复用确定性调色板；为每个键创建仅存在于内存的临时 Material，并按原槽位重建临时 Mesh 的材质表。
- Workbench 使用 `MATERIAL` 颜色、Flat 光照、黑色背景和关闭抗锯齿，沿用 Object ID 的精确 PNG 校准路径。
- 优点：不触碰用户材质；一个网格可输出多个材质；与现有辅助 Scene、清理和兼容路径一致。
- 代价：每次 Material ID 都需要复制 evaluated Mesh，内存和时间与 Object ID 相近。

### 方案 B：临时改写用户材质节点或 View Layer override

- 优点：可能少复制网格。
- 缺点：会修改用户 Material/节点或依赖上下文 override；共享材质、链接库、失败恢复和多引擎兼容风险高；违反统一临时数据和宿主隔离边界。

### 决策

采用方案 A。复用唯一 `BlenderRenderAdapter` 和辅助 Scene 清理路径，不建立第二套 Operator、全局任务状态或输出配置。

## 反打洞审查

- `bpy.context`：只在 Blender Adapter 获取 depsgraph/执行渲染，不进入 Domain 或命名规则。
- 全局状态：不新增 module-level 可变映射；颜色与临时数据由当前 `MaterialIdScene`/Session 拥有。
- 重复配置：抽取或复用 Object ID 的 Workbench 配置、颜色校准和候选对象规则。
- 临时 Operator：不新增；继续由现有批次 Operator 和 Coordinator 调度。
- 第二适配路径：不新增；Material ID 进入现有 `BlenderRenderAdapter.prepare/finalize_output` 分支。

## 临时状态、恢复与失败语义

- 不修改用户对象、材质、节点、颜色、引擎或 Scene；只创建独立临时 Scene、Camera、Mesh、Object 和 Material 数据块。
- 所有临时数据块进入统一 `cleanup_auxiliary()`，在成功、单项失败、取消、批次失败、load/unregister 和 `finish()` 中清理。
- 图片先写输出目录内 `.staging-*`，成功后 `os.replace`；失败/取消保留旧正式图。
- MaterialID JSON 使用原子写入；只有至少一个 Material ID 成功时更新。
- 强制关闭 Blender 时临时数据未保存到用户 `.blend`；插件不自动保存文件。

## 里程碑与停止条件

### M1：纯规则与公开契约

- 路径：`domain/models.py`、`domain/naming.py`、`application/job.py`、单元测试。
- 结果：`MaterialID` 进入通道顺序和确定命名，纯 Python 测试通过。
- 停止条件：命名或通道枚举仍需 Blender 才能测试。

### M2：Blender 宿主适配

- 路径：`blender/auxiliary.py`、`render_adapter.py`、`scene_reader.py`、`runtime.py`。
- 结果：多材质网格真实导出至少两种声明颜色，背景为黑色，MaterialID JSON 与像素一致，临时数据完全清理。
- 停止条件：任何用户 Material/Scene 状态被修改或临时数据残留。

### M3：UI、GUI 与恢复闭环

- 路径：`presentation/properties.py`、`panel.py`、`operators.py`、GUI/后台脚本。
- 结果：开关可用；多摄影机连续完成；取消、单项失败与批次失败保持旧文件并清理；进度分母正确。
- 停止条件：第一张后停止、取消语义变化或其他通道回归。

### M4：兼容、文档与打包

- 路径：版本清单、README、PLAN、architecture/reference/changelog、构建包。
- 结果：Blender 5.2.1 真实验收、最低版本可执行验证、Extension/Legacy 构建完成。
- 停止条件：包内版本不一致或首页宣称未验证能力。

## 验证矩阵

- 纯 Python：Channel、命名、Coordinator 动作数、调色板确定性与非黑色。
- Blender 后台：Beauty/Alpha/Object ID/Material ID 双摄影机真实渲染；一个 Mesh 至少两个材质面；逐像素只含黑色和清单颜色。
- GUI：三摄影机异步队列含 Material ID，不在第一张/第一通道后停止；取消在当前图片后结束。
- 失败/取消：注入失败、协作式取消、旧文件保留、`.incomplete` 和 RenderInfo 状态正确。
- 状态恢复：Camera、World、Light、Collection、LayerCollection、filepath、film、对象颜色和用户 Material 不变；无 `RAC_*` 临时 Scene/Object/Mesh/Material 残留。
- 性能：辅助通道按单台摄影机创建和清理临时数据，不跨整批缓存 evaluated Mesh。
- 兼容：开发门禁 Blender 5.2.1；执行既有 4.0.2/4.1/4.2/4.5 兼容入口或至少完成 API 静态审查与双包验证。

## 幂等、回滚和文档影响

- 重复运行生成相同材质键、颜色、文件名与 JSON；正式输出只在成功后替换。
- 回滚可移除 `MaterialID` 通道、UI 属性和辅助类，不影响 Beauty/Alpha/Object ID 文件契约。
- 更新 `PLAN.md`、README、架构模块登记/API/命名、实现现状、功能日志、脚本说明和计划索引。

## 进度、发现、决策与复盘

- [x] 研究现有通道、辅助 Scene、调色板、原子输出与测试入口。
- [x] 选择临时 Workbench Material Scene 方案。
- [x] M1 纯规则。
- [x] M2 Blender 适配。
- [x] M3 UI 与完整验证。
- [x] M4 文档、版本与构建。

发现：现有 Object ID 已提供确定性颜色、精确 PNG 校准、evaluated Mesh/实例复制与临时数据清理，可复用其边界但不能把“物体键”和“材质键”混为同一份运行状态。

结果复盘：0.5.0 已完成。23 个单元测试、5 个架构测试和 Ruff 通过；Blender 5.2.1 后台完成双摄影机 × Beauty/Alpha/Object ID/Material ID 共 8 个动作，GUI 完成三摄影机 × Beauty/Material ID 共 6 个动作并通过取消回归。独立验收图包含黑色背景、`Body Red`、`Top Blue` 与 `Unassigned` 三个精确标签，PNG 像素与 MaterialID JSON 一致，用户材质槽、面索引和材质颜色不变。Extension/Legacy 双包构建成功，Extension 覆盖安装后演示 `.blend` 的 8 个输出与两份 ID JSON 全部通过。当前机器只有 Blender 5.2.1；最低版本继续由 Python 3.10/清单架构门禁和 Legacy 隔离安装验证覆盖，未虚构 4.0.2 实机结果。最终文件名为 `{Blend}_{Camera}_MaterialID_{宽}x{高}_Material.png` 与 `{Blend}_MaterialID.json`；Volume 材质仍为已知限制。
