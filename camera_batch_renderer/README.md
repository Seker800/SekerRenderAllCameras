# camera_batch_renderer

可安装 Blender 插件包。实现时按以下目录分层：

- `domain/`：无 `bpy` 的纯规则和值对象。
- `application/`：任务用例、状态机与协调。
- `blender/`：Blender API、渲染和状态事务适配。
- `infrastructure/`：文件系统、JSON、日志和时钟。
- `presentation/`：Properties、Panel、Operators 与注册。

根 `__init__.py` 只负责插件元数据和对称注册，不承载业务逻辑。
