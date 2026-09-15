# 首版完整实现计划

## 状态

- 状态：ACTIVE
- 日期：2026-09-15
- 产品入口：根 `PLAN.md`
- 最低支持：Blender 4.5 LTS
- 当前实机验证：Blender 5.2.1 LTS
- 远端：`Seker800/SekerRenderAllCameras`（private）
- 阻塞：当前机器未安装 Blender 4.5 LTS，因此 4.5 兼容性只能先由能力检测、API 边界和静态检查覆盖；发布候选阶段再补 4.5 实机。

## 用户可观察结果

安装 Extension 后，用户可在 Output Properties 中看到 Render All Cameras 面板，设置批次、Alpha 与 Object ID，点击一次即可按稳定顺序渲染当前 Scene 的全部 Camera。输出写入 `.blend` 同级 `RenderOutput/<批次>/`，任务进度、失败和取消可见，任务结束后恢复活动 Camera 和所有临时宿主状态。

## 范围与非目标

范围以根 `PLAN.md` 第一版为准：Beauty、条件性 Alpha、离散 Object ID、原子批次、增量清单、取消、恢复、Extension 包与测试。非目标包括动画、多 Scene、分布式渲染、Material ID 和 Cryptomatte 输出。

## 当前实现与所有权

- 当前只有架构和目录说明，没有 Python 实现。
- `domain` 拥有不可变配置、状态、命名、排序和颜色规则，不导入 `bpy`。
- `application.BatchJob` 是任务生命周期唯一写入者。
- `blender` 包是唯一 `bpy` 边界，拥有 Scene 读取、渲染、结果提取、临时辅助 Scene 和状态事务。
- `infrastructure` 拥有文件系统与原子 JSON。
- `presentation` 只收集意图、调用 Coordinator 和展示快照。

## 方案比较与决策

### 调度

- 方案 A：同步循环执行所有 render。实现简单，但 UI 无法可靠更新和取消。
- 方案 B：Modal Operator + Timer + render handlers + 单一状态机。复杂度更高，但符合 Blender 主线程和取消要求。
- 决策：采用 B；handler 只写事件标志，状态机在主线程推进。

### Object ID

- 方案 A：临时修改原对象颜色并用 Workbench 渲染。速度快，但可能污染原对象、链接对象不可写。
- 方案 B：从 evaluated depsgraph 构建隔离临时 Scene，再用 Workbench 渲染。内存较高，但状态边界清晰。
- 决策：采用 B；无法转换的类型写入清单限制，不回退到修改原对象。

### Alpha

- 原场景透明时复用 Beauty Render Result。
- 原场景不透明时使用隔离辅助 Scene 二次渲染，关闭合成并开启 Film Transparent。
- 不以“全白 Alpha”冒充成功，也不改变 Beauty 语义。

## 公开契约

- `RenderPlan`：冻结批次、Scene、View Layer、帧、Camera DTO、通道和输出计划。
- `BatchJob`：`start()`、`advance(event)`、`request_cancel()`、`snapshot()`。
- `BlenderSceneReader`：构造冻结 DTO，不把 `bpy` 对象传入 Domain。
- `BlenderRenderAdapter`、`BlenderAlphaAdapter`、`BlenderObjectIdAdapter`：通道边界。
- `BlenderStateTransaction`：幂等恢复。
- `ManifestWriter`：同目录临时文件 + `os.replace`。

## 反打洞审查

- Domain/Application 禁止导入 `bpy`。
- Panel 和 Operator 不实现命名、渲染循环或文件写入。
- 不通过 module-level 可变字典保存第二份任务真相；唯一运行任务由组合根持有，并提供只读快照。
- 不使用 Python Thread 操作 Blender 数据。
- 不创建第二条直接调用 `bpy.ops.render` 的旁路。
- 所有 `scene.camera`、Film、引擎、色彩管理和临时 datablock 变化进入同一个状态事务。
- 临时操作器只表达用户命令，不拥有任务状态。

## 里程碑与提交边界

### M1：纯核心与持久化

路径：`domain/`、`application/`、`infrastructure/`、`tests/unit/`、`tests/architecture/`。

结果：命名、自然排序、批次、颜色、状态机 DTO、原子清单可在系统 Python 中测试。停止条件：单元测试和导入边界测试全过。

### M2：Beauty 与 Extension UI

路径：包根、`blender/`、`presentation/`、Blender 集成脚本。

结果：Extension 可注册，面板可见，多 Camera Beauty 能输出，状态恢复。停止条件：Blender 5.2.1 后台测试和 MCP/GUI 最小验证通过。

### M3：Alpha 与 Object ID

路径：辅助 Scene、像素输出、ID palette/manifest、对应集成测试。

结果：透明场景复用 Alpha，不透明场景辅助渲染；ID 图为离散颜色且原场景不被修改。停止条件：像素、临时数据和恢复测试通过。

### M4：可靠性、文档与发布包

路径：取消、失败注入、README、reference、changelog、构建脚本。

结果：完整错误语义、增量清单、可安装 ZIP。停止条件：全量测试、Extension validate/build、干净安装/禁用/卸载通过。

每个里程碑独立 commit 并 push；任何里程碑未达到停止条件不得提交为完成。

## 验证矩阵

- 纯 Python：`python -m unittest discover -s tests/unit -v`。
- 架构：`python -m unittest discover -s tests/architecture -v`。
- Blender 后台：使用 Blender 5.2.1 执行 `scripts/run_blender_tests.py`。
- MCP/GUI：在临时测试文件中验证面板、Camera 顺序、输出、进度与恢复。
- 故障：渲染失败、写入失败、取消、重复启动、清理幂等。
- 性能：至少以多 Camera 小场景检查无结果累积和临时 datablock 泄漏。
- 兼容：能力检测覆盖 4.5/5.2 差异；5.2.1 实机；4.5 实机作为发布门禁。

## 幂等、失败恢复与残留

- `unregister()`、handler/timer 解绑和状态恢复必须可重复调用。
- 已完成图片不因取消删除。
- 清单每个通道后原子更新；异常最多丢失当前尚未提交的一个状态更新。
- 未完成批次保留 `.incomplete` 和可读 JSON。
- 临时数据只按任务 UUID 精确删除。
- 插件不保存 `.blend`；强制退出时磁盘工程不写入临时状态。

## 文档影响

每个里程碑更新 `Docs/reference/实现现状.md`。稳定接口变化同步 `Docs/architecture/模块通信约束.md`；用户可见结果写入 README 和 changelog；发布命令写入工具/发布文档。

## 进度、发现与决策

- [x] 环境发现：Git、Git LFS、GitHub CLI、uvx、Blender 5.2.1 LTS 可用。
- [x] 建立私有远端并推送初始提交。
- [x] M1 纯核心与持久化：10 个单元测试、1 个架构测试和 Ruff 检查通过。
- [x] M2 Beauty 与 Extension UI：Blender 5.2.1 后台双摄影机渲染与 MCP 注册检查通过。
- [ ] M3 Alpha 与 Object ID。
- [ ] M4 可靠性、文档与发布包。

## 结果复盘

完成后填写最终 commit、测试、包哈希、未验证项和已知限制，并将文件改名为 `COMPLETED-首版完整实现.md`。
