# 插件逻辑全面审查

- 日期：2026-10-15；对象：当前工作区 0.7.0 源码，包括已有未提交修复。
- 范围：Domain 命名/调色板、Application 调度/取消、Blender 四通道/环境/事务、文件原子提交/JSON、Presentation 注册/回调/计时器、五目标装配与测试入口。
- 用户打开的 Blender MCP 不可达；未操作该实例、用户 blend 或真实插件安装。原有 ACTIVE 计划及修改保留。

## 已修复的问题

| 优先级 | 触发与影响 | 修复与证据入口 |
|---|---|---|
| P1 | `Cam/A`、`Cam:A` 和 `Cam_A_02` 可写到同一路径；长名二次截断及长路径截断也丢失 Camera/通道身份 | Naming 使用统一预算、全局已用名集合和截断摘要；最终路径预检；test_naming 三项先失败后通过 |
| P1 | Film Transparent 开启但 Composite 改写 Alpha 或 Beauty 为 JPEG/RGB 时，Alpha 被错误复用 | 限制复用条件，辅助禁用 Sequencer；edge 增加透明 Film + Composite、JPEG 真实像素断言 |
| P1 | 当前图片提交后，写清单/清理失败会被 driver 当成下一动作失败并继续 | BatchIntegrityError 终止批次，保留已提交结果；session/driver 故障注入先失败后通过 |
| P1 | 辅助清理异常会跳过 Camera、filepath 等宿主恢复 | finish 分别执行清理、恢复和文件清理，失败状态及 incomplete 明示；恢复故障回归 |
| P1 | 打开新 blend 后非 persistent handlers 消失，取消与 load 清理失效 | 三个 handlers 持久化；真实 Blender 文件重置后检查回调仍注册 |
| P1 | 辅助 Scene 构造中异常发生在 adapter 接管之前，留下 Scene/资源 | 构造异常自清理，每个新数据块立即登记；core 注入三种构造失败 |
| P1 | ID 依赖全局当前 Scene 的 depsgraph，窗口/场景切换后可能从错误场景复制几何 | 显式 source/首 View Layer override、更新与 evaluated Camera；不同上下文构造 ID 回归 |
| P2 | 两张图片之间点击停止，下一张仍被启动 | 空闲时在准备动作前处理停止；driver 先失败后通过回归 |
| P2 | 非整数缩放和裁切时元数据尺寸与实际像素不一致 | 分辨率与边界用 Blender 整数截断规则；35×39、50%、0.2–0.8 裁切由错误 11×12 修为实际 10×12 |
| P2 | 完成批次会把当前子帧归零 | 事务同时捕获和恢复 subframe；真实 0.25 子帧回归 |
| P2 | 空 Object ID 输出不写 JSON，残留上一批对象映射 | 始终写映射，空场景输出 objects=[]；core 空场景回归 |
| P2 | 环境配对等预检错误发生在工作目录被回收后；运行中选项可编辑；同步单项失败直接中断批次 | 计划/路径预检前置，禁用运行中输出开关，同步路径复用 fail_current |

## 验证记录

- 初始基线：54 unit + 7 architecture。
- 修复后普通 Python：63 unit + 7 architecture，ruff 通过。
- 开发诊断：`build/review-targeted-20261015-142315/` 复现裁切尺寸错误；`build/review-targeted-20261015-142756/` 的新空 Scene fixture 未更新 View Layer，修正 fixture 后 `build/review-targeted-20261015-142841/` core/edge 输出成功标记。临时 PowerShell 的退出码采集不足，正式通过结论只采用全量入口报告。
- `build/test-reports/20261015-142432-10708/` 为提前停止的旧源码测试，`INTERRUPTED.txt` 明示，不计完整通过。停止已确认属于本任务的套件进程，测试 Blender 自行结束，用户原有 PID 4556 保留。
- 首轮完整入口报告：`build/test-reports/20261015-143015-13628/summary.json`，62 passed / 9 failed / 18 not_run。6 项失败是旧 GUI 测试在 render 启动前点击停止却期待一张结果，现已拆为零张的立即停止与一张的活跃停止；4.2.0 Cycles 在视口 `immVertex3f → DRW_draw_cursor` 崩溃，4.5.13 Cycles 超时，原因未确认；构建过程中另一个任务增加诊断模块与事件，源码/ZIP 不一致，门禁阻止安装态测试。
- 为避免并行编辑污染最终证据，在 `build/rv/` 固定合并源码（含新增诊断功能），`build/rv/source-hashes.json` 保存逐文件 SHA-256；以该目录为根重新执行完整入口。工作区 67 unit、7 architecture、ruff 通过。
- 修订 GUI 测试：Workbench 同步渲染用 render_pre 只提交纯 coordinator 停止意图，禁止在 render handler 内调用 UI operator；Cycles 等待 job 活跃后由 UI timer 调用实际停止 operator。
- 最终五版本完整报告：`build/rv/build/test-reports/20261015-145014-35308/summary.json`（执行中）。

## 限制

- 本机只有 Cycles CPU 验证条件，未宣称 GPU 或真实大型生产场景已验证。
- 既有计划记录的 Intel GL 退出异常仍需按每次实际进程退出码判定；不能因图片已写完就忽略崩溃。
- 本次不包含发布、推送或覆盖正式安装。测试构建产物不能自动等同发布合格。
