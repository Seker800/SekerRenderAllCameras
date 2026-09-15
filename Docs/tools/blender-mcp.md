# Blender MCP

本项目采用第三方 [ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp) 作为 Agent 与已打开 Blender 之间的可选桥接。它不是 Blender 官方组件，并具备在 Blender 内执行 Python 的高权限能力。

## 组成与端口

- MCP client 启动本地 `blender-mcp` 进程。
- 该进程通过本地 socket 连接 Blender 内的 MCP addon。
- 默认主机为 `localhost`，默认端口为 `9876`；根 `.mcp.json` 显式写出这两个值。
- 同一 Blender 实例只启动一个 client bridge，避免多个客户端抢占同一端口。

## 安装

Windows 先使用 uv 官方安装脚本，并新开终端：

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
uvx --version
uvx blender-mcp install-addon
```

然后在 Blender 中进入 `Edit → Preferences → Add-ons`，启用 `Interface: MCP for Blender`。在 3D View 按 `N`，打开 MCP for Blender 页签并点击 `Start MCP Server`。

## Codex 配置

Codex CLI、桌面端和 IDE 扩展共享用户级配置。注册命令：

```powershell
codex mcp add blender -- uvx blender-mcp
```

等价的用户级 `config.toml` 片段：

```toml
[mcp_servers.blender]
command = "uvx"
args = ["blender-mcp"]

[mcp_servers.blender.env]
BLENDER_HOST = "localhost"
BLENDER_PORT = "9876"
DISABLE_TELEMETRY = "true"
```

根 `.mcp.json` 是兼容其他项目级 MCP 客户端的示例，不代表 Codex 会自动读取它。GUI 客户端找不到 `uvx` 时，先用 `where.exe uvx` 获取绝对路径并重启客户端；不要复制个人绝对路径进仓库。

## 安全边界

- 默认关闭第三方 MCP 遥测；需要启用时由用户明确决定。
- 只绑定 loopback；不要把端口暴露到局域网或公网。
- `execute_code` 等同在当前 Blender 和用户账户下执行代码。只运行本任务生成并审查过的代码。
- MCP 不得读取或上传任务范围外的文件、场景文本、资产账号或 API key。
- 修改前读取状态，修改后验证；临时修改必须恢复，除非用户明确要求，否则不保存 `.blend`。
- 安装或升级 MCP addon 会改写用户 Blender addon 目录，不作为普通项目任务的隐式步骤。

## 排障

- 先确认 Blender addon 已启用且 Blender 侧已点击 `Start MCP Server`。
- 确认只有一个 MCP 客户端进程，端口 `9876` 未被其他程序占用。
- 终端能运行但 GUI 报 `uvx` 不存在时，使用 `where.exe uvx` 返回的绝对路径配置客户端并完整重启。
- Python 解析冲突时，可把 args 改为 `--python 3.11 blender-mcp` 并设置 `UV_PYTHON_PREFERENCE=only-managed`。
- 缓存持续复现旧错误时才运行 `uv cache clean blender-mcp` 与 `uvx --refresh blender-mcp`；这会更新解析结果，执行前记录原版本和问题。
- 连接恢复后先做只读查询，再在临时测试文件中做最小写入验证。

上游命令与行为可能变化；更新本文前以仓库 README 为准，并在 `../reference/实现现状.md` 记录实际验证日期与版本。
