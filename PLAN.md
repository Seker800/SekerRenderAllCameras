# Blender 全摄影机静帧批量渲染插件开发计划

> 文档状态：实施基线（Revision 6）
>
> 最低目标版本：Blender 4.0.2
>
> 兼容验证版本：Blender 4.0.2、4.1.1、4.2.0、4.5 LTS 最新补丁版、5.2 LTS 最新补丁版

## 1. 项目概述

开发一个 Blender 插件，用于按照当前 `.blend` 文件的渲染设置，一键逐个渲染当前 Scene 中的所有摄影机，并将结果统一保存到 `.blend` 文件旁的 `SekerRenderAllCameras/` 目录。Blender 4.2+ 交付 Extension，4.0.2–4.1 交付同源 Legacy Add-on。

每台摄影机输出：

- Beauty 主图，可选且默认开启；
- Alpha 黑白贴图，可选；
- Object ID 彩色贴图，可选。
- Material ID 彩色贴图，可选。

插件只处理启动任务时的当前静帧，不提供动画、帧范围或视频渲染。

## 2. 已确定的产品决策

1. 一轮任务只处理一个 Scene、一个固定帧和多台摄影机。
2. 所有结果保存到 `.blend` 文件同级的 `SekerRenderAllCameras/`，不创建数字批次目录。
3. 文件名不使用批次 ID；同名新图成功后覆盖旧图，本次未生成的旧图保留。
4. Beauty、Alpha、Object ID、Material ID 均可独立选择；至少选择一项，Beauty 默认开启并严格遵循用户原有渲染内容设置。
5. Alpha 定义为“排除 World 背景后的原始渲染层透明度”，不是用户最终合成节点输出的 Alpha。
6. 如果原场景没有开启透明背景，Alpha 需要一次独立辅助渲染，不能承诺零成本生成。
7. Object ID 定义为“可见表面对象的离散彩色标签图”，默认关闭抗锯齿，确保像素颜色能够精确映射到 JSON。
8. Alpha 和 Object ID 使用隔离的临时辅助 Scene，不修改原对象颜色、材质或 Pass Index。
9. Material ID 使用隔离的临时 Workbench Scene，按材质数据块分配稳定颜色并保留逐面材质索引；未分配材质使用非黑色 `Unassigned` 标签。
10. 固定目录名和文件命名以 Domain Naming 为唯一事实来源，不依赖 `.blend` 内属性持久化。
11. Blender 数据访问和任务调度全部在主线程执行，不使用 Python 后台线程操作 `bpy`。
12. 每完成一个关键步骤就原子更新任务清单，异常退出后仍可追踪已生成文件。
13. 插件不主动保存 `.blend` 文件；完成或失败后不留下临时 Scene、对象、图像、节点或材质。

## 3. 第一版范围

### 3.1 包含

- 当前 Scene 的当前帧静帧渲染。
- 当前 Scene 内全部摄影机的稳定收集和排序。
- 按用户选择逐台摄影机生成 Beauty、Alpha、Object ID 和/或 Material ID；允许任意单通道。
- 可选 Alpha。
- 可选精确 Object ID PNG。
- 可选精确 Material ID PNG 与材质颜色映射 JSON。
- 自动创建输出目录。
- 文件名清理、重名处理和成功后原子覆盖。
- 任务进度、当前摄影机、成功/失败/跳过计数。
- 协作式停止。
- 增量 `RenderInfo.json`。
- Object ID 颜色与实例映射 JSON。
- 正常、取消及异常路径的统一清理。
- Blender Extension ZIP 构建和验证。
- 后续 0.4.0 扩展：Camera 可选配对 Light Collection 和 World，渲染时临时切换并完整恢复。

### 3.2 不包含

- 动画、帧序列或视频。
- 同时处理多个 Scene。
- 网络或分布式渲染。
- 摄影机专属分辨率/采样预设。
- Cryptomatte EXR 输出；架构会预留后端接口，后续版本可增加。
- Stereo/Multiview；第一版预检时明确拒绝。
- 第三方渲染引擎的无条件兼容承诺。

## 4. 用户界面

面板放在“输出属性”中，名称暂定为“全摄影机批量渲染”。

