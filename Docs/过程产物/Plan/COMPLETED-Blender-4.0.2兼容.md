# Blender 4.0.2+ 兼容实施计划

- 状态：COMPLETED
- 日期：2026-09-15
- 目标版本：0.2.0
- 入口：插件注册、Blender Adapter、构建脚本、README 下载与兼容说明
- 权威来源：`blender_manifest.toml`、`__init__.py::bl_info`、`Docs/reference/实现现状.md`
- 前置依赖：官方 Blender 4.0.2 便携版、现有 Blender 5.2.1、Blender Extension CLI
- 阻塞：无；Blender 4.0/4.1 不支持 Extension 安装体系，需要单独提供 Legacy Add-on 包

## 用户可观察结果

- Blender 4.0.2 及之后版本都能安装并使用插件。
- Blender 4.2+ 用户继续使用标准 Extension ZIP；Blender 4.0.2–4.1 用户使用 Legacy Add-on ZIP。
- 两类安装包来自同一份业务代码，界面、命名、Beauty、Alpha、Object ID、取消和恢复语义一致。
- README 显著说明版本范围、下载选择和安装入口，避免用户拿错安装包。

## 范围与非目标

- 范围：Python 3.10 兼容、Blender 4.0 API 差异、双包构建、最低版本实测、文档与版本号。
- 非目标：支持 Blender 3.x、改变输出契约、重写渲染架构、承诺尚未发布的未来 Blender 永远零修改兼容。
- “4.0.2+”表示最低支持 4.0.2；未来版本在发布时持续回归，不设置人为最高版本。

## 当前实现与责任所有者

- Domain 使用 Python 3.11 的 `enum.StrEnum`，Blender 4.0.2 的 Python 3.10 无法导入。
- Blender Adapter 包含色彩管理和 Workbench 枚举值，需要按宿主能力选择。
- Extension 清单当前最低 4.5；官方 schema 要求 Extension 的最低版本不能早于 4.2。
- Domain 继续拥有枚举语义；兼容实现只补足 Python 标准库差异。
- Blender Adapter 继续拥有 Blender 枚举/API 差异；Presentation 和 Domain 不读取版本分支。
- 构建脚本拥有包型差异，业务源码不复制为第二套实现。

## 方案比较与决策

### 方案 A：把 Extension 清单直接改成 4.0.2

- 优点：表面只有一个 ZIP。
- 缺点：违反 Extension schema 的最低 4.2.0 要求，4.0/4.1 也没有对应安装体系，无法形成真实支持。
- 结论：拒绝。

### 方案 B：共享源码，构建 Extension 与 Legacy 两个 ZIP

- 优点：符合 Blender 官方迁移策略；4.2+ 保持长期可维护的 Extension；4.0/4.1 有真实可安装包；没有第二套业务代码。
- 缺点：发布页需要两个附件并清楚标注。
- 结论：采用。

## 反打洞审查

- 不新增 `bpy.context` 隐式跨层状态；已有上下文仍只在 Blender/Presentation 边界读取。
- 不新增全局任务状态；唯一运行状态仍由 Coordinator 与 `runtime_state` 承担。
- 不复制命名、渲染或清单配置；Legacy 包只是不同目录布局的构建产物。
- 不创建兼容专用 Operator；版本差异集中在 Domain 兼容模块和 Blender Adapter。
- 不形成第二条渲染适配路径；两种安装方式导入同一模块集合。

## 里程碑与验收

### M1：最低版本代码兼容

- 路径：`camera_batch_renderer/domain/`、`camera_batch_renderer/application/`、`camera_batch_renderer/blender/`
- 结果：Blender 4.0.2 可以导入、注册并运行后台集成测试。
- 停止条件：出现无法隔离且会改变输出契约的宿主 API 缺失。

### M2：双安装包

- 路径：`scripts/build_extension.ps1`、`dist/`
- 结果：Extension ZIP 通过 4.2+ schema 验证；Legacy ZIP 具有 `camera_batch_renderer/__init__.py` 包布局并可在 4.0.2 启用。
- 停止条件：两个包需要复制或分叉业务实现。

### M3：兼容矩阵与发布资料

- 路径：`README.md`、`Docs/reference/实现现状.md`、changelog、测试说明。
- 结果：文档区分“最低支持”“实测版本”“未来版本策略”和两个下载入口。

## 验证矩阵

- 纯 Python：Python 3.10 兼容枚举的值、字符串、JSON 和比较语义；现有 unit/architecture 全量通过。
- Blender 4.0.2 后台：注册/注销、双 Camera、Beauty、Alpha、Object ID、像素、取消、失败与状态恢复。
- Blender 5.2.1 后台：同一套回归测试，证明兼容层未破坏当前版本。
- 安装态：4.0.2 Legacy 安装/启用/运行/禁用；5.2.1 Extension 验证/安装/启用/运行/卸载。
- GUI：N 栏与 Output Properties 面板继续注册；最低版本至少验证类注册，当前版本进行可见 UI 验收。
- 性能：兼容分支只在模块导入或临时 ID Scene 配置时执行，不进入逐像素 Python 热路径。

## 幂等、失败恢复与回滚

- 构建脚本覆盖同版本目标包前先明确目标文件，不修改用户 Blender 配置。
- 测试使用临时用户配置或便携版，输出使用临时目录并在结束后清理。
- 失败时保留 `.incomplete` 与 RenderInfo 行为不变；所有 Scene/Camera/Render 设置仍由现有事务恢复。
- 回滚可恢复到 0.1.1 清单和构建脚本，不涉及输出 schema 或用户数据迁移。

## 进度

- [x] 官方 Extension/Legacy 边界研究
- [x] Blender 4.0.2 便携环境与依赖探测
- [x] M1 最低版本代码兼容
- [x] M2 双安装包与安装态验证
- [x] M3 文档、版本与完整回归
- [x] 发布复盘并转为 COMPLETED

## 发现与决策

- Blender 4.0.2 内置 Python 3.10.13，不能导入 `enum.StrEnum`。
- Blender 4.0.2 内置 NumPy 1.23.5 与 OpenImageIO 2.4.15，可继续使用现有 Alpha 写出实现。
- `bpy.app.is_job_running`、render complete/cancel handlers、Workbench 相关设置在 4.0 API 中存在。
- Extension schema 要求 `blender_version_min >= 4.2.0`，所以不能用一个合规 Extension ZIP 覆盖 4.0.2。

## 结果复盘

- 15 个纯 Python 单元测试、4 个架构门禁和 Ruff 全部通过。
- Blender 4.0.2、4.1.1、4.2.0、5.2.1 均完成双 Camera 的 Beauty、Alpha、Object ID、透明 Alpha 复用、取消、故障清单与恢复测试；历史 4.5.11 门禁继续有效。
- Blender 4.0.2 与 4.1.1 的 Legacy ZIP 完成安装、启用、双面板注册、禁用与清理。
- Blender 4.2.0 的 Extension ZIP 完成官方验证、安装、启用和演示场景六图真实渲染。
- Extension：`camera_batch_renderer-0.2.0.zip`，SHA-256 `82534526CBFA679949B892521A5DD2A7505F18A842A2F01CBFFDAFDA11B2E3F0`。
- Legacy：`camera_batch_renderer-0.2.0-legacy.zip`，SHA-256 `C7280C340B5B3AF1025EBC260B2B430DDB8FF3145452F17732667C3BD5DAC1B8`。
- 已知边界：未来 Blender 版本不设清单上限，但仍需在每次上游新版本发布时回归；第三方渲染器仍只默认保证 Beauty。
