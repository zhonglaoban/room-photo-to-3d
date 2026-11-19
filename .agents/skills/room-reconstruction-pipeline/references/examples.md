# 合成示例与验证

下面命令用独立的合成房间演示模板同步、椅子的几何前向、台面承托和预览渲染。示例脚本创建桌椅和校验用摆件；要试建造完整室内外壳，见 [完整 Blender 室内模型](../../room-inventory-to-blender/SKILL.md)。

从仓库根目录运行。将 `blender` 替换为本机 Blender 命令或可执行文件路径。

```sh
pipeline=.agents/skills/room-reconstruction-pipeline/scripts
work=$(mktemp -d)
blender --background --factory-startup --python-exit-code 1 --python "$pipeline/create_test_room.py" -- "$work"
blender --background "$work/source.blend" --python-exit-code 1 --python "$pipeline/blender_pipeline.py" -- sync --profile "$work/profile.json" --output "$work/synced.blend" --negative-probe
blender --background "$work/synced.blend" --python-exit-code 1 --python "$pipeline/blender_pipeline.py" -- qa --profile "$work/profile.json" --output "$work/qa.json" --negative-probe
blender --background "$work/synced.blend" --python-exit-code 1 --python "$pipeline/blender_pipeline.py" -- render --profile "$work/profile.json" --output "$work/renders"
```

脚本的回归测试使用临时数据。布局测试检查旋转家具的净距、椅子朝向、过期标注、保留已确认椅子和覆盖保护。Blender 集成测试验证另存并重新打开后，模板同步、拒绝反向椅子与悬空设备、输出覆盖保护及渲染清单符合预期。

```sh
python3 -B "$pipeline/test_layout_constraints.py"
python3 -B "$pipeline/test_blender_pipeline.py" --blender blender --result "$work/integration-test.json"
```
