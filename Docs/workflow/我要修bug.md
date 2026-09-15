# 我要修 bug

- 写清 Blender 完整版本、插件版本、最小 `.blend`、复现步骤、预期与实际结果。
- 先判断缺陷属于 Domain、Application、Blender Adapter、Infrastructure 还是 Presentation。
- 若 Blender 正在运行且 MCP 可用，先做只读现场检查；不要在用户文件上直接试验修复。
- 以最小改动修复根因，不通过吞异常、额外全局状态或跳过恢复让表面流程通过。
- 增加能先失败后通过的回归测试，并覆盖相邻的取消、单通道失败和状态恢复风险。
- 按 `全量测试流程.md` 验证；当前事实或诊断入口改变时更新文档。
