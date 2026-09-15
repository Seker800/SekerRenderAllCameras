---
name: project-new-feature
description: "Use when adding a feature to the Blender camera batch renderer."
---

# New Feature Workflow

1. Read `AGENTS.md`, `Docs/README.md`, and applicable architecture documents.
2. Read `Docs/workflow/我要加入新功能.md` and the nearest target-directory `README.md`.
3. Identify the owner, truth source, target Blender version, reusable implementation, tests, state-restoration impact, and documentation impact.
4. Keep domain rules free of `bpy`; cross boundaries only through the registered Coordinator/Adapter.
5. Verify with pure Python, Blender integration, GUI/MCP, failure, cancellation, and restoration checks as appropriate.
