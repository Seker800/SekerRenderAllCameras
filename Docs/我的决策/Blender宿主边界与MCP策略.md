# Blender 宿主边界与 MCP 策略

- 日期：2026-09-15
- 状态：已采纳

## 背景

插件既要在 Blender 进程内通过 `bpy` 工作，又需要让 Agent 检查真实 Scene 和渲染状态。直接把宿主对象散布到所有模块，会使逻辑无法单测、上下文脆弱且难以保证恢复；MCP 还提供任意 Python 执行能力，必须明确权限边界。

## 选择

- 采用 Domain/Application/Blender Adapter/Infrastructure/Presentation 分层，核心规则不导入 `bpy`。
- 所有 Blender 临时写入集中在 `BlenderStateTransaction` 与已登记 Adapter。
- Blender MCP 只作为本地开发和现场验证桥接，不是插件运行时依赖。
- 能连接时优先用 MCP 检查打开中的真实状态；不自动保存 `.blend`，默认关闭第三方遥测，只绑定 loopback。

## 替代方案

- 全部逻辑写入 Operators：文件少，但难以测试、取消、恢复和演进，拒绝。
- MCP 作为插件必需依赖：会把开发工具耦合到用户运行时，拒绝。
- 直接修改 `.blend`：二进制格式不可安全手工编辑，拒绝。

## 后果

需要更多契约和适配代码，但纯规则可快速测试，Blender API 差异可集中处理，MCP 断连不影响插件功能，状态恢复也有单一审查点。
