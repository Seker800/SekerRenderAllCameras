# 渲染可观察性与集合显隐

- 状态：BLOCKED（源码修复已验证，4.0.2 GUI 重绘异常与 GPU 覆盖未解决）；日期：2026-10-15；目标：现有五个固定 Blender 目标。
- 入口：用户反馈无渲染进度、预设污染对象与无关集合、Cycles 输出不可靠。
- 权威来源：PLAN.md、architecture/架构约束.md、模块通信约束.md；依赖为现有事务、RenderAdapter、BatchCoordinator、host_policy。MCP 未连接，不能确认用户现场原因；GitNexus 未索引本仓库，使用源码调用链。
- 可观察结果：GUI 打开原生 Render Result 窗口并异步运行；队列在宿主空闲后记账；切换预设仅修改登记的集合根，不改对象、子集合和无关组；输出继续 staging 原子提交。
- 范围：environment、state_transaction、render_adapter、host_drivers、固定目标策略及回归测试；不保存用户 blend、不改引擎和采样、不推断 GPU 波动原因。
- 方案：同步 timer 稳定但冻结界面且不可观察；旧 modal 异步依赖窗口事件路由。选择 application timer 异步调度，显式保存启动窗口上下文，等待 render job 退出与 handler/新 staging 信号。保留后台同步入口。
- 显隐方案：逐对象隔离违反用户期望；只切换配对集合根保持用户对象与子层状态。父级手动隐藏继续生效；嵌套配对避免隐藏活动集合祖先。
- 所有权：BatchCoordinator 拥有任务；事务拥有临时集合状态恢复；environment 是唯一预览/渲染集合适配边界；host driver 只驱动既有 session。无新增全局真相、临时 operator 或跨层 bpy.context。
- M1：环境切换与事务测试；M2：异步窗口与失败/取消/长等待测试；M3：全量入口、Cycles 专项、文档回写。
- 验证：unit/architecture/ruff，独立 Blender 后台环境/恢复，GUI 连续批次/取消/失败与 Cycles 长任务；五版本按实际可用性执行，不用单版本替代兼容验收。
- 幂等/恢复：每动作恢复基线再应用；finally 恢复宿主；新图成功才提交，失败保留旧图与 incomplete；回滚对应源码改动即可，不动既有用户修改。
- 停止条件：无法安全恢复即终止；崩溃/缺版本明确记 failed/not_run。完成需记录报告路径、测试结果、兼容限制并更新 reference/流程与计划索引。

## 发现与验证记录

- M1/M2 已实施：集合根显隐、不对用户 Light 写入开关、保护子层排除状态、全 View Layer 恢复；原生窗口复用、Cycles/EEVEE 异步与 Workbench 同步、宿主空闲后提交、无输出静默退出记失败。
- Blender 取消父 LayerCollection 排除时会递归修改子层；已用真实多 View Layer 回归证明子层状态保持。隐藏非活动根不再使用 exclude=True，避免清空对象 Base 的 eye 状态。
- 50 个 unit 与 7 个架构测试通过；模拟活跃任务持续十小时不误超时、丢 handler 后备、静默退出失败和原生取消等待宿主退出均有回归。
- 五版本首轮完整报告：`build/test-reports/20261015-132712-32920/summary.json`，71 passed / 3 failed / 0 not_run。五个 Cycles GUI 与五个集合专项均通过；不能把该报告称为全量通过。
- 首轮失败：4.0.2 core 的旧断言要求强制显示子层，已按保留手动子层的新契约更正，并在 `build/feedback-regressions-402/` 重跑整个 core 与集合专项通过；4.5.13 宿主对照和 5.2.1 安装态演示在退出时出现 `igxelpicd64.dll` access violation，后者发生在 INSTALLED_DEMO_OK 与全部图片/JSON 写完之后。宿主对照的 quit 时序已修为等待 job 空闲后退出；不吞退出码或把输出完成标记当成进程通过。
- 用户要求保留正式偏好。此前少量手动 GUI 测试使用 factory-startup 独立窗口，未保存用户偏好；正式 4.0/5.2 userpref 的修改时间仍为 2026-10-14。后续统一隔离并隐藏启动；新增缺隔离目录即拒绝的 guard，完整报告 `protected-profiles.json` 确认所有正式配置 SHA-256 不变。
- Cycles 本机仅检测到 CPU；GUI 使用 512×512、1024 samples，五版本渲染中 timer 心跳分别为 394/319/409/438/481。此结果不能替代朋友机器的 GPU 或长达数小时的生产场景验收。
- 未升级 Blender、MCP 或显卡驱动，未覆盖真实插件安装，未保存用户 blend、未提交或发布。现有未提交的 release_gate 等用户改动保留。

