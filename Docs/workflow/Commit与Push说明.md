# Commit 与 Push 说明

本文件明确区分本地提交、远端推送和插件发布。用户说出 `commit and push`、`提交并推送` 或同义要求时，必须按本文件执行，不得把“代码已推到 main”误报为“用户已经能下载最新版”。

## Commit

Commit 只在本地记录已验证改动：

1. 识别并仅暂存本任务文件，检查 staged diff。
2. 排除 `.blend` 备份、渲染输出、缓存、构建 ZIP、密钥和个人 MCP 配置。
3. 运行风险匹配的测试及 `git diff --cached --check`。
4. 按 [`../Commit规范.md`](../Commit规范.md) 创建提交，禁止 `--no-verify`。

Commit 本身不代表 GitHub Release 已发布，也不代表首页下载链接可用。

## Push 触发规则

用户明确要求 push 后，先判断 staged/committed 改动是否影响可安装插件：

- 修改 `camera_batch_renderer/` 运行时代码、版本、面板、输出契约、兼容范围或安装行为：视为“发布型 push”，必须完成下方完整事务。
- 仅修改开发文档、测试说明或不进入安装包的工具：可以普通 push，但仍须读取 GitHub 最新 Release，确认首页没有把旧包描述成当前版本。
- 无法判断时按发布型 push 处理，不得默认只推源码。

## 发布型 Push 是一个完整事务

以下项目缺一不可：

1. 更新唯一版本源、Extension manifest、项目元数据、RenderInfo 版本、更新日志和 README 当前版本。
2. UI 有变化时更新真实 Blender 截图；兼容范围或操作变化时同步更新说明。
3. 按目标配置构建五个独立 Blender 版本包，运行 `scripts/release_gate.py`，确认共享功能文件逐字节一致且每包版本边界准确。
4. 完成目标 Blender 版本、安装态、渲染、取消/失败和状态恢复验证。
5. README 顶部按钮、正文安装链接和文件名全部指向本次版本，禁止残留旧版本下载 URL。
6. 创建符合规范的 commit 并 push 主分支；创建同版本 Git tag/GitHub Release，上传五个 ZIP 和校验值。
7. 运行 `python scripts/release_gate.py --verify-online`，要求最新版 Release 的五个资产都可下载，且线上内容 SHA-256 与本地已测试 ZIP 完全一致。
8. 重新读取 GitHub 线上 README 与 Release，核对版本、资产名和下载链接；只有此时才能向用户报告“已更新并可下载”。

如果 GitHub Release、资产上传或在线链接验证失败，任务状态必须明确为“源码已 push、发布未完成”，不得用 commit hash 代替发布完成证明。

## 收尾报告

报告至少包含：commit hash、tag/Release 版本、五个目标资产名及 SHA-256、在线下载哈希验证结果、测试摘要以及工作区是否干净。