### 4.1 设置区

- `输出 Beauty`：默认开启。
- `输出 Alpha`：默认关闭。
- `输出 Object ID`：默认关闭。
- `输出 Material ID`：默认关闭。
- `输出 Material ID`：默认关闭。
- `输出目录`：只读显示 `//SekerRenderAllCameras/`。
- `摄影机数量`与`预计文件数量`。
- `Camera Environments`：可添加/删除 Camera + Light Collection + World 配对；Light/World 均可留空以继承 Scene 默认。

### 4.2 执行区

- `开始批量渲染`。
- 运行期间禁用所有会改变本轮配置的控件。
- 当前状态，例如 `Beauty：Camera_Front（2/8）`。
- 总体进度条。
- `停止`按钮。
- 完成摘要：成功、失败、跳过、总耗时和输出目录。

### 4.3 必须显示的提示

- 原场景未开启 Film Transparent 时，勾选 Alpha 会为每台摄影机增加一次辅助渲染。
- Object ID 是离散标签图，边缘默认不做抗锯齿。
- Material ID 是按材质数据块生成的离散标签图；没有材质的表面使用 `Unassigned`。
- Volume 暂不纳入 Object ID。
- 未保存 `.blend` 时必须先保存。

## 5. 摄影机收集规则

第一版收集：

```text
scene.objects 中所有 type == 'CAMERA' 且 data 有效的对象
```

具体规则：

- 不处理其他 Scene 中独有的摄影机。
- 不因为摄影机自身 `hide_render` 为真而自动跳过；该属性通常表示摄影机对象是否作为物体出现在其他渲染中，不等同于禁止从该摄影机渲染。
- 如果摄影机位于被当前 View Layer 排除的集合中，必须通过集成测试确认是否仍可作为活动摄影机；无法正常使用时记录失败并继续。
- 链接库摄影机只要能够成为 Scene Camera 就允许使用。
- 按摄影机名称进行不区分大小写的自然排序，例如 `Camera2` 位于 `Camera10` 前。
- 排序键相同时，以对象完整名称和库来源作第二排序键，保证顺序稳定。

后续版本可以增加“全部、选中、指定集合”范围，但不进入第一版。

## 6. 输出目录与覆盖规则

目录结构：

```text
项目目录/
├── 客厅方案.blend
└── SekerRenderAllCameras/
```

根目录使用 Blender 相对路径表达：

```text
//SekerRenderAllCameras/
```

实现规则：

1. 使用 `bpy.data.filepath` 判断文件是否已保存。
2. 目录可重复准备，不清空已有图片或清单。
3. 新图先写入输出目录内唯一的固定隐藏工作目录，成功后使用原子替换覆盖同名旧图；成功完成后整体删除工作目录。
4. 未进入本次计划、未成功生成或取消后尚未执行的输出不碰触已有文件。
5. `.inprogress`、`.incomplete`、staging 和 JSON 临时文件都位于固定隐藏工作目录中，不散落到最终输出根目录；取消或失败只在该目录保留未完成状态。
6. 旧的 `RenderOutput/` 不自动迁移或删除。

## 7. 文件命名

默认结构：

```text
{Blend文件名}_{摄影机名}_{通道}_{关键参数}.{扩展名}
```

示例：

```text
客厅方案_Camera_Front_Beauty_3840x2160_Cycles_S256.png
客厅方案_Camera_Front_Alpha_3840x2160.png
客厅方案_Camera_Front_ObjectID_3840x2160_Object.png
客厅方案_Camera_Front_MaterialID_3840x2160_Material.png
客厅方案_RenderInfo.json
客厅方案_ObjectID.json
客厅方案_MaterialID.json
```

### 7.1 Beauty 关键参数

- 实际输出分辨率，包含分辨率百分比计算结果。
- 渲染引擎简称。
- 能够可靠读取时加入主采样数，如 `S256`。

文件名中的参数只用于人工识别，不代表完整可复现配置。完整配置以 `RenderInfo.json` 为准。

### 7.2 Alpha、Object ID 与 Material ID 参数

