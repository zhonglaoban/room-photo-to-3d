# 验收与可复现交付

## 最低交付检查

1. 用新 Blender 进程重新打开最终文件。米制 scale_length=1；活动相机为配置的中央相机，眼高和 XY 中心匹配；画面可正常渲染，无缺图。
2. 外壳的墙/地/顶和外部关闭件存在，有限正尺寸，默认视图/渲染都可见，没有隐藏 collection、View Layer 排除、局部视图或透明 camera-ray 设置造成缺墙。检查实际 evaluated mesh，不只统计对象名。
3. 对外壳做多点/多高度采样射线；这是漏墙筛查，不是连续水密证明。补充角部、板缝、门窗边缘的近景和解析/网格检查。窗玻璃是几何边界但可透光，不能把“无漏光”等同“封闭”。
4. 门窗开口中轴应穿过原宿主墙，射线对宿主墙应不命中；相邻实墙采样应命中。外窗 glass/入户门关闭件另测，不能测试整个 scene 的 hit 来误报开口堵塞。
5. 中央相机不在家具/灯具/墙体中，近裁切不切入；中央四向 PNG 来自同坐标，仅朝向变化。照片匹配相机可不同，不替代中央机位。
6. 按 asset_id 查覆盖率/数量，逐条检查源图引用。承托/包含用解析或 evaluated mesh；普通 AABB 只给候选相交，不直接给实质穿插 FAIL。
7. 有已锚定方向的同墙顺序应相符。投影点需位于相机前方和视锥内；屏外、不清晰、遮挡未验证或相机未标定时保留 WARN/UNKNOWN，不写精确匹配 PASS。全局卫生间位置没有证据时保持 UNKNOWN。
8. 验证入口到主活动区/床侧/卫生间的路径。身体尺寸、检测高度、步高和网格精度写入结果；未模拟重力、门扇或台阶须说明。几何闭合/外壳存在不能替代可达性。
9. 最终工程与配置/校验数据同版本。构建或修正后重导布局数据，不复用旧几何的 PASS。每条 JSON 检查写 status、method、result、limitations。

## 随附工具的运行方式

在独立后台进程创建空壳（先编辑示例配置，输出文件必须不存在）：

```sh
"/path/to/blender" --background --factory-startup --python /path/to/skill/scripts/create_room_shell.py -- --config /path/to/scene-spec.json --output /path/to/new-room.blend
```

只读检查已保存工程，JSON 输出文件须为新文件：

```sh
"/path/to/blender" --background /path/to/room.blend --python /path/to/skill/scripts/validate_scene.py -- --config /path/to/scene-spec.json --output /path/to/validation.json
```

Blender CLI 可按环境加 `--python-exit-code 1` 让未捕获异常返回非零。校验 JSON 的 overall 才是结果依据，不能只读进程是否结束。

工具限定主房矩形净空；射线只使用配置外壳，避免家具遮挡掩盖漏墙。相机家具净空、门窗形状、镜像关系、表面最小净距与路径仍需专门验证。对多房间、异形边界及已观察外部敞开口扩展方法并记录适用范围，不能把不适用当 PASS。

## 输出结构

`room.blend`、`scene-spec.json`、可复现构建脚本、`asset-map.json`（或配置内映射）、`validation.json`、`previews/center-{north,east,south,west}.png`、可选 `previews/cutaway.png`、可编辑 `model-review.html`。大体量原图可保留同目录资源，但 .blend 所需引用应打包。

如需 HTML 报告，按当前工程的格式与编辑要求交付。浏览器文字调整不会自动改 JSON 或 .blend，必须在报告中标明；校验状态是本次快照，后续改模型要重跑。

## 尺寸与家具间距验收

核对原始 furniture-distances.json 与 objects.json 的 distance_estimates 一致，记录其文件版本/哈希。每个有数值来源均须有应用或未解决说明；检查模型选定大小落在源 dimensions.ranges 内，并从最终几何以相同参照/metric 回测距离区间。报告给出 source_distance_id、目标、实际、偏差、状态和理由。未知不算 PASS，冲突/unresolved 给 WARN；区间不符给 FAIL 并说明软约束取舍。

随附检查器可校验已绑定对象局部轴尺寸和参考点距离；不自动推断尺度、不求解家具摆放、不认证曲面最小距离。大小/摆放必须由具体构建脚本消费源范围，不能依赖校验器代为建模。
