# 双包与发布门禁

- 状态：COMPLETED
- 日期：2026-09-16
- 目标版本：0.5.1
- 入口：`scripts/build_extension.ps1`、新增发布门禁、Git commit/push 工作流
- 权威来源：`camera_batch_renderer/version.py`、构建产物与 GitHub Release
- 前置依赖与阻塞：线上 Release 验证仅在用户明确要求 push/release 时执行

## 用户结果与范围

Blender 4.0.2–4.1 的 Legacy Add-on 与 Blender 4.2+ Extension 必须包含同一套功能代码；任何漏文件或内容差异都阻止发布。用户明确要求 `commit and push` 且改动影响插件时，必须同步完成版本、文档、双包、Release 与下载链接闭环。非目标：普通只读检查不发布；纯文档提交不强制提升插件版本。

## 当前实现、所有权与真相源

`build_extension.ps1` 从同一源码树构建两种 ZIP，但尚无产物逐字节对比。版本由 `version.py` 拥有，manifest/pyproject/README/发布资产为受门禁约束的镜像。发布流程由 `Docs/workflow/发布插件.md` 拥有，Git 行为由新增的明确说明拥有。

## 方案比较

1. 构建后规范化 ZIP 路径并逐文件比较，同时检查版本和 README 链接；复用当前单源码构建，失败信息明确，采用。
2. 分别维护 Legacy 与 Extension 两份源码再跑行为测试；会产生功能漂移和双重维护，拒绝。
3. 仅依赖人工清单；无法稳定阻止漏文件、旧下载链接和旧 Release，拒绝。

## 边界与恢复

- 门禁是纯 Python，只读源码与 ZIP，不导入 `bpy`、不改变 Blender 状态。
- 构建仍由既有脚本负责，不增加第二套打包路径。
- 联网 Release 验证仅做 HTTP 读取；发布写操作仍需用户明确要求 push/release。
- 失败时保留构建产物供诊断，不修改 Git 历史或远端。

## 里程碑与验收

1. 新增门禁脚本与单元测试：双包文件集合和字节必须一致，仅允许 Extension 多 manifest。
2. 检查版本表面、README 两个下载链接和双包文件名均为当前版本。
3. 构建脚本自动调用门禁；任一差异以非零退出。
4. 新增明确的 commit/push 说明，并更新发布与 Git 工作流入口。
5. 用 0.5.1 双包运行门禁、单元/架构测试和双包构建。

停止条件：故意改变任一包功能文件时测试先失败；恢复后一致通过；文档明确区分 commit、push 与 release，并规定线上链接验证。

## 进度、发现与决策

- 进度：已完成。
- 发现：首页源代码已到 0.5.0，但最新 Release 与下载按钮仍为 0.2.1；现有流程未把 push 和发布闭环绑定。
- 决策：运行时代码改动的 push 默认视为完整发布事务；非运行时代码改动仍需核对线上下载链接未失真，但不强制发版。

## 结果复盘

`scripts/release_gate.py` 已接入双包构建，0.5.1 的 33 个功能文件逐字节一致；单元测试证明内容不同时门禁失败。README、manifest、项目元数据、changelog 和双下载 URL 纳入版本检查。Blender 4.0.2 安装态验证还发现并修复了 `bl_info` 非字面量会破坏 Legacy 插件发现的问题，新增 AST 门禁防止回归。发布后的在线资产检查由 `--verify-online` 执行。