- Alpha：实际分辨率。
- Object ID：实际分辨率及固定类型 `Object`。
- Material ID：实际分辨率及固定类型 `Material`。

当前帧不默认进入文件名；帧号必须写入清单。在同一 `.blend` 中改变帧后重新渲染会覆盖同名通道文件。

### 7.3 文件名安全

- 替换 `/ \\ : * ? \" < > |` 等非法字符。
- 处理 Windows 保留名称：`CON`、`PRN`、`AUX`、`NUL`、`COM1` 等。
- Unicode 名称规范化。
- 清除末尾空格与句点。
- 连续空白合并为下划线。
- 使用大小写不敏感的冲突检测，以兼容 Windows 和默认 macOS 文件系统。
- 清理后为空时使用安全占位名。
- 根据完整路径预算截断 Blend 名和摄影机名，始终保留通道、参数、扩展名和重名后缀。
- 清理后重名时按稳定排序追加 `_02`、`_03`。

## 8. Beauty 输出规范

### 8.1 内容语义

Beauty 是用户在当前 Scene、当前 View Layer 和当前帧使用正常“渲染图像”得到的最终 Composite 结果。

插件沿用：

- 当前渲染引擎；
- 分辨率、百分比、像素比例和 Render Border/Crop；
- Cycles/EEVEE 采样和降噪；
- 灯光、材质、World、透明设置；
- 色彩管理、曝光和 Look；
- Compositor 设置；
- 静态图像格式、色深、压缩或质量。

插件只临时切换 `scene.camera`。Beauty 完成后通过正式图像保存接口写入目标文件，不长期修改用户的默认输出路径。

### 8.2 第一版格式白名单

明确支持：

- PNG
- JPEG
- TIFF
- OpenEXR
- OpenEXR Multilayer

FFmpeg、AVI 等视频格式在预检阶段拒绝。其他静态格式只有通过目标版本集成测试后才能加入白名单。

### 8.3 预检限制

- Stereo/Multiview 开启时拒绝任务，并说明第一版不支持。
- 检查输出目录是否可创建和写入。
- 检查渲染引擎是否可用。
- 第三方引擎允许尝试 Beauty，但 Alpha/ID 支持必须按能力矩阵决定，不能静默假设兼容。
- 提醒用户：其已有 Compositor File Output 节点仍可能按照原节点设置额外写出文件，这是 Blender 正常行为。

## 9. Alpha 输出规范

### 9.1 定义

Alpha 是排除 World 背景后的原始 Render Layer 透明度：

- 白色：完全不透明；
- 黑色：完全透明；
- 灰色：半透明或采样后的边缘覆盖率；
- 与 Beauty 的实际像素尺寸一致；
- 保存为无损 8-bit 灰度 PNG；
- 使用 Non-Color/Data 语义，避免显示变换改变数值。

### 9.2 生成策略

场景原本开启 Film Transparent 时：

1. 正常渲染 Beauty。
2. 从原始 Render Layer Alpha 提取结果。
3. 不增加第二次完整渲染。

场景原本没有开启 Film Transparent 时：

1. 先按用户原设置生成 Beauty，保留原 World 背景。
2. 创建隔离的临时辅助 Scene。
3. 临时 Scene 继承必要的渲染、View Layer、摄影机和可见性设置。
4. 在临时 Scene 中开启 Film Transparent，并绕过用户最终 Composite 背景。
5. 执行第二次渲染并提取原始 Render Layer Alpha。
6. 删除临时 Scene 和所有临时数据。

这样保证 Beauty 不被 Alpha 选项改变，同时对额外成本作如实说明。

### 9.3 已知边界

- Alpha 代表渲染器计算出的透明度，不等同于“所有物体轮廓强制为白色”。
- Holdout、透明材质、玻璃和体积的表现取决于渲染引擎。
- 第三方引擎只有通过兼容测试后才启用 Alpha。
- 提取像素时必须验证 Render Result、Render Layer、View Layer 和预期尺寸一致。

## 10. Object ID 输出规范

### 10.1 定义

第一版输出“可见表面对象的离散 ID 标签图”：

