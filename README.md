# 全摄影机批量渲染

这是一个 Blender 插件项目：按稳定顺序批量渲染当前场景的全部摄影机，并可输出 Beauty、Alpha、Object ID 与任务清单。

当前产品定义见 [`PLAN.md`](PLAN.md)。项目知识库入口见 [`Docs/README.md`](Docs/README.md)，Agent 协作规则见 [`AGENTS.md`](AGENTS.md)，开发环境和 Blender MCP 部署见 [`Docs/tools/开发环境与插件.md`](Docs/tools/开发环境与插件.md)。

## 目录约定

```text
camera_batch_renderer/  # 可安装的 Blender 插件包
tests/                  # 不依赖 Blender 的单元测试与 Blender 集成测试入口
scripts/                # 开发、验证和打包脚本
examples/               # 可直接打开的双摄影机验收场景
Docs/                   # 架构、实现事实、流程、工具、决策与过程产物
```

Beauty、Alpha 与 Object ID 三通道批量渲染已经可用。输出默认位于 `.blend` 同级的 `RenderOutput/<批次>/`。

## 安装与使用

1. 在 Blender 4.5 LTS 或 5.2 LTS 中打开 `Edit → Preferences → Get Extensions`。
2. 通过右上角菜单选择 `Install from Disk`，安装 `dist/camera_batch_renderer-0.1.0.zip`。
3. 保存 `.blend`，在 `Output Properties → Render All Cameras` 中选择批次前缀与可选通道。
4. 点击 `Render All Cameras`；可在运行期间点击 `Cancel Batch` 协作式停止。

可直接打开 `examples/RenderAllCameras_Demo.blend` 体验完整流程。该场景包含两台摄影机，
默认一次生成 2 张 Beauty、2 张 Alpha、2 张 Object ID，以及对应的 RenderInfo/ObjectID 清单。

开发验证：

```powershell
python -m unittest discover -s tests/unit -v
python -m unittest discover -s tests/architecture -v
blender --background --factory-startup --python scripts/run_blender_tests.py
powershell -ExecutionPolicy Bypass -File scripts/build_extension.ps1
```
