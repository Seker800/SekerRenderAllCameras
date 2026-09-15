# Blender API 验证记录

目标 Blender 版本确定后，在此记录通过最小实验确认的事实：

- `bl_info`/extension manifest 要求与安装方式。
- Cycles、EEVEE、Workbench 的实际 `scene.render.engine` 枚举。
- Render Result 的像素和 Alpha 读取方式、色彩空间影响与内存行为。
- Workbench Object Color 是否能生成符合规范的稳定 ID PNG。
- timer、handler、取消和 UI 进度在目标版本的行为。
- 后台模式下可运行的测试与必须在 GUI 中验收的行为。

每条记录包含 Blender 完整版本、最小脚本或测试路径、观察结果和日期。未经验证的 API 名称不得写成实现事实。