- 每个可见对象或可见实例使用一个稳定 RGB 颜色。
- 背景固定为 `#000000`。
- 灯光和摄影机不分配 ID。
- Volume 第一版不支持，并在清单中记录。
- 不受原材质、纹理、灯光、阴影、反射和曝光影响。
- 默认关闭抗锯齿，避免边缘产生不存在于颜色表中的混合颜色。
- 固定输出无损 8-bit RGB PNG。
- 禁用 dithering，并使用经过验证的中性色彩转换路径。

### 10.2 隔离实现

不得修改原场景对象的 `color`、材质槽或 `pass_index`。推荐实现：

1. 在当前帧取得依赖图评估结果。
2. 创建专用临时 ID Scene。
3. 复制当前摄影机及必要的相机数据到临时 Scene。
4. 遍历依赖图中的可渲染对象和对象实例。
5. 将可转换的评估后可见几何复制为临时对象，保留世界变换、可见遮挡关系和实例位置。
6. 为每个临时对象写入分配好的 Object Color。
7. 使用 Workbench、Flat Lighting、Object Color，关闭阴影、Cavity、轮廓、镜面、透明叠加和抗锯齿。
8. 设置黑色背景、零 dithering 和经过测试的中性色彩管理。
9. 渲染并保存 PNG。
10. 在统一清理路径中删除临时 Scene、对象、网格、摄影机和图像。

这种方案会增加可选的临时内存占用，但避免污染原对象，也能处理多数链接库对象和评估后的修改器结果。

### 10.3 稳定 ID 分配

颜色分配不能只做一次 Hash 后直接使用。必须：

1. 为对象构造稳定键：库来源规范路径、对象完整名称和对象类型。
2. 对实例追加实例拥有者及稳定实例路径/持久标识。
3. 对稳定键进行确定性 Hash。
4. 映射到排除黑色和过暗颜色的 24-bit 调色板。
5. 检测本批次颜色碰撞；发生碰撞时按稳定规则探测下一颜色。
6. 将最终 8-bit 输出颜色写入 JSON，而不是仅记录内部线性浮点颜色。

用户重命名对象、改变实例结构或库路径后，ID 可能变化。第一版不向原对象写入 UUID，因此不承诺跨重命名稳定。

### 10.4 精确性验收

- 对象内部像素必须与 JSON 中的 8-bit RGB 完全一致。
- PNG 中除了黑色背景，只允许出现 JSON 中声明的颜色。
- 如果目标 Blender/显卡组合无法保证该条件，Object ID 功能必须在该组合上禁用并提示，而不是输出看似成功但数值错误的图片。

### 10.5 后续专业后期模式

架构预留 `CRYPTOMATTE_EXR` 后端。Cryptomatte 是更适合 Blender、Nuke 等后期流程的标准方案，能够表达多对象像素、透明和抗锯齿；它与第一版离散 PNG 的用途不同，不混为同一种输出。

### 10.6 Material ID 输出规范

- 每个 Blender Material 数据块使用一个确定性、非黑色的 8-bit RGB 标签；稳定键由库来源和材质完整名称组成。
- 同一个 Material 用于不同对象、摄影机或重复任务时保持同色；重命名材质或改变库路径后允许改变。
- 同一 evaluated Mesh 的不同材质槽和 polygon `material_index` 必须保留，因此不同材质面输出不同标签。
- 没有材质或空材质槽使用固定语义键 `builtin|<Unassigned>`，获得独立的非黑色颜色；黑色只表示背景。
- 使用隔离的临时 Workbench Scene、Flat Lighting、Material Color、关闭阴影/高光/抗锯齿和 dithering；不修改用户 Material、节点、材质槽或面分配。
- 固定输出无损 8-bit RGB PNG，并写入 `{Blend}_MaterialID.json`，记录材质键、显示名、RGB、Hex 和跳过项。
- Volume 暂不支持并明确写入已知限制。

## 11. 任务清单与恢复标记

每批输出：

```text
客厅方案_RenderInfo.json
客厅方案_ObjectID.json    # 仅开启 ID 时
客厅方案_MaterialID.json  # 仅开启 Material ID 时
.inprogress                   # 未完成标记
```

### 11.1 RenderInfo 最低字段

