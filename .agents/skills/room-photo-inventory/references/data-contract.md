# 数据约定

objects.json 根字段：schema_version、room_id、analyzed_at、units（m）、method、images（image_id/file/status/description）、zones、assets、relationships、unknowns、excluded_transient_items。

asset：asset_id、name、category（structure/furniture/appliance/fixture）、zone_id、stability（fixed/long_lived）、evidence_image_ids、identity_confidence（high/medium/low）、geometry、dimensions、appearance、placement、modeling_notes。

dimensions：status=estimated 或 unknown；unit=m；axes 明确 width/depth/height 定义；ranges 包含三个 [min,max] 或 null；basis；confidence=low（仅凭照片时）。曲线结构注明宽度是包围盒、不是直径。绝对坐标若未知用 null。

appearance：base_color_description、approx_hex（可以多个近似色）、material_appearance、texture、roughness_hint、lighting_caveat。材质未实物验证，不把外观当作成分鉴定。

新分析还必须包含 `appearance_analysis: {schema_version:"1.0", observations_file:"material-observations.json", spec_file:"material-spec.json", validation_file:"material-validation.json"}`。颜色/纹理逐图证据、跨图决策和校验见 [color-texture-analysis.md](color-texture-analysis.md)。原 appearance 保留摘要，并用 `material_ids` 关联该资产的表面材质；床架/床品等不可用一个平均色替代。

relationship：subject/object/type/evidence_image_ids/confidence；方向关系必须在 type 或 notes 中注明观察照片。unknowns 用问题和所需补充数据描述。


## 逐图构图与关系

objects.json 增加 image_spatial_relations，另导出 image-spatial-relations.json。
每图：image_id、file、status(analyzed/unavailable)、coordinate_frame=image_viewer_left_right_top_bottom、visible_asset_count、objects、relationships、skip_reason。
objects：asset_id、name、position_in_image（左下/中间偏右等自然语言）、depth_hint（foreground/midground/background/unknown；需证据）、position_confidence、occlusion、normalized_bbox（没有实际框标注则null）。
relationships：subject_asset_id、predicate、object_asset_id、description、confidence、frame=image、evidence_image_id。谓词可为left_of/right_of/above_in_image/below_in_image/upper_right_of/in_front_of/behind_in_image/inside_recess_of/supported_by等；语义必须与当前图一致。
只有一个大件时relationships=[]且skip_reason=single_asset_no_relationships；缺图objects=[]、relationships=[]、skip_reason=source_unavailable。不要把结构泛背景或临时小件凑进数量。方位不可无条件跨视角传递。

## 家具间距

objects.json 新增 distance_estimates，另导出 furniture-distances.json；字段、三种距离口径及示例见 [distance-estimation.md](distance-estimation.md)。尺寸范围仍记录单件家具大小；距离范围单独记录家具间距，不能互相替代。逐图 relationship 可选 distance_ids 引用同一对资产的距离记录。旧 schema 可读但无字段标为未分析；新输出须包含数组（无可估数值时保留关键对的 unknown 记录与原因）。
