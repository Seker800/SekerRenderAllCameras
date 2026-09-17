# 发布契约与五包同源门禁

- 状态：COMPLETED（本地实现；线上发布另行执行）；日期：2026-09-16；目标版本：0.7.0。
- 入口：五包构建、发布门禁、安装态验收、README 下载入口。
- 权威来源：`camera_batch_renderer/version.py`（版本）、`packaging/blender_targets.json`（宿主目标）、新增 `packaging/release_contract.json`（公开身份与功能契约）。
- 前置依赖与阻塞：保留现有未提交 0.7.0 工作；正式线上验证要等用户明确要求发布。

## 结果与边界

五个包必须从同一源码构建，拥有相同的公开名称及四个输出选项。每个安装态包须验证 Beauty 默认开启、四个通道可单选、全不选拒绝及结果集合准确。下载文件名使用可辨认的产品名，内部 Extension ID 和 Legacy Python 包名保持 `camera_batch_renderer`，避免升级后产生第二个插件。README 在 0.7.0 未发布前仍指向 0.6.0，不暗示当前下载含 0.7.0 功能。

非目标：改动渲染业务语义、改动 Blender 用户场景、自动提交/push/Release、改写历史资产。

## 当前实现与方案

现有共享代码已在构建时按 `host_policy` 生成五包，但资产前缀来自源码目录名；发布门禁比较文件字节和全选四通道结果，未检查公开身份及每个安装包的输出选项行为。Presentation 拥有 UI Property；Blender Adapter/Application 拥有通道执行；构建和门禁在 `scripts/`，不跨边界改变核心。

方案 A：复制最新 Blender 包再向旧版回迁。会形成五份业务真相，拒绝。方案 B：共享源生成目标包，发布契约登记公开身份和通道能力，安装态逐包实测，采用。

不新增 `bpy.context` 隐式入口、全局可变状态、临时 Operator 或第二条宿主路径。测试仅使用隔离 Blender 用户目录与自建演示场景；不保存或修改用户 `.blend`。单通道批次沿用现有快照与 `finally` 恢复机制，失败后只保留允许的隐藏诊断标记。

## 里程碑与停止条件

1. `packaging/release_contract.json`、`scripts/build_target_packages.py`、`scripts/release_gate.py`：规范显示名、模块 ID、资产名和四通道期望；故意改错任一包显示名/开关时门禁失败。
2. `scripts/run_installed_demo.py`、`scripts/verify_cross_version_contracts.py`、`scripts/run_full_test_suite.ps1`：五版本隔离安装后验证 UI 身份和四个单通道，比较跨版本语义；任何未执行或不一致阻断发布。
3. `README.md` 和稳定文档：区分公开 0.6.0 与开发 0.7.0，记录命名与发布规则；纯 Python、Blender 后台、GUI、取消/失败恢复和五目标安装态复核。

回滚：本次只改源码和生成产物逻辑，不更改线上资产；若验证失败，保留旧 Release 并明确 0.7.0 未发布。最终记录实测 Blender 精确版本、摘要与未运行项。

## 进度与复盘

- [x] 身份与构建契约：五个 `RenderAllCameras-0.7.0-<目标>.zip` 构建成功，内部 ID 不变，静态门禁通过。
- [x] 安装态通道契约：五版本均检查产品名、两个面板、四个开关/默认值、四个单通道及全不选拒绝。
- [x] 文档与门禁反例：旧 README 下载链接会阻断 0.7.0 正式发布门禁；单元测试验证面板缺项、线上 tag 漂移与哈希漂移均失败。
- [x] 全量验证：`build/test-reports/20260916-220112-28064/summary.json`，Blender 4.0.2、4.1.1、4.2.0、4.5.13、5.2.1 共 63 项通过、0 失败、0 未运行；跨版本契约通过。第一次测试的 Extension `bl_info` 测试假设错误已修复并重跑。开发工作树仍脏，不构成正式发布；线上仍为 0.6.0。