## 最终收尾与阻断

- 重点复核报告：`build/test-reports/20261015-133707-33796/summary.json`，24 passed / 2 failed / 8 not_run。两个失败分别为 5.2.1 宿主对照在 quit 后再次出现 Intel GL access violation，以及只传两个 Blender 路径时五包构建器拒绝缺失的 4.1.1 等目标；后者不是插件运行失败，五包构建/源码门禁已在首轮报告通过。不把 skipped 安装态写成通过。
- Cycles CPU 四通道真实 GUI：5.2.1 在重点报告中完整通过（840 心跳）；4.0.2 在 `build/feedback-final-regressions/4.0.2-cycles-all.log` 完整通过（611 心跳），均包含三摄影机、独立 Alpha Scene、Object/Material ID、Material-only 下一批、当前图片完成后停止及 blend/偏好恢复。
- `build/feedback-final-regressions/summary.json` 两项通过：4.0.2 四通道 Cycles 和修正退出时序后的 4.5.13 宿主对照。
- `build/feedback-native-control-52/summary.json` 在完全不导入/注册插件的 5.2.1 宿主对照中连续两次退出正常。这只能缩小调查范围，不能据此断言之前异常与插件完全无关，也不能推断朋友 GPU 波动的原因。
- 原始失败报告保留，不覆写结果或忽略非零退出码。整体检查摘要：`build/feedback-diagnosis.json`；正式配置在两次报告中前后 SHA-256 均相同，最终只剩用户原先的 Blender PID 4556。
- 下一步：在能复现的宿主上定位 Intel GL 退出路径/插件卸载交互，并取得有 Cycles GPU 的测试设备与朋友场景；未获证据前不升级宿主或驱动、不宣称第四项已完全解决、不发布或替换用户安装。恢复实施时使用当前源码与上述日志即可，无需聊天记忆。

## 2026-10-15 继续排查

- 用户明确要求继续第四项与退出崩溃，优先 4.0.2/5.2.1；继续使用 project-bugfix-loop，不使用真实配置或用户实例做实验。
- 比较方案：直接更换驱动/后端会改变用户环境且不足以定位插件责任；选择进程隔离对照（native、numpy/OIIO、adapter import、register、unregister），再按差异收敛；不通过 os._exit 或忽略退出码掩盖 native 异常。
- 阶段 N1：小场景重复退出矩阵与 crash 栈；N2：定位共享状态/资源/调度责任后最小修复；N3：重点版本长 Cycles、失败/取消与真实文件提交，最后完整门禁。
- 新诊断脚本仅在 scripts/ 内拥有测试配置与进程；正式配置哈希前后核验，所有 GUI 进程逐一隐藏启动；原生状态保持由既有 transaction 与 finally 承担。

## 首次启动与输出阶段扩展

- 用户新增反馈：前两三次点击未开始渲染。范围增加 `infrastructure.storage` 临时目录回收与 Presentation 启动失败反馈；唯一所有者仍是 Storage（文件生命周期）、BlenderBatchSession（启动事务回滚）与既有 Operator（展示错误），不新增跨模块旁路。
- 已复现 Windows 真实 sharing lock：旧实现 `rmtree(ignore_errors=True)` 隐藏失败后，mkdir 抛 WinError 183；0.15 秒锁释放后再次点击才可启动。加入 bounded sharing-lock 重试（总等待上限 0.35 秒），永久错误明确报错；完成清理也不再静默忽略错误。回归先失败后通过，旧输出保留。
- 启动错误保留在面板状态；已创建的 session 若 start/driver.start 失败，通过 session.abort_start 统一恢复事务、标记失败并清理，poll 提供正在运行/宿主忙的原因。
- 退出矩阵首轮 32 次：4.0.2 native（无插件、无 NumPy/OIIO Python 导入）4 次中 1 次在 Intel GL DLL unload / LdrShutdownProcess 崩溃，图片和 job_idle 已确认；其余 31 次退出正常。正式配置哈希保持一致。该证据证明至少一种退出异常独立于插件，不据此解释朋友现场所有故障。
- 首次 UI 探针 r1/r2 在测试脚本初始化 UI 时上下文尚未就绪，尚未调用产品 Operator，属于无效测试；r3 将区域初始化放到显式 window override 的 timer 后再测，不把脚本自身错误记为产品缺陷。
- 同时测量 1024 图像后处理的 Python 内存/耗时：当前 Alpha 和 ID 会复制全图为 Python float tuple/list，4K/8K 可能造成明显 CPU 等待与高内存；只有实测确认后才改为 foreach_get 与分块向量化，并核对 256 色/Alpha 精度和恢复。所有这些修改只在 Blender Adapter，纯核心不依赖 NumPy/bpy。

