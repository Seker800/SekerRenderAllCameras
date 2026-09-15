# Docs Knowledge Base

本目录是项目知识库入口。同一条知识只维护在一个权威位置。

## 知识地图

- 项目概览：[`../README.md`](../README.md)
- 产品基线：[`../PLAN.md`](../PLAN.md)
- Agent 入口：[`../AGENTS.md`](../AGENTS.md)
- 长期架构：[`architecture/`](architecture/README.md)
- 当前实现：[`reference/`](reference/README.md)
- 工作流：[`workflow/`](workflow/README.md)
- 工具与 Blender MCP：[`tools/`](tools/README.md)
- Git 提交：[`Commit规范.md`](Commit规范.md)
- 架构决策：[`我的决策/`](我的决策/README.md)
- 变更历史：[`changelogs/`](changelogs/README.md)
- 过程产物：[`过程产物/`](过程产物/README.md)

## 使用规则

- 长期规则和系统边界从 `architecture/` 获取，不从旧计划或代码注释拼凑。
- API、路径、目标版本与已落地行为从 `reference/` 和代码获取。
- 操作步骤、诊断和验收从 `workflow/` 与 `tools/` 获取。
- `.agents/skills/` 与 `.claude/skills/` 只包装高频流程；`Docs/workflow/` 始终是真相源。
