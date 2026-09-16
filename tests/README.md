# Tests

- `unit/`：系统 Python 可运行的 Domain/Application 测试。
- `architecture/`：导入方向、`bpy` 隔离和唯一 Adapter 门禁。
- `blender/`：目标 Blender 中运行的集成与恢复测试。
- `fixtures/`：最小、可重建的 `.blend` 和预期数据。

真实用户文件和渲染输出不得作为 fixture 提交。

完整工况矩阵、发布阻断条件与唯一执行入口见
[`../Docs/workflow/测试范围与发布验收矩阵.md`](../Docs/workflow/测试范围与发布验收矩阵.md)
和 [`../Docs/workflow/全量测试流程.md`](../Docs/workflow/全量测试流程.md)。
