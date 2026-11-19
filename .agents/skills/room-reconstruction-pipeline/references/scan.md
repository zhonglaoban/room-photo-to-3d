# 扫描适配与测量边界

支持的导出目录有cameras/*.json、images/*.jpg、depth/*.png、confidence/*.png，同一帧用相同stem。相机JSON为width/height、fx/fy/cx/cy和t_00..t_23（相机到世界），X向右/Y向上/视线-Z。RGB/深度像素须已对齐。其他格式先写适配器，不能猜轴或用固定缩放把房间凑对。

```sh
python3 <skill>/scripts/fuse_depth.py --keyframes <export> --output <new-directory> --depth-scale <metres-per-value> --confidence-value <highest-valid-code> --max-frames 3
```

先用少量帧核对朝向、尺度、文件配对和有效点，再移除max-frames批量融合。`--depth-scale` 和 `--confidence-value` 应来自当前扫描的元数据、导出说明或已做过的诊断。

helper过滤无效深度/边缘，按位姿变换并体素去重，输出fused.npz和统计manifest。它没有执行GLB配准、点云语义分割、量尺认证或“每个物品完整尺寸”提取。要量物品需选语义ROI、避开混入邻物的点，报告可见跨度/分位数/缺失面与完整外形补全的区别。

深度与GLB同源时，配准一致只能证明内部相容；另加独立量尺才有外部尺度依据。透明/金属反射、遮挡和低置信点不足时保留UNKNOWN，不能放宽过滤凑出数字。
