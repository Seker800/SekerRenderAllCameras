# 预览仅切换相机与 World

- 状态：COMPLETED
- 日期：2026-11-06
- 目标版本：0.9.2
- 入口：`blender.environment.preview_environment`、`presentation.properties._preview_pair`
- 目标 Blender：4.0.2 最低；继续构建五目标包
- 权威来源：`PLAN.md`、`Docs/architecture/API边界.md`、`Docs/reference/实现现状.md`
- 前置依赖：0.9.1 的预览不隐藏其他灯组行为

## 用户可观察结果

1. 在 Camera Environments 列表中点击/修改已配置相机时，只切换当前相机和 World。
2. 插件不再改动任何灯组 Collection 的 `hide_render`、`hide_viewport` 或 LayerCollection `exclude`，因此不会因为点击列表而把灯光集合中的其他集合排除。
3. 正式渲染仍按配对隔离已登记灯组，状态事务和恢复不变。

## 范围

### 包含

- `preview_environment` 移除灯组参数和 `switch_light_collections` 调用。
- `properties._preview_pair` 只传 Camera 和 World。
- `switch_light_collections` 移除 0.9.1 的 `hide_others` 参数，恢复为仅渲染使用。
- 单元、Blender 后台、集合显隐专项、安装态和文档同步。

### 非目标

- 不改变渲染阶段的灯组隔离、集合显隐事务和恢复。
- 不改变 Camera Environments 配对字段、World 预览或输出命名。
- 不改变 All Cameras 范围和空列表回退。

## 方案比较

- 方案 A（采用）：预览只设置 `scene.camera` 和 `scene.world`，不触碰任何 Collection。
  - 优点：点击列表不可能改变集合排除状态；渲染路径保持单一隔离入口。
- 方案 B（拒绝）：预览启用选中灯组但保存/恢复其他集合。
  - 缺点：仍会改变 LayerCollection `exclude`，Blender 可能重建对象 Base 或产生其他集合被排除的副作用，无法满足“不因点击导致排除”。

## 边界审查

- 预览只经 `preview_environment` 修改 Camera/World，不通过 `bpy.context` 或对象名称隐式发现 Collection。
- 渲染仍经 `state_transaction.apply_environment` → `switch_light_collections`，默认隔离行为不变。
- 不新增全局状态、临时 Operator 或第二条预览路径。

## 验证

- 单元：预览前后所有 Collection `hide_render/hide_viewport` 和 LayerCollection `exclude` 完全不变；Camera/World 切换生效。
- Blender 4.0.2：列表点击后其他集合（包括选中集合）保持原状态；渲染仍隔离并恢复。
- 集合显隐专项 `run_collection_visibility_tests.py`。
- 安装态、五包构建与 `release_gate`。

## 回滚与文档

- 回滚只需在预览中恢复灯组调用；渲染路径不受影响。
- 更新 README、camera README、changelog、reference、PLAN、architecture、测试矩阵和 review。
- 完成后改为 `COMPLETED-预览仅切换相机与World.md` 并更新索引。

## 结果

- `preview_environment` 只设置 Camera/World；单元和 4.0.2 实机测试确认所有集合显隐/排除状态不变。
- 渲染隔离、空列表回退、状态恢复、五包构建、4.0.2 Legacy 与 4.2 Extension 安装态通过。
- 安装包位于 `D:\Blender插件\RenderAllCameras插件更新`，SHA-256 见 review 记录。
- 未覆盖：4.5/5.2 本机安装验证和完整五目标 GUI 发布套件。
