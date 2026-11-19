# 照片颜色、纹理与建模材质交接 v1.0

## 识别与决策

先看全部图，再核对每种主要表面的原图局部：墙地顶、门框/柜体、沙发、床架/床品、窗帘、石材、卫浴/家电。为每个稳定资产列出主要表面；被遮挡或分辨率不足的表面保留 unknown，不根据其他房源补造。本轮输出必须覆盖全部资产，复合资产允许多个材质。

逐图观察先于跨图选择：记录观察色的名称与近似 sRGB 色卡、光照条件、是否受阴影/高光/混光影响。优先无强阴影或反光的漫反射区域，多取能代表主体的局部，排除拼缝、镜中反射、邻物串色和窗外。只有真的选区并计算了像素才用 roi_statistics；目测必须写 visual_estimate，不虚构框、样本数或统计色差。原始像素是该图成像颜色，不能直接认作材质 Base Color。

跨图对比同一 asset_id/surface_id，先判断是否属于同一表面、相机曝光/白平衡是否可比，再选有代表性的颜色范围和纹理，不把暖灯图与日光图机械平均。保留差异、选用证据与排除理由。没有校色卡、RAW 或可靠照明标定时，建模用基础色是候选值，状态为 modeling_assumption；实物材质与真实反射率仍未确定。数值色差只有在色彩空间、白平衡和可比区域一致时才有意义；不要用所有房源共用的固定 RGB/色差阈值冒充准确性校验。

纹理应区分外观类别与图案：木纹可为 straight_grain/wavy_grain/ring_grain，布料可为 weave，石材可为 speckled/veined，另有 plain/geometric/other/unknown。记录可见方向、疏密、对比度、拼板/砖缝、哑光/亮光外观。图片中的方向不是世界坐标；纹理尺寸只有尺度锚点支持时才给米制范围。看不到细纹时选择“未分辨/低对比”，不能凭材质名字创造显眼图案。

候选材质必须符合证据：照片是直木纹/素面，不得变成波浪/高反差纹；颜色不能无依据从浅暖木色换成深红棕。高光、阴影、褶皱投影和拼缝不是一张可平铺凹凸贴图。粗糙度、微表面法线与高度数值作为后续建模假设选择；不要把带明暗的颜色图直接强力接入 Bump。连续地面需在建模时统一方向、比例和 UV 起点，并检查平铺边界。

## 机器可读文件

`material-observations.json`：

```json
{
  "schema_version": "1.0",
  "room_id": "当前房源ID",
  "color_space": "sRGB",
  "observations": [{
    "observation_id": "OBS_FLOOR_01",
    "image_id": "IMG_01",
    "asset_id": "FLOOR_LIVING",
    "surface_id": "finish",
    "region": {"method":"visual_only", "bbox_normalized":null, "description":"沙发前未被地毯覆盖、无明显阴影的地面"},
    "color": {"method":"visual_estimate", "description":"浅暖木色", "approx_hex":["#B69368"], "lighting":"daylight", "bias_notes":"示意近似色；未经实物校色", "confidence":"low"},
    "texture": {"material_appearance":"外观类似木地板，不能确认实木或木纹饰面", "pattern":"straight_grain", "direction_in_image":"由画面下方朝走廊纵深", "contrast":"low", "scale_range_m":null, "scale_basis":null, "finish_appearance":"matte", "confidence":"medium"}
  }]
}
```

以上仅说明格式，不是某房源已分析的事实。颜色未知时 method=unknown、approx_hex=[]、confidence=unknown，说明原因。纹理未知时 pattern/direction_in_image/contrast/finish_appearance 可写 unknown，confidence=unknown。

region.method 为 visual_only 或 annotated_bbox；后者 bbox_normalized=[x0,y0,x1,y1]，0≤x0<x1≤1、0≤y0<y1≤1，表示实际标注区域而非检测模型自动输出。roi_statistics 必须引用实际 annotated_bbox，并记录 color.sample_count（正整数）。记录裁切/透视校正操作时保存方法；不以框自动确认该区域只有一个材质。

`material-spec.json`：

