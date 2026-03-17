#!/usr/bin/env python3
"""
可视化验证脚本：在Isaac Sim GUI中查看SAGE场景和Go2-X5机器人
"""

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Visualize SAGE scene with Go2-X5 robot")
parser.add_argument("--scene_path", type=str,
                    default="/home/tjz/go2_loco_mani/datasets/sage-10k/scenes/test_scene",
                    help="Path to SAGE scene directory")
parser.add_argument("--robot_usd", type=str,
                    default="/home/tjz/go2_loco_mani/assets/go2_x5.usd",
                    help="Path to robot USD file")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# 启动Isaac Sim（GUI模式）
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# 在AppLauncher之后导入
import json
import os
import numpy as np
from pxr import Usd, UsdGeom, Gf, UsdPhysics, PhysxSchema
import omni.usd

def load_scene_and_robot():
    """加载场景和机器人"""

    # 创建新stage
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()

    # 创建World
    UsdGeom.Xform.Define(stage, "/World")

    print("=" * 60)
    print("加载SAGE场景...")
    print("=" * 60)

    # 加载场景JSON
    scene_path = args_cli.scene_path
    json_files = [f for f in os.listdir(scene_path) if f.endswith('.json')]
    if not json_files:
        print("✗ 未找到场景JSON文件")
        return

    json_path = os.path.join(scene_path, json_files[0])
    with open(json_path, 'r') as f:
        scene_data = json.load(f)

    # 创建场景几何
    for room in scene_data.get("rooms", []):
        room_id = room["id"]
        room_type = room["room_type"]
        dims = room["dimensions"]

        print(f"\n房间: {room_type}")
        print(f"  尺寸: {dims['width']}m × {dims['length']}m × {dims['height']}m")

        room_path = f"/World/Scene/{room_id}"
        UsdGeom.Xform.Define(stage, room_path)

        # 创建地板
        floor_path = f"{room_path}/floor"
        floor = UsdGeom.Cube.Define(stage, floor_path)
        floor.GetSizeAttr().Set(1.0)

        floor_xform = UsdGeom.Xformable(floor)
        floor_xform.ClearXformOpOrder()
        floor_xform.AddTranslateOp().Set(Gf.Vec3d(dims['width']/2, dims['length']/2, -0.05))
        floor_xform.AddScaleOp().Set(Gf.Vec3d(dims['width'], dims['length'], 0.1))

        # 添加碰撞
        UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(floor_path))

        # 创建墙体
        for i, wall in enumerate(room.get("walls", [])):
            start = wall["start_point"]
            end = wall["end_point"]
            height = wall["height"]

            dx = end["x"] - start["x"]
            dy = end["y"] - start["y"]
            length = np.sqrt(dx**2 + dy**2)

            if length < 0.01:
                continue

            wall_path = f"{room_path}/wall_{i}"
            wall_cube = UsdGeom.Cube.Define(stage, wall_path)
            wall_cube.GetSizeAttr().Set(1.0)

            wall_xform = UsdGeom.Xformable(wall_cube)
            wall_xform.ClearXformOpOrder()

            center_x = (start["x"] + end["x"]) / 2
            center_y = (start["y"] + end["y"]) / 2
            center_z = height / 2

            wall_xform.AddTranslateOp().Set(Gf.Vec3d(center_x, center_y, center_z))
            wall_xform.AddScaleOp().Set(Gf.Vec3d(length, 0.1, height))

            if abs(dx) > 0.01:
                angle = np.arctan2(dy, dx)
                wall_xform.AddRotateZOp().Set(np.degrees(angle))

            UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(wall_path))

        print(f"  ✓ 创建了地板和{len(room.get('walls', []))}面墙")

    print("\n" + "=" * 60)
    print("加载Go2-X5机器人...")
    print("=" * 60)

    # 添加机器人
    robot_path = "/World/Robot"
    robot_prim = stage.DefinePrim(robot_path, "Xform")
    robot_prim.GetReferences().AddReference(args_cli.robot_usd)

    # 设置机器人位置（房间中央，高度0.5m）
    robot_xform = UsdGeom.Xformable(robot_prim)
    robot_xform.ClearXformOpOrder()
    robot_xform.AddTranslateOp().Set(Gf.Vec3d(3.0, 4.0, 0.5))

    print(f"  ✓ 机器人已加载")
    print(f"  位置: (3.0, 4.0, 0.5)")

    # 设置物理场景
    scene_prim = stage.GetPrimAtPath("/World")
    scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(9.81)

    print("\n" + "=" * 60)
    print("✓ 场景和机器人加载完成！")
    print("=" * 60)
    print("\n操作提示：")
    print("  - 使用鼠标拖拽旋转视角")
    print("  - 滚轮缩放")
    print("  - 点击Play按钮开始物理仿真")
    print("  - 按Ctrl+C退出")
    print()

def main():
    try:
        load_scene_and_robot()

        # 保持窗口打开
        while simulation_app.is_running():
            simulation_app.update()

    except KeyboardInterrupt:
        print("\n退出...")
    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulation_app.close()

if __name__ == "__main__":
    main()
