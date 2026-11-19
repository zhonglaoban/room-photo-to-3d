# 详细模板、实际网格与渲染

配置顶层：`units:m`、`project_root`（相对配置文件）、`layout`（相对project_root）、`scene`、`bindings`、`qa` 和可选 `render`。源.blend由Blender命令加载，不在脚本里硬编码或清空。

## bindings

每项有instance_id、root（场景EMPTY名）、origin（目前只支持明确bottom_center）、source_forward和layout_forward（+X/-X/+Y/-Y）。root不存在时可给template_root从静态EMPTY/MESH子树克隆。源模板原点/前向必须先从实际几何确认；旋转适配只做一次，避免再次把椅子转反。

尺寸同步是显式可选：resize=true时给template_size_m（未缩放局部尺寸）和layout_size_axes（局部XYZ对应layout的尺寸索引排列）。没有resize只同步位置/方向，在结果中标size_applied=false。不要整体压缩复合设备去代替部件比例重建。

可给tilt_child在该根对象内控制俯仰，读取layout tilt。不要把吊杆跟屏幕一起俯仰。helper只处理配置的静态实例，不重建墙、不删除缺失资产；未绑定实例列在结果中。

## qa

- chairs：root_pattern、expected_count、mesh_pattern、back_height_fraction、seat_height_fraction（按该椅名义高度归一化的顶点区间）、minimum_dot、minimum_back_extra_m。由实际网格计算正面、椅背/坐面到旋转桌面的距离，允许座位收在桌下。根据实际椅子模板配置区间和阈值。
- supports：object、surface、surface_shape=rectangle、tolerance_m；containment=true检查投影是否在矩形支撑面范围，check_contact=false可仅验托盘等部件的平面范围。只支持水平矩形承托面，其他形状需专门检测。
- parallel_panels：a、b对象名、normal_local（如[0,-1,0]）、max_angle_deg，校验屏幕与框的真实法线。
- counts：pattern、type（如EMPTY）、expected。按实例根对象计数，不按零件数量。

0匹配、缺少ID、空顶点探针、错误前向都会失败；没配置任何检查为UNKNOWN。`--negative-probe` 在内存临时反转一把已通过的椅子，检查必须拒绝，finally恢复，不保存测试状态。

```sh
blender --background source.blend --python-exit-code 1 --python <skill>/scripts/blender_pipeline.py -- qa --profile room/profile.json --output new-qa.json --negative-probe
blender --background source.blend --python-exit-code 1 --python <skill>/scripts/blender_pipeline.py -- sync --profile room/profile.json --output new-room.blend --negative-probe
```

sync只写新文件；配置检查不通过不保存。不修改源工程；从新文件另跑qa验证保存结果。

## render

render含samples、adaptive_threshold、width/height、view_transform、look、exposure、device（CPU或METAL）、views（camera、file及可选scene/width/height）。只使用源工程中存在的相机，不改动房间几何；PNG输出目录必须为空或不存在。

```sh
blender --background new-room.blend --python-exit-code 1 --python <skill>/scripts/blender_pipeline.py -- render --profile room/profile.json --output new-renders
```

先小尺寸/低采样试图，再按目标设备和用途选正式质量。主场景完整墙地顶，剖切使用独立scene；中央四向应同坐标仅转向。manifest记录源.blend指纹和逐视图完成状态，中断时不能冒称全部交付。AgX/曝光与网页色调映射分开验收。
