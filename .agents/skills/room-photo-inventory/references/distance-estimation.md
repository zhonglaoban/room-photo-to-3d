# 家具间距估算与建模交接

## 估什么、怎样估

在既有逐图相对位置分析之外，默认分析关键家具对的间距：床与柜/床侧通道、沙发与茶几、桌与座台凹区边缘、柜与相邻家电等。每条记录指明参照部位，区分边缘间距与中心距；只做布局重要且有线索的对，不生成全体两两组合。家具到墙/门也可用同一结构记录，但墙/门须有稳定 asset_id。

先找尺度锚点，优先级为现场测量、明确型号/规格、同平面可识别物体的合理尺寸范围。仅“常见床宽/瓷砖尺寸”属于假设尺度，写明该假设，估算仍为低置信度。能观察到同一地平面时，可用透视校正后的比例；有可靠同深度/近似正面条件时可用同平面比例。没有这些条件不能简单用像素比例跨深度换算米数。若确实使用像素测量，保存实际选点/校正方法，不伪造标注。

估算要同时计入尺度锚点范围、透视、遮挡和未知边缘的误差。普通未标定照片只给粗区间（如 0.4–0.7 m），不输出伪厘米精度或虚假统计置信区间。看不全参照端点、无可信尺度、镜像反射无法排除时 range_m=null、status=unknown，并记录需要补拍或测量的位置。不能把“建议留 0.8 m 通道”写成“照片估计 0.8 m”。

多图同一对可交叉核对，但先统一 metric、参照部位和证据，不能平均不同口径。区间冲突时保留各条原始记录并填 conflict_group；不得强取无交集区间或静默折中。单物体图片不新增该图的 pair-distance 记录；跨图推断须明确标 inferred，不能伪称同图可见。

## 输出契约（distance_estimates v1.0）

在 `objects.json.distance_estimates` 保存数组；同时导出 `furniture-distances.json`：
`{schema_version:"1.0", room_id, units:"m", distances:[同一数组]}`。
两份记录必须一致；清单中没有该字段的旧版本应识别为“未分析间距”，不能解释成所有间距为零。逐图 relationships 可用 distance_ids 引用对应记录；缺图或单物体图不得附带该图测得的家具对间距。

每条记录：
- distance_id：稳定且唯一；subject_asset_id / object_asset_id：不同资产 ID。
- metric：`reference_distance_xy`（明确参照点之间的水平距离）、`center_distance_xy`（指定家具整体或指定组件的包围盒中心间水平距离）、`vertical_gap`（object 参照点在 subject 参照点上方的垂直净距，保留上下顺序）。不把欧氏 3D 距离、中心距、最窄通道和边缘间距混用。
- subject_reference / object_reference：可复现的部位说明；如“沙发前沿中央地面投影”“茶几靠沙发一侧边沿中央地面投影”。reference_distance_xy 不自动等于整条通道的最小净宽。曲面/凹区要描述具体断面，无法用本口径表达时另记方法，不硬塞为中心距。
- status：estimated / measured / unknown；range_m：[min,max]，米、0≤min≤max；unknown 时为 null。照片估算不可写成 measured。
- confidence：low / medium / high / unknown；普通未标定照片估算为 low；high 必须有相应直接测量证据。
- evidence_image_ids：成功取得的源图 ID；provenance：observed / inferred / measured。距离数值从照片推断通常是 inferred，即使两物体本身可观察。
- method：coplanar_ratio / rectified_floor / visual_range / direct_measurement / unknown；basis：推导和不确定性说明。
- scale_reference：`{kind:measured_anchor/documented_product/assumed_typical_size/none, description, range_m:[min,max]或null, source}`；kind=none 时禁止输出数值。direct_measurement 可用 measured_anchor；source 填实际来源说明，不必伪造 URL。
- measurement_source：现场实测或用户明确提供的数据来源；非实测时可 null。
- conflict_group：无冲突为 null；有冲突为共享分组 ID，另说明冲突。

示意数据仅用于说明格式，不是本工程房源的测量结果：

```json
{
  "distance_id": "D_SOFA_TABLE",
  "subject_asset_id": "SOFA",
  "object_asset_id": "TABLE",
  "metric": "reference_distance_xy",
  "subject_reference": "沙发前沿中央的地面投影",
  "object_reference": "茶几靠沙发侧边沿中央的地面投影",
  "status": "estimated",
  "range_m": [0.4, 0.7],
  "confidence": "low",
  "evidence_image_ids": ["IMG_EXAMPLE"],
  "provenance": "inferred",
  "method": "visual_range",
  "basis": "示意：同一近似地平面上的间距，以假设沙发宽度范围作尺度；包含透视误差",
  "scale_reference": {"kind":"assumed_typical_size", "description":"示意沙发宽度", "range_m":[1.8,2.2], "source":"常见尺寸假设，需核对型号"},
  "measurement_source": null,
  "conflict_group": null
}
```

## 交接与校验

运行 `python3 scripts/validate_distances.py 房源目录` 检查 ID、单位、范围、尺度依据与双份记录一致性；它不替代照片量距本身。`validate_inventory.py` 在发现新字段/文件时也执行这些检查。报告展示参照部位、估算区间、依据、置信度、UNKNOWN 和冲突，修改报告不改源 JSON。

交给 room-inventory-to-blender 时同时提供家具自身 dimensions.ranges 和 furniture-distances.json。建模使用尺寸区间与距离区间共同设定大小/位置；不能独立随机摆放后只把估算文本放进说明。
