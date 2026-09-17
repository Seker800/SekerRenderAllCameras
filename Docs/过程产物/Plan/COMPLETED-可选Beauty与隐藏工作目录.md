# 可选 Beauty 与隐藏工作目录实施计划

- 状态：COMPLETED
- 日期：2026-09-16
- 目标版本：0.7.0
- 入口：通道选择 UI、Scene 预检与 RenderPlan、Alpha Adapter、输出目录分配、全量测试和用户文档
- 权威来源：本计划、`PLAN.md`、`Docs/architecture/`、`camera_batch_renderer.domain.Channel`、`camera_batch_renderer.infrastructure.storage`
- 前置依赖：五个受支持 Blender 测试环境和 0.6.0 全量测试基线
- 阻塞：无；任一目标版本出现单通道失败、状态泄漏或工作目录泄漏即停止发布

## 用户可观察结果

- Beauty、Alpha、Object ID、Material ID 在面板中并列选择；默认只勾选 Beauty，保持升级后的首次体验不变。
- 用户可以只渲染 Alpha、只渲染 Object ID、只渲染 Material ID，或选择任意组合。
- 四项都未选择时不启动任务，并显示明确错误，不创建输出目录或运行标记。
- 输出目录外层只出现最终图片和正式 JSON；staging、运行状态标记和原子写入临时文件进入一个固定隐藏工作目录，成功后整体删除。
- 取消、失败或异常时不在外层散落临时文件；隐藏工作目录只保留可诊断的未完成状态，并在下一次任务开始时安全复用/清理。

## 范围、非目标与不可变边界

- 范围：通道选择、无通道预检、Alpha-only、固定工作目录、Windows 隐藏属性、相关测试、截图和文档。
- 非目标：删除 RenderInfo/ObjectID/MaterialID 正式说明文件、改变图片命名、改变固定输出目录、合并 manifest schema、改变旧图保留语义。
- 默认 Beauty 为开；现有用户不操作复选框时仍得到 Beauty。
- 插件仍不保存 `.blend`，不永久改变 Camera、帧、渲染器、Film、色彩管理、World、灯光、对象、材质或节点状态。
- 每个 Blender 版本仍使用独立包；公共 Domain/Application 不判断 Blender 版本。

## 当前实现、所有权与公开契约

- `RAC_Settings` 只有三个附加通道布尔值；`scene_reader.build_render_plan` 无条件加入 `Channel.BEAUTY`。
- `BlenderRenderAdapter` 在 Film Transparent 开启时从前一个 Beauty 文件提取 Alpha，因此 Alpha-only 需要在没有本批 Beauty 时回退到隔离 `AlphaScene`。
- `RenderPlan.channels` 是本次冻结通道的唯一真相源；UI 只传递四个布尔意图，Scene Reader 负责验证非空并冻结顺序。
- `BatchCoordinator` 继续拥有动作顺序和结果；不新增第二个任务状态机。
- `infrastructure.storage.OutputAllocation` 继续拥有输出与工作路径；Adapter 只接收明确的 staging 路径。
- 正式 JSON 是可观察结果而非临时文件，继续由 `ManifestWriter` 写入输出根目录。

## 方案比较与决策

### 通道方案 A：始终暗中渲染 Beauty，但不保存

- 优点：Alpha 复用路径改动少。
- 缺点：用户选择“只渲染 ID”仍支付 Beauty 成本，进度与实际行为不一致。
- 结论：拒绝。

### 通道方案 B：Beauty 成为真实可选通道

- 优点：计划、进度、耗时和用户选择一致；ID-only 不做无关渲染。
- 缺点：Alpha-only 需要独立宿主路径。
- 结论：采用；有本批 Beauty 且可复用时提取 Alpha，否则使用隔离 Alpha Scene。

### 临时文件方案 A：系统临时目录

- 优点：用户输出目录最干净。
- 缺点：可能跨卷，无法保证图片 `os.replace` 的同卷原子性，崩溃证据也难定位。
- 结论：拒绝。

### 临时文件方案 B：输出目录内固定隐藏工作目录

- 优点：同卷原子替换、只有一个工作入口、成功后可整体清理、失败可诊断。
- 缺点：显示隐藏文件时仍可看到该目录。
- 结论：采用；目录使用点前缀，并在 Windows 设置 Hidden 属性。

## 反打洞审查

- 不在 Panel 复制通道排序或无通道规则；规则只在 Scene Reader 冻结。
- 不用全局变量保存通道选择或工作目录；全部进入 `RenderPlan` / `OutputAllocation`。
- 不通过临时 Operator 生成 Alpha；复用现有 `BlenderRenderAdapter` 与 `AlphaScene`。
- 不让各通道自行创建临时目录；工作路径由 Storage/组合根一次分配。
- 不为五个 Blender 复制实现；按现有目标装配和五版本测试验证。

