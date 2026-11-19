# 使用照片距离共同设定模型大小与位置

## 读取与求解

读取 furniture-distances.json、objects.json 的 dimensions.ranges、逐图方向关系，不能只读距离文本。将 `inventory_file` 与 `distance_estimates_file` 写入 scene-spec.json（路径相对配置文件）；保留原始输入，校验读取实时来源并在结果记录 SHA256。

1. 用可用尺度锚点确定米制比例；在每件家具尺寸区间内选择体块尺寸，记录 source_dimension 与 target_m。
2. 用门窗连接、同墙顺序、承托/包含约束确定区域、朝向与相机方向。距离是标量，单条距离不能唯一确定方向或整个户型。
3. 用家具间距区间确定位置，同时满足房间边界、避免穿插与中央机位净空。在无真实绝对方位时允许整组旋转/平移，不能镜像已确认关系。
4. 若所有区间不能同时满足，先识别冲突及共同尺度误差；保留直接测量/明确规格，低置信度照片估计作为软约束。记录哪条未满足及原因，不擅自修改源区间或把未知补成“已估算”。
5. 从最终 evaluated geometry 重新量同一参照部位，报告源区间、选定目标、实际值及偏差；先粗模求解、后细化，模型变更重测。

示意（非本房源事实）：两件家具沿 X 并排且局部轴与 X 对齐，A 宽选 2.0 m、B 宽选 0.8 m，边缘净距源区间 0.4–0.7 m，目标取 0.55 m，则中心距为 2.0/2 + 0.55 + 0.8/2 = 1.95 m。建模先设大小，再将 B 中心放在 A 中心右侧 1.95 m。若改 A 大小，则 B 位置需重算。对旋转家具需投影相应半尺寸，曲线/凹区用真实轮廓；不能套用同轴盒公式。

从同一“假设床宽”推导的多条距离并非独立尺度证据，不重复加权使误差虚假缩小。可采用约束求解器或确定性解析布局，不规定某一种算法，但构建脚本必须实际消费这些输入，禁止先写死坐标再添加名义上的 distance 字段。

## scene-spec 扩展

- `inventory_file`：objects.json。
- `distance_estimates_file`：furniture-distances.json（schema_version 1.0、units m、room_id 与配置一致）。
- `dimension_constraints[]`：`{asset_id, object, axis:"X"/"Y"/"Z", source_dimension:"width"/"depth"/"height", target_m}`。源范围直接读取 dimensions.ranges；object 应是覆盖该尺寸的最终整体/主组件，不能用床腿宽度代替整床宽度。脚本评估对象局部轴包围尺寸，换算父级/缩放后的米制值；复合资产需合适的整体代理或额外聚合方法，别随意选零件冒充整体。
- `distance_constraints[]`：`{source_distance_id, state:"applied"/"unresolved", selected_target_m, subject_anchor, object_anchor, reason}`。source ID 必须存在；每个数值来源都须有 applied 或 unresolved 的显式记录，不能静默跳过。未知距离可不绑定，但须保留 UNKNOWN。
- anchor：`{object, mode:"local_point"/"bbox_center", local_point_m:[x,y,z]}`。local_point_m 是对象局部坐标数值，按 matrix_world 转到世界坐标；在 scale=1 时等于局部米，若对象未应用缩放需按真实局部坐标填写，不能把 world 点填入。bbox_center 为 evaluated mesh 局部包围盒中心转换到世界，不是对象 origin。

本检查器支持 reference_distance_xy、center_distance_xy、vertical_gap，使用来源记录 metric，不能为迁就模型改成其他距离口径。center_distance_xy 要求两个 anchor 都为 bbox_center。vertical_gap 为 object.z - subject.z，不能取绝对值掩盖上下颠倒。reference_distance_xy 的 local point 须由实际几何参照部位导出，尺寸变化后重算；它验证指定点的间距，不认证最近表面距离或整条通道最窄净宽。

```json
{
  "inventory_file": "../input/objects.json",
  "distance_estimates_file": "../input/furniture-distances.json",
  "dimension_constraints": [
    {"asset_id":"SOFA", "object":"SM_Sofa_Body", "axis":"X", "source_dimension":"width", "target_m":2.0}
  ],
  "distance_constraints": [{
    "source_distance_id":"D_SOFA_TABLE",
    "state":"applied",
    "selected_target_m":0.55,
    "subject_anchor":{"object":"SM_Sofa_Body", "mode":"local_point", "local_point_m":[1.0,0,0]},
    "object_anchor":{"object":"SM_Table_Top", "mode":"local_point", "local_point_m":[-0.4,0,0]},
    "reason":"示意：沿同一X轴放置，两点代表相向边沿"
  }]
}
```

数值与 ID 仅示意，不可复制成任何真实房源证据。完整场景仍需主房/外壳/中央相机等已有字段。空壳工具不求解家具，仍只建六面壳；具体家具构建器负责按所选尺寸、朝向和距离计算位置。

## 校验结果语义

validate_scene.py 会检查已配置来源下的尺寸和间距，输出目标、实际、区间及偏差；源记录缺绑定/同 ID 多绑定、源数据与 room_id 不符、无尺度却有数值等不得写 PASS。数值落在估计区间内只说明“模型满足所选照片估计”，不认证现场真实距离。unknown 为 UNKNOWN，unresolved/冲突为 WARN，不算通过；模型外壳完整、中央相机、关系/通行等其他验收仍保留。

旧配置缺少上述来源时照常可读，输出 not_checked 中明确缺少尺寸/间距校验；旧数据不会自动产生估算，需要上游新一轮照片分析后再建模。