- `schema_version`
- 插件版本
- Blender 版本
- `.blend` 绝对路径及文件指纹信息
- Scene、View Layer、当前帧
- `status`: `in_progress/completed/cancelled/failed`
- 开始、更新时间和结束时间
- 渲染引擎及实际像素尺寸
- 输出格式、采样、降噪、Film 和色彩管理摘要
- 是否启用 Alpha、Object ID、Material ID
- 摄影机稳定顺序
- 每台摄影机、每个通道的状态、文件名、耗时和错误
- 已知限制和被跳过对象
- Object ID 清单文件名
- Material ID 清单文件名

### 11.2 原子写入

- 先写入同目录临时 JSON。
- 刷新并关闭文件后使用 `os.replace()` 替换正式清单。
- 创建或复用固定输出目录后立即写一次。
- 每完成一个通道或摄影机更新一次。
- 正常完成、取消和可捕获异常时更新最终状态。
- 即使 Blender 崩溃，上一份完整 JSON 仍然可读。

## 12. 任务调度架构

### 12.1 主线程原则

- 不创建长期运行的 Python Thread 操作 `bpy`。
- 使用 Modal Operator、Blender Timer 和渲染 Handler 协调任务。
- Handler 只记录完成、取消和错误信号，不直接切换摄影机、删除数据或启动下一次渲染。
- 所有 Blender 数据修改均由主线程状态机执行。

### 12.2 状态机

```text
IDLE
  → PREFLIGHT
  → ALLOCATING_BATCH
  → PREPARING_CAMERA
  → BEAUTY_RENDERING
  → WRITING_BEAUTY
  → ALPHA_PREPARING / ALPHA_RENDERING / WRITING_ALPHA
  → ID_PREPARING / ID_RENDERING / WRITING_ID
  → MATERIAL_ID_PREPARING / MATERIAL_ID_RENDERING / WRITING_MATERIAL_ID
  → ADVANCING_CAMERA
  → WRITING_MANIFEST
  → RESTORING
  → COMPLETED | CANCELLED | FAILED
```

每个状态只能做一类操作。状态转换必须集中定义，避免 UI、Handler 和输出模块各自推进任务。

### 12.3 停止语义

- 用户点击停止后设置 `cancel_requested`。
- 如果 Blender 当前渲染支持安全取消，则向渲染任务发送取消请求。
- 无法即时取消时，不再安排下一通道或下一摄影机。
- 当前回调结束后必须进入 `RESTORING`。
- “停止”不等同于回滚已保存图片；已完成文件保留，清单标记为 `cancelled`。

### 12.4 防重入

- 全局只允许一个插件任务运行。
- 开始按钮在任务期间禁用。
- 注册 Handler 时防止重复注册。
- 任务结束、插件卸载、加载新文件前都要解除 Handler 和 Timer。
- 加载新 `.blend` 时如果任务仍在运行，先请求取消并清理可安全清理的运行时状态。

## 13. 状态隔离与清理

Beauty 原场景需要保存并恢复：

- 原活动摄影机；
- 原 World 与所有被任务触及的 Light `hide_render`；
- 原当前帧；
- 原渲染输出路径及相关图像设置中确实被临时改变的字段；
- 原界面锁定状态；
- 插件注册的 Handler、Timer 和运行时引用。

辅助通道尽量通过临时 Scene 隔离，不对原对象执行材质、颜色或 Pass Index 写入。

统一清理器必须：

- 幂等，多次调用不会再次破坏数据；
- 按依赖逆序删除临时图像、对象数据、对象、集合、Scene；
- 只删除带有本次任务唯一标识的临时数据；
- 不按模糊名称批量删除；
- 正常、取消和异常都执行；
- 不自动保存 `.blend`。

插件应承诺“任务结束后不留下临时数据或永久设置变化”，但不承诺 Blender 的未保存修改标记一定保持不变，因为创建和删除临时数据本身可能使文件被标记为已修改。

## 14. 失败与覆盖策略

### 14.1 预检即停止

- `.blend` 未保存。
- 没有有效摄影机。
- 输出目录不可创建或不可写。
- 选择了不支持的输出格式。
- 开启 Multiview。
- 当前引擎不支持所选辅助通道。