- 异步生命周期审查新增风险：原 unregister 会在 render job 仍持有辅助 Scene 时同步 cancel/cleanup。调整为由既有 active driver 保存一次关闭回调、请求当前图片后停止，在 job idle、输出记账、事务恢复与 timer 清理完成后才注销类/属性；不增加全局状态或第二条 timer。load_pre 复用 driver.finish 处理待关闭回调。以真实 Cycles Alpha-only 活跃渲染中的 disable 回归验证，禁止删除仍被 job 使用的 Scene。

## 继续排查的实测结果

- 54 unit、7 architecture 与全目录 ruff 通过。Windows 真实文件锁回归已先验证旧代码失败，再验证新代码单次 prepare 成功；永久锁明确失败且不破坏最终旧图。
- `build/first-start-probes-r3/summary.json`：两版本各四种 UI/偏好组合、每种两次冷启动共 16/16 正常启动和退出；`build/failed-start-rollback-probes/summary.json`：两版本故障注入后均成功回滚并接受下一次请求。
- 像素实测 `build/pixel-export-baseline/` 与 `build/pixel-export-after/`：1024×1024 的 ID Python 峰值由约 160 MiB 降至 25 MiB，Alpha 由 144 MiB 降至 24 MiB；tracemalloc 下 ID 由 10.6–14.5 秒降至 0.12–0.14 秒。只代表后处理，不代表整批渲染提速。`build/pixel-export-4k/` 两版本 4096×4096 调色板及全部 Alpha 字节检查通过。
- `build/active-shutdown-probes/summary.json`：四次功能断言均通过；4.0.2 第二次完成断言后在 Intel DLL 退出路径崩溃，仍保留 exit 11，不能写为四次进程通过。
- 最新重点套件 `build/test-reports/20261015-141154-28128/summary.json`：39 passed / 1 failed / 0 not_run。两个重点版本的首次启动、启动回滚、渲染中禁用、安装态、后台核心与边界通过，五包构建/源码门禁通过、两版本契约一致、正式配置哈希不变。4.0.2 Cycles GUI 首张 Beauty 写完后在 `blender::gpu::GLFrameBuffer::bind → wm_draw_window_offscreen` 崩溃，尚未完成本轮四通道；该异常不同于退出 DLL 栈。5.2.1 本轮四通道通过（1069 心跳）。原始失败不能被此前通过覆盖。
- `build/native-exit-52-opengl/` 不加载插件、不导入 NumPy/OIIO、不执行第二次 factory reset 的 8 次原生 GUI 对照中，第 4 次在同一个 `igxelpicd64.dll` 地址与 LdrShutdownProcess 栈崩溃；写图成功且 job_idle。至此两个重点版本均直接复现了独立于插件的 Intel GL 退出故障。
- 新增 `native_window` 对照，用原生 Cycles CPU 512×512/1024 samples 和独立 Render Result 窗口检查新出现的 4.0.2 重绘异常；测试后端选择只通过测试进程参数，不改变用户偏好。
- `build/native-exit-52-vulkan/summary.json`：5.2.1 相同原生对照仅进程参数切换 Vulkan，8/8 正常渲染及退出，正式配置哈希不变。只能作为本机 OpenGL 路径的定位证据，未对插件全通道或用户 GPU 场景做 Vulkan 兼容结论，不自动更改用户配置。
- `build/native-cycles-window-402/summary.json`：原生 Cycles 独立 Render Result 窗口 4/4 通过；`build/native-cycles-sequence-402/summary.json`：主场景后复制临时 Alpha Scene 并再次异步渲染 3/3 通过。尚未在最小原生对照复现套件中的 GLFrameBuffer 重绘崩溃，不能把这处故障直接归因于驱动或排除插件交互。
- 本轮收尾摘要为 `build/continued-diagnosis.json`。代码已修复并验证的范围是短暂文件锁、启动回滚/反馈、像素内存与活跃 job 的安全注销；退出 DLL 和 4.0.2 GUI 重绘风险仍需独立解决，缺少 Cycles GPU 设备与朋友现场。未更改用户配置、驱动、原始实例或真实安装，不发布。后续从保留的失败 fixture、crash 栈和当前源码继续，禁止把偶发通过当成修复。
