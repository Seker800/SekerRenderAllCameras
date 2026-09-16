# Git 自主提交工作流

用户已授权仓库修改且仓库已初始化 Git 时，完成验证后可创建本地提交；只读任务、用户明确不提交或当前目录尚非 Git 仓库时不自动提交。

- 先检查工作区并识别已有改动，只暂存本任务拥有的文件或 hunk。
- 检查是否包含 RenderOutput、缓存、`.blend` 备份、构建 ZIP、密钥或个人 MCP 路径。
- 运行风险匹配的测试和 diff check，创建提交前阅读 `../Commit规范.md`。
- hook 失败时修复根因，禁止 `--no-verify`；默认不 push、不 amend、不做破坏性 reset。
- 收尾报告提交 hash、标题与验证；无法安全提交时说明具体原因并保留改动。

用户明确要求 push 时必须继续执行 [`Commit与Push说明.md`](Commit与Push说明.md)。运行时代码、版本、UI、输出或兼容性变化属于发布型 push，只有 GitHub Release、双包资产和线上下载链接全部验证后才算完成。
