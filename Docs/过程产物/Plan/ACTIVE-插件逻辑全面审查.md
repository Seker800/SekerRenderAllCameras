# 插件逻辑全面审查

- 状态：ACTIVE；日期：2026-10-15；目标版本：packaging/blender_targets.json 的五个固定目标。
- 入口：用户要求全面 review 并修复问题。权威来源：PLAN.md、architecture/、reference/实现现状.md、workflow/全量测试流程.md。
- 前置：保留现有未提交改动与独立 ACTIVE 计划；MCP 当前不能连接，现场只读检查不可用，使用隔离测试实例。
- 可观察结果：不同 Camera/通道不互相覆盖；Alpha 符合原始透明度定义；错误不归到下一动作；失败仍恢复宿主状态；打开新文件后 handler 可用；辅助构造失败不泄漏资源。
- 范围：Domain Naming、Blender Session/Adapter/辅助 Scene、Presentation 生命周期与相关测试；不提交、不发布、不覆盖真实安装或保存用户 blend。
- 现有所有权：Naming 决定文件名；BatchCoordinator 拥有任务状态；BlenderBatchSession 协调提交/清单；StateTransaction 恢复宿主；host driver 负责调度；复用这些契约。
- 方案比较：在 driver 中捕获全部异常后继续，无法区分动作失败与已提交后的清单失败；选择明确批次级异常并由既有 coordinator 终止。命名随机后缀不可重复，选择确定性冲突分配与截断摘要。
- 反打洞：不新增全局任务状态、临时 Operator 或第二套适配器；核心无 bpy；辅助 Scene 构造异常自清理，批次 finally 保证事务恢复。
- M1：记录基线、逐层源码审查与先失败的单元回归；M2：最小修复及真实 Blender 边界用例；M3：全量五版本测试、文档和审查结论。
- 验证：普通 Python/架构/ruff；五版本后台 Alpha/命名/生命周期/恢复；现有 GUI、取消、单项失败、CPU Cycles、压力与安装态门禁。GPU 没有设备则不宣称验证。
- 临时状态：Camera、filepath、辅助 Scene/对象/材质，沿用统一事务与清理；失败清单和 incomplete 保留，旧的未成功输出不动。回滚只撤销本次增量。
- 停止条件：恢复、清单一致性或输出安全不可保证即终止批次；宿主崩溃/缺失目标如实 failed/not_run，不能改写为通过。
- 文档影响：reference/实现现状.md 与 review 报告；完成时更新本索引和计划状态。

## 进度

- 基线：54 unit、7 architecture 通过。审查已定位命名碰撞、Alpha 复用条件不足、提交后错误归属及 finally 恢复路径问题。
- M1/M2 完成：12 组问题与修复已记录在 review/ACTIVE-插件逻辑全面审查.md；新增先失败后通过的命名、清理、错误归属和取消测试，真实 Blender core/edge 覆盖 Alpha、构造回滚、上下文、空 ID、文件加载、子帧和裁切尺寸。
- 首轮完整入口 62/9/18，包含旧取消测试断言、4.2/4.5 GUI Cycles 异常和并行诊断功能编辑造成的包源码漂移；原报告保留。固定 `build/rv/` 源码快照重跑五目标，所有用户原有修改及并行新增功能保留。