## 里程碑与验收

### M1：纯规则与存储边界

- 路径：`scene_reader.py`、`storage.py`、`manifest.py`、单元测试。
- 结果：任意非空通道组合按固定顺序冻结；空选择失败且不分配输出；固定隐藏工作目录承载 staging、marker 和 JSON 临时文件。
- 停止条件：需要跨卷移动、删除输出根目录或改变旧图保留契约。

### M2：UI 与 Alpha-only 宿主路径

- 路径：`properties.py`、`panel.py`、`operators.py`、`render_adapter.py`。
- 结果：四通道并列、Beauty 默认开启；Alpha-only 在 Film Transparent 开/关下均生成有效 PNG。
- 停止条件：需要隐式 Beauty、第二套 Coordinator 或无法恢复 Blender 状态。

### M3：五版本回归与文档

- 路径：Blender/GUI/安装态脚本、README、PLAN、reference、changelog、真实截图。
- 结果：五版本覆盖 Beauty-only、Alpha-only、Object-only、Material-only、全选、空选择、取消/失败和工作目录清理。
- 停止条件：任一发布必测项 failed/not_run。

## 验证矩阵

- 纯 Python：四通道组合、空选择、默认值契约、固定工作路径、成功/失败 marker、原子 JSON 临时目录。
- Blender 后台：四个单通道、全通道、Film Transparent 两种 Alpha-only、旧文件保留。
- GUI：四个复选框、空选择错误、只选 ID 后动作数/输出正确、取消后隐藏工作目录状态。
- 失败/取消：准备失败不创建外层 marker；渲染失败、取消、异常后无外层 staging/tmp 文件。
- 状态恢复：沿用并重跑 Camera/Film/输出/环境/临时数据块恢复断言。
- 兼容：4.0.2、4.1.1、4.2.0、4.5.13、5.2.1 分版本测试；一个版本不能替代另一个版本。
- 性能：ID-only 不执行 Beauty；动作数严格等于 Camera 数 × 已选通道数。

## 幂等、失败恢复、回滚和文档影响

- 工作目录固定且只属于本插件；下一批开始前清理它的 staging 子目录，不触碰最终图片和无关文件。
- 成功删除整个工作目录；取消/失败保留一个隐藏的 incomplete 状态，下一次任务会替换。
- 回滚可恢复 Beauty 强制选择与旧 staging 位置，不需要迁移 `.blend` 数据；新增 Beauty 布尔属性缺失时使用默认 true。
- 更新 `PLAN.md`、架构事务规则、实现现状、README、插件 README、测试范围、changelog 和真实面板截图。

## 进度

- [x] 研究当前通道计划、Alpha 依赖、Storage/Manifest 与 UI
- [x] 完成方案比较、边界和验证计划
- [x] M1 纯规则与隐藏工作目录
- [x] M2 UI 与四个单通道宿主路径
- [x] M3 五版本回归、截图与文档闭环

## 发现与决策

- 用户所说“临时文件”按运行期 staging/marker/tmp 处理；三个 JSON 是正式说明文件，本次不删除或合并，避免破坏 ID 图片的颜色解释与旧图保留契约。
- Alpha-only 不能依赖磁盘上可能存在的旧 Beauty；只允许复用本次批次刚完成的 Beauty，否则必须独立渲染。

## 结果复盘

- Beauty 已成为默认开启但可取消的真实通道；四通道可任意非空组合，空选择在分配输出前失败。Alpha-only 在 Film Transparent 开/关下均通过真实图片测试，且不会复用历史 Beauty。
- staging、运行标记和 JSON 原子临时文件已统一进入 `.render-all-cameras-work/`；成功后目录被删除，取消/失败后外层无散落文件且只在隐藏目录保留 `.incomplete`。
- 完整开发门禁报告：`build/test-reports/20260916-131543-20060/summary.json`。Blender 4.0.2、4.1.1、4.2.0、4.5.13、5.2.1 共 63 项通过、0 失败、0 未执行，包含源码态、GUI、压力、五个 0.7.0 分版本包安装态与跨版本一致性。
- 新面板截图由实际安装的 `camera_batch_renderer-0.7.0-blender-5.2-lts.zip` 生成并写入 `Docs/images/plugin-quick-start.jpg`。
- 0.7.0 仍是未发布源码；主页下载链接继续指向已发布且已验证的 0.6.0，待正式 Release 后再切换链接并执行线上哈希回读。
