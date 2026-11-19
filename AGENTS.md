# 室内重建项目约定

处理室内照片分析、候选户型、Blender 建模、模型同步、实际网格校验或渲染时，先阅读 [.agents/skills/room-reconstruction-pipeline/SKILL.md](.agents/skills/room-reconstruction-pipeline/SKILL.md)，按任务选择阶段。

- 原始图片和尺寸数据是证据。将可见事实、用户确认、建模假设和未知分别记录。
- 处理照片用 `room-photo-inventory`，从清单建模用 `room-inventory-to-blender`。
- 优先复用已有证据、用户确认和可编辑工程。另存新的 Blender 文件并重开检查。示例布局及尺寸只用于示例。
- 按需使用项目 Agent `room_reconstruction`。源图片、扫描数据、Blender 工作文件和输出默认保存在本地。
