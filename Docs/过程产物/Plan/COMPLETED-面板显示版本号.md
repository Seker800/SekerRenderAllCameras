# 面板显示版本号

- 状态：COMPLETED
- 日期：2026-09-16
- 目标版本：0.5.1
- 入口：Output Properties 与 `3D Viewport → N → Batch Render`
- 权威来源：`camera_batch_renderer.version.VERSION`
- 前置依赖与阻塞：无

## 用户结果与范围

两个插件面板底部直接显示当前运行中的插件版本，用户无需打开偏好设置即可判断 Blender 内存里加载的是新包还是旧包。覆盖 Blender 4.0.2–4.1 Legacy Add-on 与 Blender 4.2+ Extension。非目标：不自动升级插件、不修改 `.blend`、不增加联网检查。

## 当前实现与所有权

版本身份由 `camera_batch_renderer.version.VERSION` 拥有；`presentation.panel.draw_controls` 是两个面板的共享绘制入口。实现只读取该唯一版本源，不把版本复制到 Scene 属性、全局运行状态或第二条 UI 路径。插件入口、打包清单、项目元数据和 RenderInfo 由一致性测试约束为同一版本。

## 方案比较

1. 从 `camera_batch_renderer.version.VERSION` 读取并在共享控件末尾显示：复用唯一身份来源，没有持久状态，Legacy/Extension 同时生效，采用此方案。
2. 新增 Scene 字符串属性保存版本：会把安装包身份写进用户文件，可能随 `.blend` 留下过期版本，违反只读展示职责，拒绝。
3. 分别从 Extension manifest 和 Legacy 元数据读取：形成两条适配路径且运行时解析文件没有必要，拒绝。

## 边界审查

- 不使用 `bpy.context` 隐式读取版本；绘制函数只使用显式传入的 layout/context。
- 不增加全局可变状态、临时 Operator、配置副本或 Blender 状态事务。
- 不改变 Scene、WindowManager、Render Result、对象、材质、节点或输出文件。
- 绘制失败不会留下文件或状态；回滚只需移除一行 UI 与版本变更。

## 里程碑与验收

1. 将版本提升到 0.5.1，并让面板从 `bl_info` 显示 `Version 0.5.1`。
2. 扩展架构测试，证明面板引用唯一版本来源且各包表面版本一致。
3. 在 Blender 5.2.1 GUI 截图确认文字可见；用 Blender 4.0.2 Legacy 安装态确认注册和面板绘制无异常。
4. 运行单元测试、架构测试、Ruff、双包构建；更新实现现状和功能日志。

停止条件：两个面板均显示运行中版本、两种包构建通过、无 Blender 状态变化、版本一致性门禁通过。

## 进度、发现与决策

- 进度：已完成。
- 发现：用户当前 Blender 曾出现磁盘为 0.5.0、内存仍运行 0.4.1；面板缺少版本信息会放大误解。
- 决策：显示安装包运行时版本，不显示 `.blend` 保存时版本。

## 结果复盘

0.5.1 已在共享面板底部显示 `Version 0.5.1`。25 个单元测试、6 个架构测试与 Ruff 通过；Blender 5.2.1 Extension 实际截图确认版本可见，Blender 4.0.2 Legacy 隔离安装、注册、禁用与清理通过。实现不新增 Scene 属性或 Blender 可变状态。
