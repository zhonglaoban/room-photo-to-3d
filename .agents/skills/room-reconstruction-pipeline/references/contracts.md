# 输入与标注应用

Python 3（标注helper仅标准库）；扫描helper另需numpy/Pillow；Blender helper需在Blender Python中运行。所有路径通过参数/配置传入，无用户目录或日期默认值。

## 房间数据

布局协议：layout `units: m`，`assets[]` 有 `instance_id`、`asset_id`、`kind`、`position:[x,y,z]`（底部中心）、`size:[w,d,h]`、`yaw`（弧度，可选），椅子另有 `table_instance_id`。Z向上。名义尺寸不自动等于详细网格外包尺寸。

照片分析至少保存来源文件/哈希、稳定实例ID、证据图片ID、表面颜色/纹理观察、逐图相对关系和机位、同墙顺序、承托、数量状态和未知。不要要求“一房一定一床一电视”等会改变用户业务的普遍假设；只对该房源已确认的数量验收。

## review JSON

`schema`可按项目扩展；helper消费以下字段：

```json
{
  "units":"m", "reviewed":true,
  "source_sha256":"待填入当前layout文件的SHA256",
  "edits":[
    {"op":"set_size","instance_id":"desk","size_m":[1.4,0.8,0.76],"raw_user_text":"桌子1.4×0.8，高0.76米","evidence":"用户本次确认"},
    {"op":"gap","fixed":["cabinet"],"moving":["desk"],"axis":"X","side":1,"gap_m":1.1,"metric":"world_aabb_face","raw_user_text":"桌子离柜前沿1.1米","evidence":"已确认参照面"}
  ]
}
```

`set_pose` 接受 `position_m` / `yaw_deg` / `tilt_deg`；`gap` 同时平移整个moving组，必须与fixed组不同。`seating` 字段：tables（实例ID数组）、chair_asset_id、chair_size_m、per_side、floor_z_m、seed、tuck_m、jitter（tangent_m/normal_m/yaw_deg），可选replace_generated。只替换helper自己创建的椅子；既有未接管椅子会报错，不能静默丢弃。

每条记录都需要原文和证据。`reviewed:true` 表示代理已对照用户意图完成规范化，不能用它伪造用户批准。这里不自动猜测“紧贴”“左边”“差不多”的米制值。先用已有证据消除歧义；确实缺信息才询问。

```sh
python3 <skill>/scripts/layout_constraints.py --layout room/layout.json --review room/review.json --output room/layout-applied.json
```

源哈希不匹配拒绝应用，避免旧页面覆盖新布局；输出已存在默认拒绝，可明确加 `--replace-backup` 保留带时间戳备份。输出包含应用原文与限制。座椅扰动是艺术选值，helper不声称检查了全场碰撞或门前通行。

示例数值仅解释协议。每次使用当前布局版本的哈希，并按该房间证据填写尺寸。
