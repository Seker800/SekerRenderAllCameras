# 空列表回退与预览灯组保留

- 状态：COMPLETED
- 日期：2026-11-06
- 目标版本：0.9.1
- 入口：`presentation.panel`、`blender.scene_reader`、`blender.environment`、`blender.state_transaction`
- 目标 Blender：4.0.2 最低；继续构建五目标包
- 权威来源：`PLAN.md`、`Docs/architecture/系统总览.md`、`Docs/reference/实现现状.md`
- 前置依赖：0.9.0 的 All Cameras 范围选项与 Camera Environments 配对

## 用户可观察结果

1. 关闭 **All Cameras** 且 **Camera Environments** 列表为空时，不再报错；使用场景当前灯光/World，渲染当前 Scene 全部相机。
2. 在 Camera Environments 列表中选择一台已配置相机时，仍切换该相机、World 和选中灯组，但**不再隐藏或禁用其他未选择的灯组 Collection**；其他集合的视口/渲染可见性保持点击前状态。
3. 渲染阶段仍按现有语义隔离已登记灯组：渲染某台配对相机时只启用其灯组，其他已登记灯组隐藏；预览和渲染的差异在文档中明确。
4. `RenderInfo.all_cameras` 记录实际范围；空列表回退时记录 `true`。

## 范围

### 包含

- 删除 `validate_scene` 中“All Cameras 关闭且无配对即拒绝”的预检。
- `build_render_plan` 在配对 Camera 集合为空时回退到全部 Camera，并冻结实际范围。
- 面板在 All Cameras 关闭且列表为空时显示回退提示，而不是错误提示。
- `switch_light_collections` 新增 `hide_others` 开关；预览传 `False`，渲染保持 `True`。
- 单元、Blender 后台、安装态、发布契约和文档同步。

### 非目标

- 不改变渲染阶段的灯组隔离、状态快照和恢复。
- 不改变 Camera Environments 的配对、World 切换或输出命名。
- 不新增“当前选中相机”等其他范围模式。
- 不改变空场景、无 Camera、未保存文件等既有预检。

## 方案比较

- 方案 A（采用）：预览调用 `switch_light_collections(..., hide_others=False)`，渲染调用默认 `True`；空列表在 `build_render_plan` 中回退全部 Camera。
  - 优点：一个集合切换边界，两类调用显式区分；空列表回退与实际 Camera 选择同处 `scene_reader`。
  - 代价：`switch_light_collections` 多一个布尔参数，需补预览/渲染回归测试。
- 方案 B（拒绝）：预览完全不调用灯组切换。
  - 缺点：选中的灯组若原本隐藏/排除，预览不会显示，用户仍要手动打开；不符合“切换选中灯组但不隐藏其他”的预期。
- 方案 C（拒绝）：渲染也传 `hide_others=False`。
  - 缺点：会破坏 Camera Environments 的渲染隔离语义，多个灯组互相污染。

## 边界审查

- 预览只通过 `preview_environment` 修改选中集合根；其他集合不做任何写入，不依赖 `bpy.context` 全局状态。
- 渲染仍通过 `state_transaction.apply_environment` → `switch_light_collections(hide_others=True)`，状态快照和恢复不变。
- 空列表回退不新增全局变量；实际范围进入 `RenderPlan.all_cameras`。
- 不新增临时 Operator；面板提示只读。

## 验证

- 单元：预览不改变其他集合 `hide_render/hide_viewport`，选中集合启用；`hide_others=True` 的渲染行为不变。
- Blender 4.0.2：空列表回退 2 台 Camera、RenderInfo `all_cameras=true`；预览两台配对相机后其他灯组保持可见；渲染仍隔离。
- 安装态：4.0.2 Legacy 与 4.2 Extension 演示通过。
- 打包：五包构建、`release_gate --packages-only`、`--prerelease`。

## 回滚与文档

- 回滚只需恢复预览的 `hide_others=True` 和空列表预检；渲染路径不受影响。
- 更新 README、camera README、changelog、reference、PLAN、architecture 和 review 记录。
- 完成后改为 `COMPLETED-空列表回退与预览灯组保留.md` 并更新索引。

## 结果

- 空列表回退到全部相机并在 RenderInfo 记录实际范围；预览只启用选中灯组，其他集合可见性不变。
- 单元 68/68、架构 7/7、Ruff、4.0.2 集成测试和环境配对验收通过；4.0.2 Legacy 与 4.2 Extension 安装态通过。
- 五包构建、`release_gate --packages-only`、`release_gate --prerelease` 通过；安装包位于 `D:\Blender插件\RenderAllCameras插件更新`。
- 未覆盖：4.5/5.2 本机安装验证和完整五目标 GUI 发布套件。
