# Blender 宿主边界

- `.blend` 是用户资产，不是插件数据库。插件偏好进入 Addon Preferences；文件级可持久设置进入带项目前缀的 Scene 属性；一次任务状态只存在于运行时。
- `bpy.context` 依赖窗口、区域和模式，只能在明确的 UI/Operator 边界读取。能用 data API 的地方不依赖 selection、active object 或屏幕布局。
- `bpy.ops` 需要显式上下文时由 Adapter 负责组装和校验；Domain 不知道 Operator。
- 渲染 handlers、timers 和 WindowManager 状态都必须由任务组合根注册并在完成、取消、异常和插件注销时解除。
- Blender 主线程限制属于 Adapter 契约；后台线程不得访问 `bpy` 数据。
- 修改 Scene 摄影机、World、Light `hide_render`、Collection `hide_render`、LayerCollection `exclude`、输出路径、引擎、图像设置、色彩管理、Workbench 参数、对象显示色或临时数据块时，先登记原值，再修改；恢复顺序与依赖相反。Material ID 只能创建隔离的临时 Material/Mesh/Object/Scene，不得改写用户材质槽、面分配或节点。用户在配对列表中主动选择组合属于预览操作，经统一 Environment Adapter 应用，不归渲染事务回滚。
- 测试 `.blend` 只存放最小、可重建场景。真实用户文件不得进入自动化测试或由 MCP 自动保存。
