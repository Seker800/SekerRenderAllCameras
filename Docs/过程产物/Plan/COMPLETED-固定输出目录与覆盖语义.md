# 固定输出目录与覆盖语义实施计划

- 状态：COMPLETED
- 日期：2026-09-15
- 目标版本：0.3.0
- 入口：Domain 命名、Infrastructure 输出目录、Blender Runtime、Presentation UI、清单与测试
- 权威来源：`domain/naming.py`、`infrastructure/storage.py`、`domain/models.py::RenderPlan`、`PLAN.md`
- 阻塞：无

## 用户可观察结果

- 保存后的 `.blend` 旁边只使用固定目录 `SekerRenderAllCameras/`。
- 不再生成 `RenderOutput/001/`、`002/` 等批次目录，文件名也不再带数字批次前缀。
- 本次成功生成的同名图片和清单覆盖旧文件。
- 本次没有生成的旧图片保留；插件不在开始时清空目录，也不删除已移除摄影机或未勾选通道的历史输出。
- 旧的 `RenderOutput/` 不迁移、不删除，避免损坏用户已有成果。

## 范围与非目标

- 范围：移除批次号配置和数据模型，改为固定目录与稳定文件名，实现覆盖/保留语义，升级清单 schema，更新 UI、测试和文档。
- 非目标：自动删除历史目录，清理“多余”图片，迁移旧批次，改变当前 Scene/当前帧/全部可用 Camera 的产品范围。

## 当前实现与责任所有者

- `domain.naming` 当前拥有三位批次号和带前缀文件名；改后它仍是固定目录名和输出文件名的唯一真相源。
- `infrastructure.storage` 当前通过创建新的数字目录避免冲突；改后只准备固定目录和运行标记，绝不清空普通文件。
- `RenderPlan` 当前携带 `batch_number`、`batch_label`、`conflict_policy` 的假真相；改后完全删除这些已失效字段。
- Blender Runtime 负责将 `.blend` 路径、命名结果和存储契约组合起来；UI 只展示通道选项和固定输出位置。

## 方案比较与决策

### 方案 A：保留内部批次号，只在 UI 和路径中隐藏

- 优点：改动少。
- 缺点：模型、清单和测试仍维护一个用户已经不存在的 ID，后续容易再泄漏到文件名或界面。
- 结论：拒绝。

### 方案 B：端到端删除批次概念，以稳定路径表达覆盖语义

- 优点：用户契约与代码模型一致；同名路径天然实现新图覆盖旧图；不扫描和删除目录即可保留未生成的旧图。
- 缺点：是输出契约的破坏性变更，需升级清单 schema 和小版本。
- 结论：采用。

## 反打洞审查

- 不在 Runtime、UI 和测试中各写一份文件夹字符串；固定名称由 Domain 导出。
- 不用隐藏的固定批次号兼容旧函数；旧批次 API 直接移除。
- 不新增目录清理 Operator、全局状态或跨层 `bpy.context` 依赖。
- 不为“覆盖”建第二条渲染通路；Adapter 继续写 Coordinator 分配的唯一目标路径。

## 里程碑与验收

### M1：Domain 与存储契约

- 移除批次号、批次冲突策略和前缀命名。
- 固定目录重复准备是幂等的，已有普通文件不被删除。

### M2：Blender Runtime 与 UI

- 同一 `.blend` 的两次渲染使用完全相同的输出路径，第二次覆盖同名成果。
- 取消、失败和异常仍写 `.incomplete` 并恢复 Blender 状态，不删除之前的图片。
- UI 不再显示批次前缀，只显示 `//SekerRenderAllCameras/`。

### M3：Schema、文档与发布产物

- RenderInfo schema 升为 2 并移除 `batch`；固定清单名不带前缀。
- 产品基线、架构、实现现状、README、测试说明和 changelog 与新契约一致。
- 构建和安装 0.3.0 产物前，通过纯 Python、架构、Ruff、Blender 后台与 GUI 回归。

## 验证矩阵

- 纯 Python：无前缀命名、固定目录幂等、已有文件保留、marker 完成/不完成切换。
- 架构：Domain 不引入 Blender；UI 不拥有路径/命名规则；无旧批次 API 残留。
- Blender 后台：双 Camera、Beauty/Alpha/Object ID、第二次覆盖同名文件、未生成旧图保留、取消/失败/恢复。
- GUI：面板无批次字段，模态渲染连续运行，取消后可再次启动。
- 版本与打包：清单、`bl_info`、`pyproject` 和运行清单版本一致。

## 幂等、失败恢复与回滚

- 开始时只创建/复用目录并刷新 `.inprogress`，不删除其他文件。
- 已有同名输出只在新渲染真正写出时被替换；未进入的 action 不触碰它的目标。
- 取消或失败不清理旧成果，只更新状态清单与 `.incomplete`。
- 回滚代码可恢复 0.2.2 批次输出逻辑；已生成的新目录不自动搬移或删除。

## 进度

- [x] M1 Domain 与存储契约
- [x] M2 Blender Runtime 与 UI
- [x] M3 Schema、文档、验证与产物
- [x] 发布复盘并转为 COMPLETED

## 发现与决策

- 用户语义是“有新图才覆盖”，因此不在 session 开始时预删除任何输出。
- 文件名仍包含 Blend、Camera、通道、尺寸、引擎/采样等可观察特征，只删除批次前缀。
- 固定正式路径使旧文件天然存在，不能再把“正式文件存在”当作当前渲染完成信号；当前动作改为检查独立 staging 输出，避免误把旧图当新图而提前推进。

## 结果复盘

- 端到端删除 `batch_start`、`batch_number`、`batch_label`、`ConflictPolicy`、批次分配 API 和 UI 字段，没有保留隐藏的假批次 ID。
- 新图片先写 `.staging-*` 临时目录，完成后以 `os.replace()` 替换正式路径；取消、失败和未执行动作不触碰旧图，任务结束清理 staging。
- 21 个纯 Python 单元测试、5 个架构门禁和 Ruff 全部通过。
- Blender 5.2.1 后台测试通过：固定目录、无数字前缀、同路径重复渲染、实际覆盖、未勾选 Object ID 保留、无关旧文件保留、取消/失败/状态恢复和 staging 清理均通过。
- Blender 5.2.1 GUI 测试通过：在首轮三张旧图已经存在时，第二轮仍正常启动；取消后只完成当前图，其余旧图保留，没有再次出现队列提前停止。
- Extension 清单验证、0.3.0 Extension/Legacy 双包构建和真实安装态六图演示通过；本机 User Default 已重装并启用 0.3.0。
- Extension SHA-256：`619334282E322724D446F900B44EC1AF6321B1BC3B708D60453CF18559029681`。
- Legacy SHA-256：`CC2568B209950831D005890FA5C57EC040B5369CC69D62A4D00C8ED5215B5FA7`。
