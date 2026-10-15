# 0.8.0 发布验证

## 发布验证结果

- 固定候选提交：`f240a88770becd650dde66df4aa9f48f7b05c3fa`，干净工作树，发布模式。
- Blender：4.0.2、4.1.1、4.2.0、4.5.13 LTS、5.2.1 LTS。
- **88 passed / 6 failed / 0 not_run；正式发布门禁未通过。**
- 67 个单元测试、7 个架构测试、Ruff、五包同源与版本门禁通过。
- 五包均完成隔离安装、启用、实际四通道及单通道演示、禁用/卸载；跨版本功能契约通过。
- 所有正式 Blender 偏好和启动文件哈希不变；没有替换用户安装。
- 五个 GitHub 公开资产已重新下载，SHA-256 全部与本地已测试包一致。

| 失败步骤 | 本轮结果 |
|---|---|
| 4.0.2 first-start | 三个功能断言均通过；Properties 窗口用例完成后退出码 11 |
| 4.1.1 active-shutdown | 渲染中禁用插件专项原生崩溃，退出码 3221226505，无完成标记 |
| 4.2.0 active-shutdown | 同专项原生崩溃，退出码 3221226505，无完成标记 |
| 4.2.0 gui-cycles | 第一张 Beauty 写出后，渲染流程中原生访问异常，退出码 11 |
| 4.5.13 diagnostics | 四个诊断功能断言通过；全部日志目录不可写用例完成后退出码 3221225477 |
| 4.5.13 gui-cycles | 第三台 Camera Beauty 后停滞，240 秒测试时限触发 |

4.0.2、4.1.1、5.2.1 的本轮 GUI Cycles 整批通过。以上失败原样保留，不用单次重试覆盖。只有 CPU 渲染覆盖，GPU 现场原因仍待诊断。用户已要求不继续第 6 项退出崩溃调查；渲染中崩溃和停滞仍是不同的发布限制。

原始报告：`build/test-reports/20261015-151014-25468/summary.json`。用户已明确授权带已知限制的测试版发布：main 与 [v0.8.0 Pre-release](https://github.com/Seker800/SekerRenderAllCameras/releases/tag/v0.8.0) 已更新，Latest 仍为 0.7.0。`--prerelease --verify-online` 完整通过；五个公开资产下载 SHA-256 与下表一致。正式发布门禁失败状态不变。

## 安装包与 SHA-256

| 文件 | 测试宿主 | SHA-256 |
|---|---|---|
| RenderAllCameras-0.8.0-blender-4.0.2.zip | 4.0.2 | `f5ea7e9af20f8967b4880a6a05771eb725f52ea8b3babed9904e41d02c380c7d` |
| RenderAllCameras-0.8.0-blender-4.1.1.zip | 4.1.1 | `faaf43e5bac80c5a259318d3afa7adeda161f6b6d0b4fa37ab55d9bf50d58136` |
| RenderAllCameras-0.8.0-blender-4.2.0.zip | 4.2.0 | `b35098545b0e6111ae2b4d64a91deab7e996b48b14b58ae261fa7d3635c3f2e7` |
| RenderAllCameras-0.8.0-blender-4.5-lts.zip | 4.5.13 | `3853af86914bee1315ef706d6c3914c9678f65097b88714c4a5f30bc8012df0a` |
| RenderAllCameras-0.8.0-blender-5.2-lts.zip | 5.2.1 | `04d37353e9eb881db35f4a498d59b1f7173974fee50f62969c6f8a4afd240995` |
