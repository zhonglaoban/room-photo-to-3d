# 输入与场景约定

## 消费既有输入，不重写观察

本项目上游格式：
- `images-manifest.json` 与 `objects.json.images`：实际图片 file/status、原 URL、缺图状态。
- `objects.json.assets`：asset_id、zone_id、证据 image_id、几何、尺寸 ranges、外观、placement、modeling_notes。尺寸 axes 有明确含义；未知为 null。
- `image-spatial-relations.json.images[]`：每图 objects[] 与 relationships[]（subject_asset_id、predicate、object_asset_id、frame=image、evidence_image_id）。两端须存在同图，单物品 relationships=[]。
- `layout-candidate.json`：可选的假设区域和布局。旧项目 `regions.bounds` 为 `[xmin,ymin,xmax,ymax]`，不要误认为下面的 bounds_min/max 三维格式。转换时写明轴与单位。

原始文件只读保留。物品名、材质别名可归一化但不改变稳定 ID。源清单有 32 项不代表每个场景必须恰有 32 个网格；墙、窗帘等可能跨区域复用，床是多个零件组成的一个资产。

## scene-spec.json（本 skill 版本 1.0）

`assets/scene-spec.example.json` 是可执行空壳示例，所有尺寸为假设。按本次实际场景替换：

- schema_version、room_id、units=m、coordinate_frame=blender_xyz_z_up。
- main_room：净空 `bounds_min:[xmin,ymin,zfloor]`、`bounds_max:[xmax,ymax,zceiling]`，wall_thickness_m；`provenance` 标 measured / inferred / assumed。
- central_camera：name、eye_height_m（相对地面）、mode=human_eye / geometric_center、heading_degrees（0 看 +Y，90 看 -X；Blender Z 轴右手正旋转），不以照片左右推导全局轴。眼高需小于房间高度。
- envelope_objects：所有外壳对象名（墙、地、顶及外部门窗关闭件）；内部隔墙不要冒充外壳去掩盖漏墙。
- asset_bindings：`{asset_id, objects:[...], disposition:modeled/omitted, reason, evidence_image_ids}`。omitted 必须解释（如临时小件不建、证据缺失），不能默默掉资产。
- assumptions：带 ID 的假设、依据和受影响资产；conflicts：证据冲突、选择及待补资料。
- openings：id、host_wall、kind、dimensions、center、closure_object、evidence、status。几何开口与关闭件是两回事，内部门洞可无门；外部敞开须记录例外。
- relation_checks：来源 image_id、约束、对应相机/解析几何检查方法、PASS/WARN/FAIL/UNKNOWN 与理由。

校验器使用主房净空、相机、envelope_objects、asset_bindings 和已配置的尺寸/距离约束；其他字段给模型构建和人工审阅使用。多区域采样、自定义敞开外口、门洞形状、摆门、家具碰撞需扩展；不能删掉失败检测来适配场景。

## 场景组织与元数据

建议 COL_Envelope、COL_Partitions、COL_Openings、COL_Furniture、COL_Fixtures、COL_Lights、COL_Cameras、COL_References；可沿用已有命名并写映射。外壳 `room_role=envelope`，家具 `asset_id=Axxx`；配置是映射来源，属性作为辅助，不能靠名称猜材质或识别所有碰撞。

嵌入 `SOURCE_objects.json`、`SOURCE_image-spatial-relations.json`、`SCENE_SPEC.json`、`START_HERE`；文件不存在则如实注明，不能创建伪原始数据。图片打包只代表可移植性，不代表已做照片匹配。外壳无需合并成单 mesh；每个实体厚板正常外向法线，室内面朝室内。

## 家具距离与尺寸（v1.1 增补）

新增 furniture-distances.json 输入、inventory_file / distance_estimates_file 来源路径、dimension_constraints 和 distance_constraints，详见 [distance-driven-layout.md](distance-driven-layout.md)。源文件相对 scene-spec 路径解析；validate_scene 输出源 SHA256、实际值、目标与偏差。旧配置仍可读，但缺来源不算已校验距离。新的建模任务须消费上游距离数据，或明确未估/冲突原因。