### 14.2 单项失败后继续

- 单台摄影机 Beauty 失败：记录失败，不生成其 Alpha，继续下一摄影机。
- Alpha 失败：保留 Beauty，记录错误，继续 ID 或下一摄影机。
- ID 失败：保留 Beauty/Alpha，记录错误，继续下一摄影机。
- Material ID 失败：保留此前成功通道，记录错误，继续下一摄影机。
- JSON 更新失败：视为任务级严重错误，停止新渲染并清理，因为任务已无法可靠追踪。

### 14.3 已有文件

- 本轮明确计算且成功写出的同名文件自动覆盖。
- 不属于本轮计划、尚未执行或写出失败的目标保留旧文件。
- 不扫描或删除固定输出目录中的其他内容。
- 所有图片先写任务临时目录，后处理成功后使用 `os.replace()` 原子替换正式文件。

## 15. 性能原则

- Beauty 每台摄影机只渲染一次。
- 原场景已透明时 Alpha 不重复渲染。
- 原场景不透明且用户要求 Alpha 时，接受一次额外渲染以保证语义正确。
- Object ID 使用 Workbench 临时场景，渲染成本低于正常光照渲染，但可能产生较高临时几何内存。
- Material ID 同样使用 Workbench 临时场景并复制 evaluated Mesh；按摄影机完成后立即释放临时材质和几何。
- 每台摄影机完成保存后释放不再需要的像素和临时数据。
- 不同时在内存中长期保留所有摄影机结果。
- 辅助 Scene 可以在同一台摄影机的 Alpha/ID 完成后释放；是否跨摄影机复用需以不增加状态风险为前提再优化。
- 第一版优先正确性、可恢复性和像素一致性，不为了速度牺牲数据安全。

## 16. 推荐代码架构

```text
camera_batch_renderer/
├── blender_manifest.toml
├── __init__.py
├── domain.py
├── job_controller.py
├── state_guard.py
├── camera_query.py
├── naming.py
├── storage.py
├── manifest.py
├── compatibility.py
├── outputs/
│   ├── __init__.py
│   ├── base.py
│   ├── beauty.py
│   ├── alpha.py
│   └── object_id.py
├── ui/
│   ├── __init__.py
│   ├── properties.py
│   ├── panel.py
│   └── operators.py
├── tests/
│   ├── test_naming.py
│   ├── test_batch_allocation.py
│   ├── test_manifest.py
│   └── blender_integration/
├── README.md
└── LICENSE
```

职责边界：

- `domain.py`：不可依赖 UI 的任务配置、摄影机项、输出结果和状态枚举。
- `job_controller.py`：唯一状态机和任务编排入口。
- `state_guard.py`：原状态快照、恢复和临时数据登记。
- `camera_query.py`：摄影机收集、排序和稳定键。
- `naming.py`：纯函数形式的名称生成与清理。
- `storage.py`：固定输出目录、运行标记和原子文件操作。
- `manifest.py`：带版本的 JSON 模型和增量写入。
- `compatibility.py`：Blender 版本、引擎与功能能力检测。
- `outputs/base.py`：输出后端协议。
- `outputs/*`：各通道实现，不直接控制整轮任务。
- `ui/*`：只负责界面和用户命令，不包含渲染业务逻辑。

避免建立无边界的 `utils.py`；通用函数应放在拥有明确领域含义的模块中。

## 17. Extension 打包规范

Blender 4.2 以后采用 Extension 格式。ZIP 至少包含：

- `blender_manifest.toml`
- `__init__.py`
- 插件模块
- `README.md`
- `LICENSE`

Manifest 至少声明：

```toml
schema_version = "1.0.0"
id = "camera_batch_renderer"
version = "0.1.0"
name = "Camera Batch Renderer"
tagline = "Render a still image from every camera"
type = "add-on"
blender_version_min = "4.2.0"
license = ["SPDX:GPL-3.0-or-later"]
```

正式交付前执行：

```text
blender --command extension validate
blender --command extension build
```

