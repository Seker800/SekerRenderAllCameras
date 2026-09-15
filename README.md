# 全摄影机批量渲染

这是一个 Blender 插件项目：按稳定顺序批量渲染当前场景的全部摄影机，并可输出 Beauty、Alpha、Object ID 与任务清单。

当前产品定义见 [`PLAN.md`](PLAN.md)。项目知识库入口见 [`Docs/README.md`](Docs/README.md)，Agent 协作规则见 [`AGENTS.md`](AGENTS.md)，开发环境和 Blender MCP 部署见 [`Docs/tools/开发环境与插件.md`](Docs/tools/开发环境与插件.md)。

## 目录约定

```text
camera_batch_renderer/  # 可安装的 Blender 插件包
tests/                  # 不依赖 Blender 的单元测试与 Blender 集成测试入口
scripts/                # 开发、验证和打包脚本
Docs/                   # 架构、实现事实、流程、工具、决策与过程产物
```

插件代码尚未实现时，这些目录由各自的 `README.md` 先定义责任边界；实现不得绕过文档中登记的所有权和适配层。