```json
{
  "schema_version":"1.0", "room_id":"当前房源ID",
  "materials":[{
    "material_id":"M_FLOOR_LIVING", "asset_id":"FLOOR_LIVING", "surface_id":"finish",
    "evidence_observation_ids":["OBS_FLOOR_01"],
    "base_color":{"target_srgb_hex":"#B69368", "status":"modeling_assumption", "basis":"示意：选无明显阴影区域的浅暖木色；需在中性光与目标网页复核", "allowed_srgb_range":[[165,195],[125,165],[80,125]], "range_basis":"示意候选配色范围，按此表面的照片观察和去光照选择；不是实测置信区间或通用木色"},
    "texture":{"pattern":"straight_grain", "contrast":"low", "direction_basis":"保持同一地面连续铺设，世界方向待建模确定", "scale_range_m":null, "scale_basis":null, "relief":"micro", "relief_basis":"木纹仅作微表面外观，不增加可见波浪"},
    "cross_view":{"status":"single_view", "basis":"只有一张可用局部，无法交叉验证", "conflicts":[], "excluded_observation_ids":[], "exclusion_reason":""},
    "review_checks":[
      {"name":"color_consensus", "status":"UNKNOWN", "method":"单图观察", "notes":"未校色且缺少第二视角"},
      {"name":"pattern_match", "status":"PASS", "method":"查看原图局部与选用图案", "notes":"局部为低对比细直纹，未选波浪纹"},
      {"name":"lighting_bias", "status":"WARN", "method":"目视检查阴影和灯光", "notes":"仍可能有白平衡偏差"}
    ]
  }]
}
```

每个材质至少绑定一条实际观察；完全不可见的表面可用无证据记录，但 base_color.status=unknown、target_srgb_hex=null、texture.pattern=unknown、cross_view.status=unknown，保留原因。新资产仍需在 appearance.material_ids 中引用这条 unknown 记录，不能悄悄跳过。

base_color.status 为 modeling_assumption/unknown；不要把普通照片给出的颜色标 measured。候选基础色还给出该表面自己的 allowed_srgb_range（R/G/B各为0–255的[min,max]）及 range_basis，用于拦截后续随意变深/变色；目标色须在范围内。范围是本轮选定的建模外观容差，不是照片测量置信区间，不能套用示例木色到所有房源。无法合理选色时用 unknown、target_srgb_hex=null、allowed_srgb_range=null；不得为消除未知虚填宽泛范围。纹理 contrast 为 low/medium/high/unknown；relief 为 flat/micro/visible_relief/unknown；scale_range_m 为 null 或 [min,max] 正数范围，有数值时 scale_basis 必填并注明尺度假设，不当作实测。

cross_view.status 为 consistent/single_view/conflict/unknown；consistent 至少两张不同来源图片，说明可比性。相同文件内容即使有不同 image_id 也只算一张来源；文件哈希去重不等于识别近似重复图片。conflict 保留 conflicts，必须解释为什么选择某些观察、排除另一些；不可通过少引用证据隐藏冲突。excluded_observation_ids 属于同一资产表面，并写 exclusion_reason。表面证据只有一种已识别图案时，选用图案应与之相同；未知不能随意换成另一种显眼图案。用户明确要求改设计时另记 `design_override:{source:"user",reason:"用户实际要求与来源说明"}`，与照片忠实还原区分。

review_checks 必须包含 color_consensus、pattern_match、lighting_bias；各自有实际方法与结果说明，状态 PASS/WARN/UNKNOWN/FAIL。PASS 表示该项实际看过并相容，不表示真实色度已校准。单图颜色不能标“跨图一致”PASS；未经相同光照/区域复核不能把像素统计写成色度准确认证。

## 校验与交付

执行 `python3 scripts/validate_materials.py 房源目录 --require`。脚本检查资产与证据引用、区域/色码/范围、覆盖完整性、双向 material_ids、观察与选用图案是否冲突、跨图数量和复核结果，生成 material-validation.json。结构通过与视觉匹配分开：overall=PASS/WARN/FAIL，visual_status=REVIEWED/UNKNOWN/FAIL；存在未解决的冲突或未知复核时为 WARN/UNKNOWN，不得仅凭 JSON 合法宣称照片还原通过。

analysis.html 展示按表面分组的证据局部或原图链接、观察色卡与选用色卡、纹理特征、照明偏差及跨图检查。色卡旁保留可编辑文字色码；截图不替代文字。报告编辑不改变 JSON。保留用户对可编辑正文、按列拖宽、保存当前 HTML 和打印的要求。

向后续模型传递 material-spec.json 和 material-validation.json。下游 scene-spec.material_bindings 至少记 source_material_id、object_names、actual_base_color_srgb、texture_files、uv_direction/uv_scale_m/uv_phase、normal_and_roughness_assumptions。源色卡与实际着色器基础色允许因去光照估计不同，但差异须有依据并在对照图复核；不擅自重选纹理。Web 导出核对色彩空间、材质因子、法线、重复边界；网页与离线图分开验收，首页用真实网页截图时记录对应模型/材质版本。