Extension ZIP 必须在 Blender 4.2+ 完成官方验证与安装态测试；同源 Legacy ZIP 必须在 Blender 4.0.2–4.1 完成安装、启用、运行、禁用和卸载测试。

## 18. 兼容性策略

- 最低支持 Blender 4.0.2，不声明人为最高版本。
- Blender 4.0.2–4.1 使用 Legacy Add-on；Blender 4.2+ 使用 Extension。
- 兼容层集中在 `domain.compat` 或 Blender Adapter，业务模块不散布大量版本判断。
- 使用能力检测优先于只比较版本号，例如检查属性、枚举项和引擎能力是否真实存在。
- 对 Cycles 和 EEVEE 建立明确能力矩阵。
- 第三方引擎默认只尝试 Beauty；Alpha/ID 必须显式通过测试才启用。
- 最低版本、安装体系边界版本和当前 LTS/最新版本运行集成测试。
- 新发布的 Blender 版本进入支持范围前运行回归；若上游破坏 API，在兼容层修复并记录。

官方参考：

- Blender Extension 创建规范：<https://docs.blender.org/manual/en/4.3/advanced/extensions/getting_started.html>
- Blender 4.5 LTS Python API：<https://docs.blender.org/api/4.5/>
- Blender LTS 状态：<https://www.blender.org/download/lts/>
- Blender Cryptomatte：<https://docs.blender.org/manual/en/4.5/render/layers/passes.html>

## 19. 测试计划

### 19.1 纯 Python 单元测试

- 自然排序。
- 中文、Unicode、非法字符和 Windows 保留名称。
- 大小写冲突和截断后冲突。
- 完整路径预算。
- 固定输出目录的幂等准备与旧文件保留。
- 参数文件名格式。
- JSON Schema 版本和状态转换。
- Object ID 调色板碰撞处理。
- Material ID 文件命名、调色板确定性和通道动作顺序。

### 19.2 Blender 集成场景

- 1 台、多台、零台摄影机。
- 透视和正交摄影机。
- 中文及重名清理后的摄影机。
- 本地对象、链接库对象、Collection Instance。
- 修改器、Geometry Nodes 和实例。
- Cycles 与 EEVEE。
- PNG、JPEG、TIFF、OpenEXR Beauty。
- Render Border/Crop。
- 用户启用/禁用 Compositor。
- Compositor 中存在 File Output 节点。
- Film Transparent 开启与关闭。
- 半透明、Holdout、玻璃和透明边缘。
- Beauty-only、Alpha-only、Object ID-only、Material ID-only、任意组合、四者全部；四项全未选必须在创建输出前拒绝。

### 19.3 ID 精确性

- 同一对象在不同摄影机、重复任务中颜色一致。
- 保存关闭并重新打开后颜色一致。
- PNG 内部像素严格属于已声明调色板。
- 背景严格为黑色。
- 链接对象和实例具有可追踪稳定键。
- 重命名对象后允许颜色变化并在新清单中正确记录。
- Volume 被明确跳过而不是静默错误着色。
- 同一材质在不同对象和摄影机中颜色一致；同一 Mesh 的不同材质面使用不同颜色。
- 未分配材质使用非黑色 `Unassigned` 标签，Material ID PNG 只包含黑色和 MaterialID JSON 声明颜色。

### 19.4 恢复与故障注入

- Beauty 渲染失败。
- Alpha 辅助 Scene 创建或渲染失败。
- ID 临时几何复制失败。
- 图片写入失败。
- JSON 更新失败。
- 用户在各状态点击停止。
- 插件禁用时任务仍处于运行状态。
- 测试结束后无临时 Scene、对象、网格、图像、Handler 或 Timer 残留。
- 原摄影机、帧、输出设置和界面锁定状态恢复。

### 19.5 输出可靠性

- 每次任务复用同一个 `SekerRenderAllCameras/` 目录。
- 同名新图成功后替换旧图。
- 未勾选通道、已移除摄影机和未执行动作的旧图保留。
- 渲染失败或取消时，未成功替换的旧图保持可读。
- 任务崩溃后保留可读清单和未完成标记。
- 最终输出根目录不出现 staging、marker 或 `.tmp`；运行期文件只允许存在于一个固定隐藏工作目录。

