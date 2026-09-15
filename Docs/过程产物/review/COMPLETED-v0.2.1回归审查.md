# v0.2.1 回归审查

- 日期：2026-09-15
- 范围：Blender 4.0.2+ 兼容改动、双安装包、渲染/取消/恢复、发布下载
- 结论：未发现渲染功能回归；发现并修复 Legacy ZIP 目录时间戳导致的非确定性构建

## 影响面

- 运行时代码只改变 Python 3.10 枚举兼容、UTC 时区写法和版本元数据。
- Coordinator、渲染循环、Alpha/Object ID、取消语义和状态事务没有改动。
- 安装面新增 4.0.2–4.1 Legacy 包；4.2+ 保持官方 Extension 包。
- GitNexus 本地仓库尚未建立索引，因此使用 Git diff、调用搜索、架构门禁和真实 Blender 矩阵测试完成影响复核。

## 发现与修复

- v0.2.0 Legacy 包连续构建时 SHA-256 不同。
- 逐文件哈希证明发布包与重建包的 30 个文件内容完全相同，差异仅为 ZIP 目录项时间戳。
- v0.2.1 使用固定文件顺序、时间戳、权限和无压缩归档，连续构建得到相同字节。
- 新增版本面一致性、Python 3.10 API 边界和 Legacy 可重复构建自动测试。

## 验证结果

- 16 个纯 Python 单元测试通过。
- 5 个架构门禁通过，Ruff 全部通过。
- Blender 4.0.2、4.1.1、4.2.0、5.2.1：双 Camera Beauty/Alpha/Object ID、透明 Alpha 复用、取消、故障清单、状态恢复、注册清理全部通过。
- Blender 4.0.2/4.1.1：隔离用户目录中的 Legacy 安装、启用、N 栏/Output 面板、禁用和移除通过。
- Blender 4.2.0/5.2.1：隔离用户目录中的 Extension 安装及演示场景六图真实渲染通过。
- Extension 官方 manifest 验证与构建通过；两个 ZIP 连续构建哈希一致，且无缓存、Git、RenderOutput 或备份文件。

## v0.2.1 产物

- Extension SHA-256：`EBB28EDAA2224958C9133B0AED3C7522C1E1CB24F756EBB6AF67B7337CD9C0BA`
- Legacy SHA-256：`205CA1D37E7257C48023957E33D18ADF8C4C8A37ED21ABB13F19E6066C79A0D3`

## 剩余边界

- “4.0.2+”不代表能够预先验证尚未发布的 Blender；新版本仍需执行相同矩阵门禁。
- Blender 5.2 对演示场景生成脚本的 `Material.use_nodes` 给出 Blender 6.0 弃用提示，但插件运行时代码不调用该 API，不影响当前支持范围。
- 第三方渲染器仍只默认保证 Beauty；Volume 仍不进入 Object ID。
