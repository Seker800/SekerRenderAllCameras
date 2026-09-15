# Blender 命令行与后台验证

普通纯规则测试使用系统 Python；需要 `bpy` 的集成测试使用目标 Blender 可执行文件。

典型入口：

```powershell
blender --background tests/fixtures/minimal.blend --python scripts/run_blender_tests.py
```

- 后台模式不等价于 GUI：Panel、区域上下文、modal operator 与视觉进度必须另做 GUI 验收。
- 命令必须指定仓库内可重建的测试文件，不对用户生产 `.blend` 执行自动化。
- 脚本必须以非零退出码报告失败，并在异常时输出测试名和最小堆栈。
- 不用后台测试自动覆盖 fixture；更新 fixture 是独立、可审查的任务。
