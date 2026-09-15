---
name: project-new-feature
description: "Use when adding a feature to the Blender camera batch renderer."
---

# New Feature Workflow

Follow `Docs/workflow/我要加入新功能.md`. Keep domain logic free of `bpy`, use the registered adapter boundary, and verify temporary Blender state is restored on every exit path.
