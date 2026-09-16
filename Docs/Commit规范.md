# Commit 规范

本文件是本项目 commit message 的唯一权威来源。

格式：`<类型>: <一句话描述>`

可用类型：`新增`、`修复`、`重构`、`清理`、`文档`。

标题说明实际结果，不使用英文 Conventional Commit 前缀，不罗列文件路径。示例：`新增: 建立 Blender 插件架构与文档体系`。

提交前必须复核 staged 文件、diff、测试结果和是否包含 `.blend` 备份、渲染输出、密钥或个人 MCP 配置。禁止用 `--no-verify` 绕过门禁。

Commit 不等于发布。用户要求 push 时，必须遵循 [`workflow/Commit与Push说明.md`](workflow/Commit与Push说明.md)；发布型 push 必须同步版本、README、更新日志、双安装包、GitHub Release 和下载链接。