## 20. 第一版验收标准

1. 已保存工程包含多台摄影机时，一次点击按所选通道生成结果；Beauty 默认开启，但允许只生成 Alpha 或任一种 ID Map。
2. 所有输出位于 `.blend` 同级 `SekerRenderAllCameras/`。
3. 文件名不包含批次前缀，同名新图覆盖而未生成的旧图保留。
4. 文件名包含 Blend 名、摄影机、通道和约定关键参数。
5. Beauty 与用户单独执行正常渲染得到的最终 Composite 内容一致。
6. 原场景透明时 Alpha 不重复渲染；不透明时通过独立渲染得到有意义的背景透明 Alpha。
7. Object ID 图只包含黑色及 JSON 声明的离散 RGB 颜色。
8. Material ID 图保留逐面材质分配，只包含黑色及 JSON 声明颜色，且不修改用户材质。
9. 同一稳定键在不同摄影机和重复任务中获得同一颜色。
10. RenderInfo 在中途异常后仍保留上一份有效状态。
11. 用户停止后已完成文件保留，清单标记为取消，并完成清理。
12. 正常、取消和可捕获异常后不留下临时 Blender 数据。
13. 插件不主动保存 `.blend`，不永久修改原对象材质、颜色或 Pass Index。
14. 只有本轮成功生成的同名输出会覆盖旧文件，其他已有文件不受影响。
15. Extension ZIP 在 4.2+ 通过官方验证并安装运行，Legacy ZIP 在 4.0.2–4.1 安装运行。
16. 有配对的 Camera 只使用指定 Light Collection/World，未配对 Camera 使用 Scene 默认，任务结束后原环境完整恢复。

## 21. 开发阶段

### 阶段 0：技术验证

- 验证目标版本中的异步单帧渲染、Handler 和 Modal 状态机。
- 验证 Render Result 的最终 Composite 与原始 Render Layer Alpha 读取。
- 验证 Film Transparent 开关下的 Alpha 行为。
- 验证临时 Scene 的生命周期和清理。
- 验证评估几何复制、链接对象和实例。
- 验证 Workbench 离屏 ID 渲染的像素精确性。
- 验证 4.0.2、4.1、4.2 安装边界与当前 LTS API 差异。

技术验证不通过时先修改设计，不进入完整 UI 开发。

### 阶段 1：Beauty MVP

- Extension 骨架和 Manifest。
- 摄影机收集与排序。
- 固定输出目录准备与临时写出。
- 命名和格式预检。
- 主线程状态机。
- 逐摄影机 Beauty。
- 增量清单和基础恢复。

### 阶段 2：辅助通道

- Alpha 条件性提取/辅助渲染。
- 隔离的 Object ID 临时 Scene。
- 稳定调色板和碰撞处理。
- Object ID JSON。
- Material ID 临时 Scene、逐面材质槽重建与 MaterialID JSON。

### 阶段 3：任务体验与可靠性

- 进度、停止和完成摘要。
- 同名覆盖与未生成旧图保留。
- 故障注入测试。
- Handler、Timer 和临时数据泄漏测试。

### 阶段 4：兼容与发布

- Blender 4.0.2/4.1/4.2 与当前 LTS 全量测试。
- Extension 与 Legacy 两种包的安装、禁用、卸载测试。
- README 和使用说明。
- 官方 Validate/Build。
- 生成可安装 ZIP。

## 22. 长期演进原则

- 保持静帧批量任务这一核心职责，不把插件扩张成通用渲染农场。
- 新输出类型通过 `outputs/base.py` 后端协议增加，不修改核心状态机。
- JSON Schema 只做向后兼容扩展；破坏性变化提升 Schema 主版本。
- 文件名模板未来可以配置，但默认模板长期保持稳定。
- 优先支持在维护期内的 Blender LTS，不追逐每日开发版 API。
- 每次支持新 LTS 都通过能力矩阵和集成场景验证。
- 后续最有价值的扩展依次为：选中/集合摄影机、Cryptomatte EXR、自定义命名模板、16-bit 数据贴图。
- 任何性能优化都必须保留状态隔离、原子清单和像素一致性测试。
