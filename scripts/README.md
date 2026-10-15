# Scripts

`run_gui_render_tests.py` 从“新渲染窗口”用户偏好、真实 3D View 上下文启动 GUI 三摄影机批次，
验证原生渲染窗口、宿主空闲后推进、当前图片后停止、连续运行和用户偏好不变；
丢失 `render_complete` 的文件后备语义由纯逻辑测试单独覆盖。

存放可复现的测试、打包和本地开发入口。脚本必须支持非交互执行、正确退出码和明确工作目录；不得写入用户 Blender 配置、安装/升级 MCP 或覆盖 `.blend`，除非脚本名称和文档明确说明且由用户主动执行。

- `build_extension.ps1`：读取 `packaging/blender_targets.json`，从共享纯核心装配 4.0.2、4.1.1、4.2.0、4.5 LTS、5.2 LTS 五个独立 ZIP，并用各目标 Blender 校验 Extension 清单。
- `build_legacy_package.py`：按固定顺序、时间戳和文件属性生成可重复构建的 Legacy ZIP。
- `run_blender_tests.py`：在目标 Blender 中验证真实渲染、像素、取消、故障与恢复。
- `run_blender_edge_cases.py`：验证预检、Camera/格式矩阵、Compositor、Render Border/Crop、文件名冲突与 `.blend` 不被保存。
- `run_full_test_suite.ps1`：全量测试唯一入口；执行所有层、隔离安装/卸载并生成 `build/test-reports/` JSON 摘要和逐步日志。
- `test_legacy_install.py`：在 factory-startup 隔离环境中安装 Legacy 包，并从真实安装路径运行完整四通道演示后禁用与清理。
- `run_installed_demo.py`：针对已安装 Legacy/Extension 运行演示场景端到端验收并输出跨版本功能契约。
- `run_stress_smoke.py`：执行 50 Camera 和连续十批小尺寸真实渲染烟测，检查输出稳定性与临时数据清理。
- `test_target_version_rejection.py`：在真实目标 Blender 中确认错版本包的固定宿主策略拒绝注册。
- `verify_cross_version_contracts.py`：比较五个安装态包的 Camera、通道、结果矩阵、清单 schema 与 ID 调色板。
- `run_environment_pair_acceptance.py`：创建两 Camera、两套隐藏/排除灯组与两个 World 的 EEVEE 真实场景，实际导出 Beauty，检查图片色彩、RenderInfo 和宿主状态恢复。验收产物保留在 `build/environment-pair-acceptance/`。
- `run_material_id_acceptance.py`：创建双材质面与未分配材质物体，实际导出 Material ID PNG，逐像素核对黑色背景、稳定颜色映射、材质槽/面分配不变和临时数据清理。验收产物保留在 `build/material-id-acceptance/`。
- `run_gui_host_control.py`：在加载插件但不启动插件批次的前提下执行单张异步 GUI 渲染，用于区分 Blender/驱动宿主崩溃与插件批次调度故障；它不是插件 GUI 验收的替代品。
- `capture_plugin_screenshot.py`：在真实 Blender GUI 中加载已安装插件、展开 3D View 的插件侧栏并截取编辑器区域；通过 `RAC_SCREENSHOT_PATH` 指定临时截图位置，不保存 `.blend`。
- `release_gate.py`：逐包对照当前源码装配结果，检查内部版本、身份、功能文件、README、changelog 和下载链接，并比较五包共享功能；Release 上传后加 `--verify-online` 核对线上 README、Release 正文和五个资产的 SHA-256。安装态跨版本功能行为仍由 `run_full_test_suite.ps1 -Release` 阻断验收。

- GUI 测试必须经 `run_full_test_suite.ps1` 启动；`blender_test_safety.py` 在缺少已创建的隔离 `BLENDER_USER_*` 目录时拒绝执行，正式配置目录不能作为测试配置。测试前后比较真实 `userpref.blend` / `startup.blend` 哈希，报告写入 `protected-profiles.json`。
- `run_collection_visibility_tests.py` 验证仅切换已登记的集合根，保留手动隐藏子集合、未配对集合、对象开关和多 View Layer 状态，覆盖异常恢复。
- `run_gui_render_tests.py` 支持 `RAC_TEST_ENGINE=CYCLES` 与 `RAC_TEST_SAMPLES`；全量入口使用 CPU、512×512、1024 samples，检查渲染期间 timer 心跳、连续输出和协作停止。GPU 长渲染仍需对应设备验收。

- `run_gui_host_control.py` 等待宿主 job 结束再退出；用 `RAC_HOST_CONTROL_WITH_ADDON=0` 可在同一隔离环境中完全不导入插件，核对 native-only 对照。零退出码与成功标记必须同时满足。

- `run_full_test_suite.ps1 -BlenderPaths ... -PackageBlenderPaths ...` 可以只运行重点版本，同时用完整五版本路径构建和校验五包。发布模式仍要求全部目标的运行与安装态验收，不能用包校验替代运行覆盖。
- `run_exit_probe_matrix.py --blender label=executable --output build/新目录` 串行隐藏启动隔离进程，保留每次退出码、日志、crash 文件和正式配置哈希；默认诊断模式记录失败，`--require-success` 则强制失败退出。`--backend` 只对该测试进程传入后端参数，不保存用户偏好；默认保持宿主默认后端。
- `probe_render_exit.py` 对比原生渲染、NumPy/OIIO 导入、插件注册/注销；`--factory-reset 0` 避免启动后第二次工厂重置。全部测试正常 quit，不以强制进程退出隐藏错误。
- `--modes native_window --engine CYCLES` 增加独立 Render Result 窗口的原生 CPU 512×512、1024 samples 对照，用于区分渲染窗口重绘与批次调度故障；应同时设置足够的 `--timeout`（例如 150 秒）。
- `--modes native_sequence --engine CYCLES` 在上述窗口中完成主场景后复制临时 Alpha Scene，再异步渲染并恢复/删除，用于最小化跨场景重绘问题。
- `probe_first_start.py` 覆盖冷启动的 3D View/Output Properties、NONE/WINDOW 显示偏好及启动失败回滚；一次有效请求必须产出图片，失败请求后 runtime/staging 必须清理。
- `probe_active_shutdown.py` 在 Cycles Alpha 辅助 Scene 正被渲染时禁用插件，核对延迟清理、取消清单、用户场景恢复和正常退出。
- `probe_pixel_export.py` 核对实际 Blender 颜色转换和完整 Alpha 字节，记录处理耗时与 Python 内存峰值。以上 probe 由矩阵入口隔离执行，不在用户实例中直接运行。
- `probe_cycles_transitions.py` 覆盖首次点击、加载文件、编辑模式、Output Properties、单层渲染与锁定界面；每进程连续三批、每批两摄影机四通道。可选 `RAC_PACKAGE_PARENT` 仅用于诊断源码快照，默认测试当前源码。
- `probe_render_diagnostics.py` 覆盖启动异常、单张渲染异常、主目录不可写/全部不可写、长渲染存活记录和取消；检查诊断内容、重启后的目录定位、场景和原文件恢复。由 `run_exit_probe_matrix.py --probe probe_render_diagnostics.py --modes startup render_failure fallback unwritable heartbeat cancel` 隔离启动；全量入口纳入前四种工况。功能断言与原生退出码分别报告，不隐去失败。
