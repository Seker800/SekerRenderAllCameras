# API 边界

## 核心公开面

- 命令表达请求：开始任务、请求取消、打开输出目录。
- 查询返回只读快照：预检结果、任务进度、完成摘要。
- 事件表达已发生事实：摄影机开始/完成、通道失败、任务结束。
- DTO 只包含 Python 基础类型、枚举、`pathlib.Path` 可序列化表达或项目值对象；不把 `bpy.types.*` 暴露给 Domain。

## Blender-facing 边界

- `BlenderSceneReader` 读取并冻结 Scene、帧、Camera、每机 Light Collection/World 与渲染参数。
- `BlenderRenderAdapter` 按冻结计划设置目标摄影机和环境，并执行渲染。
- `BlenderAlphaAdapter` 从当前 Render Result 提取 Alpha，不拥有 Beauty 调度。
- `BlenderObjectIdAdapter` 临时配置 ID 渲染并把所有修改登记到状态事务。
- `MaterialIdScene` 在隔离的临时 Workbench Scene 中保留 evaluated Mesh 的逐面材质索引，以稳定材质颜色输出 PNG；不修改用户 Material 或材质槽。
- `BlenderStateTransaction` 捕获、应用并恢复 Camera、World、Light、Collection `hide_render` 与 LayerCollection `exclude` 等宿主状态。
- `blender.environment.preview_environment` 是 Presentation 选中配对后预览 Camera/Light/World 的唯一宿主边界；Property update 只转发意图。

这些名称是架构契约；若实现采用 Protocol/ABC 或不同具体类名，应在 `Docs/reference/实现现状.md` 建立一一映射。

## 兼容策略

- 最低 Blender 版本确定前，不以猜测兼容多个版本；版本差异集中在 `compat` 或 Blender Adapter 中。
- 对外清单必须包含 `schema_version`、插件版本和 Blender 版本。
- schema 新增可选字段优先；改写字段含义或删除字段需要版本升级与兼容读取说明。
- Blender API 枚举或属性差异不得泄漏到 Domain；由 Adapter 转换为项目枚举或能力结果。
