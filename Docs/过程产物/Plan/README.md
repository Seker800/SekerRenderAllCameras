# Plans

创建、更新、评审或执行计划前，必须完整阅读 [`../../workflow/我要编写实施计划.md`](../../workflow/我要编写实施计划.md)。

## 当前执行

- `ACTIVE`：[`ACTIVE-分版本Blender适配与发布矩阵.md`](ACTIVE-分版本Blender适配与发布矩阵.md) — 共享纯核心，按 4.0.2、4.1.1、4.2.0、4.5 LTS、5.2 LTS 分别装配宿主实现、测试和发布。
- `COMPLETED`：[`COMPLETED-双包与发布门禁.md`](COMPLETED-双包与发布门禁.md) — 自动比较 Extension/Legacy 功能内容，并把运行时 push 与版本、Release、下载链接闭环绑定。
- `COMPLETED`：[`COMPLETED-面板显示版本号.md`](COMPLETED-面板显示版本号.md) — 在两个插件面板中直接显示当前运行版本，区分旧内存实例与新安装包。
- `COMPLETED`：[`COMPLETED-Material-ID通道.md`](COMPLETED-Material-ID通道.md) — 新增稳定材质颜色、Material ID PNG 与材质映射 JSON，并完成真实 Blender 验收。
- `COMPLETED`：[`COMPLETED-摄影机灯光与World环境配对.md`](COMPLETED-摄影机灯光与World环境配对.md) — 为摄影机配对灯光 Collection 和 World，渲染时隔离切换并完整恢复。
- `COMPLETED`：[`COMPLETED-固定输出目录与覆盖语义.md`](COMPLETED-固定输出目录与覆盖语义.md) — 移除批次 ID/数字目录，改为 `.blend` 旁固定输出目录与“新图覆盖、未生成旧图保留”语义。
- `COMPLETED`：[`COMPLETED-Blender-4.0.2兼容.md`](COMPLETED-Blender-4.0.2兼容.md) — Python 3.10/Blender 4.0 API 兼容、双安装包与版本矩阵验证。
- `COMPLETED`：[`COMPLETED-首版完整实现.md`](COMPLETED-首版完整实现.md) — 首版插件的分层实现、里程碑、验证与发布结果。
- 产品基线：根 [`PLAN.md`](../../../PLAN.md) — 产品范围、输出契约与第一版验收标准。

## 状态规则

- 文件名使用 `ACTIVE-主题.md`、`BLOCKED-主题.md` 或 `COMPLETED-主题.md`。
- 状态变化时同步重命名并更新本索引。
- 稳定规则不得只留在计划中；完成前必须回写架构、参考、流程、工具或决策文档。
