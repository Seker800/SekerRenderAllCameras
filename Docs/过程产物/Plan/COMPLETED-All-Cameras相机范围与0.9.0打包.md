# All Cameras 相机范围与 0.9.0 打包

- 状态：COMPLETED
- 日期：2026-11-06
- 目标版本：0.9.0
- 入口：`presentation.properties`、`presentation.panel`、`blender.scene_reader`、`blender.runtime`、`RenderInfo`
- 目标 Blender：4.0.2 最低；继续构建 4.0.2、4.1.1、4.2.0、4.5 LTS、5.2 LTS 五个包
- 权威来源：`PLAN.md`、`Docs/architecture/系统总览.md`、`Docs/reference/实现现状.md`
- 前置依赖：0.8.0 工作区源码；现有 Camera Environments 配对、状态事务和 RenderInfo schema 2

## 用户可观察结果

- 插件面板新增 **All Cameras** 复选框，默认勾选；勾选时行为与 0.8.0 完全一致，渲染当前 Scene 全部 Camera。
- 取消勾选时，只渲染 `Camera Environments` 列表中已指定 Camera 的对象；列表中没有 Camera 时在预检阶段拒绝，不创建隐藏工作目录或任何图片。
- 配对行指定 Camera 但 Light Collection / World 都留空时，仍视为选中该 Camera，使用批次开始时的 Scene 环境。
- 同一 Camera 在列表中出现多次且都带环境时继续按现有规则拒绝；重复的空环境行按一次选择处理。
- `RenderInfo.json` 记录 `all_cameras`，便于确认本次范围。

## 范围

### 包含

- `Scene.rac_settings.include_all_cameras` 布尔属性与两个面板的共享绘制入口。
- `validate_scene`、`build_render_plan`、`create_session`、`run_batch_sync` 的显式参数，默认 `True` 保持兼容。
- Camera 选择规则集中在 `blender.scene_reader`；不新增第二条 Camera 发现路径。
- 预检错误、RenderInfo 字段、面板运行中禁用、提示文字。
- 0.9.0 版本面、更新日志、参考文档、发布契约、测试与五包构建。

### 非目标

- 不改变 Camera Environments 的灯光/World 切换、恢复和预览语义。
- 不新增“当前选中 Camera”“指定集合”等其他范围模式。
- 不改变文件名、输出目录、覆盖/保留、通道、Alpha/ID 规则。
- 不改变 GUI 调度、诊断、取消和失败语义。
- 不发布 GitHub Release；只生成本地安装包。

## 当前实现与责任

- `presentation.properties.RAC_Settings`：设置唯一来源；新增属性为普通 BoolProperty，默认 `True`。
- `presentation.panel.draw_controls`：两个面板共用的只读绘制入口；新增复选框和范围提示，运行中由现有 `session is None` 禁用。
- `blender.scene_reader`：拥有 Scene Camera 发现、配对校验和 RenderPlan 生成；在此集中过滤，避免 UI/Operator 复制规则。
- `blender.runtime`：只传递设置并写入 RenderInfo；不拥有选择规则。
- `application`/`domain`：RenderPlan 新增只读 `all_cameras` 快照；核心仍不依赖 `bpy`。
- 依赖方向保持 Presentation → Application → Domain，Blender Adapter 只负责宿主读取。

## 方案比较

- 方案 A（采用）：给 `validate_scene/build_render_plan/create_session/run_batch_sync` 增加 `include_all_cameras` 与 `environment_pairs` 参数，在 `scene_reader` 内统一选择 Camera。
  - 优点：唯一 Camera 发现路径；预检和计划一致；UI 只收集意图。
  - 代价：四个公开函数签名扩展，需更新调用点和测试。
- 方案 B（拒绝）：在 Operator 中先把 Camera 列表过滤后再传给 runtime。
  - 缺点：Operator 复制 Camera 发现与配对校验，绕过 `scene_reader` 的既有错误和排序规则；未来同步入口会分叉。
- 方案 C（拒绝）：新增全局 Camera 选择状态或临时 Operator。
  - 缺点：违反“Scene 设置唯一来源”和 `bpy.context` 反打洞约束。

## 边界审查

- 不通过 `bpy.context` 发现 Camera；继续使用传入的 `scene` 与 `scene.objects`。
- 不新增全局变量；批处理范围冻结在 `RenderPlan.all_cameras`。
- 不新增临时 Operator；复用现有 `render.render_all_cameras`。
- 不修改 `scene.camera` 的持久值来筛选；只按计划生成动作。
- 配对 Camera 不在当前 Scene、重复环境配对仍由现有 `_environment_specs` 拒绝。
- 关闭 All Cameras 且无有效配对时，在 `prepare_output_directory` 之前抛 `ValueError`。

## 里程碑

1. 纯规则/计划：`RenderPlan.all_cameras`、`scene_reader` 过滤、预检错误。
2. 运行时：`create_session`/`run_batch_sync` 参数、Operator 传值、RenderInfo 字段。
3. UI：属性、共享面板绘制、运行中禁用、无配对提示。
4. 契约与测试：release contract、`run_blender_tests.py`、`run_installed_demo.py`、单元/架构测试。
5. 版本与文档：0.9.0、README、changelog、reference、PLAN/architecture 同步。
6. 打包：五目标 ZIP，4.0.2 Legacy 安装验收，`release_gate --packages-only`，复制到指定目录。

## 验证

- 纯 Python：`python -m unittest discover -s tests/unit -v`、`tests/architecture`。
- Blender 4.0.2 后台：`scripts/run_blender_tests.py`；新增默认全量、关闭后单机、空配对拒绝、无环境配对仍选中、RenderInfo 字段、状态恢复。
- 安装态：用 4.0.2 Legacy ZIP 在隔离 `BLENDER_USER_SCRIPTS` 中安装并运行 `scripts/run_installed_demo.py`。
- GUI：至少确认两个面板绘制 All Cameras；4.0.2 有窗口时做一次关闭复选框的单相机试跑，若环境不允许则记录未执行。
- 打包：五包构建、`release_gate --packages-only`、ZIP 内容/名称/版本检查、4.0.2 安装包实测。
- 失败/取消/恢复：关闭范围后的空列表、配对校验失败均不得创建隐藏工作目录或任何图片；成功/失败后 Camera、World、集合和文件路径恢复不变。

## 回滚与文档

- 若新范围行为失败，设置默认 `True` 可保持 0.8.0 行为；代码回滚只需移除参数和属性。
- 更新 `README.md`、`camera_batch_renderer/README.md`、`Docs/reference/实现现状.md`、`Docs/changelogs/功能更新日志.md`、`PLAN.md`、`Docs/architecture/系统总览.md` 和发布契约。
- 完成后把本计划改为 `COMPLETED-All-Cameras相机范围与0.9.0打包.md` 并更新索引。

## 结果

- 0.9.0 源码、UI、RenderPlan、Runtime、RenderInfo、发布契约和文档已同步。
- 单元 68/68、架构 7/7、Ruff、Blender 4.0.2 集成测试通过；4.0.2 Legacy 安装态和 4.2.22 上的 4.2.0 Extension 安装态完成四通道 + All Cameras 范围验收。
- 五包构建与 `release_gate --packages-only`、`release_gate --prerelease` 通过；安装包已复制到 `D:\Blender插件\RenderAllCameras插件更新`，SHA-256 记录在 `Docs/过程产物/review/COMPLETED-0.9.0-All-Cameras验证.md`。
- 未覆盖：4.5.13/5.2.1 本机安装验证和完整五目标 GUI 发布套件；0.8.0 已知原生限制继续保留。
