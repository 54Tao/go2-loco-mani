#!/usr/bin/env python3
"""
Test script to integrate Go2-X5 robot into a SAGE scene.
This script loads a SAGE scene and places the Go2-X5 robot in it.
"""

import argparse
from isaaclab.app import AppLauncher

# Parse arguments
parser = argparse.ArgumentParser(description="Integrate Go2-X5 robot into SAGE scene")
parser.add_argument("--scene_path", type=str, required=True, help="Path to SAGE scene directory")
parser.add_argument("--robot_usd", type=str, default="/home/tjz/go2_loco_mani/assets/go2_x5.usd",
                    help="Path to robot USD file")
parser.add_argument("--spawn_x", type=float, default=3.0, help="Robot spawn X position")
parser.add_argument("--spawn_y", type=float, default=4.0, help="Robot spawn Y position")
parser.add_argument("--spawn_z", type=float, default=0.5, help="Robot spawn Z position")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# Launch Isaac Sim
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

# Import after AppLauncher
import json
import os
import numpy as np
from pxr import Usd, UsdGeom, Gf, UsdPhysics, PhysxSchema
import omni.usd
import carb

def create_ground_plane(stage, path="/World/GroundPlane"):
    """Create a ground plane with physics."""
    # Create ground plane
    plane_prim = UsdGeom.Xform.Define(stage, path)

    # Add cube geometry for ground
    cube_path = f"{path}/CollisionPlane"
    cube = UsdGeom.Cube.Define(stage, cube_path)
    cube.GetSizeAttr().Set(1.0)

    # Scale to make it large and flat
    cube_xform = UsdGeom.Xformable(cube)
    cube_xform.ClearXformOpOrder()
    cube_xform.AddTranslateOp().Set(Gf.Vec3d(0, 0, -0.5))
    cube_xform.AddScaleOp().Set(Gf.Vec3d(100, 100, 1))

    # Add collision
    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(cube_path))

    return plane_prim

def load_sage_scene_basic(stage, scene_path: str):
    """Load basic SAGE scene geometry (floor and walls)."""

    # Find the layout JSON file
    json_files = [f for f in os.listdir(scene_path) if f.endswith('.json')]
    if not json_files:
        raise FileNotFoundError(f"No JSON file found in {scene_path}")

    json_path = os.path.join(scene_path, json_files[0])
    print(f"Loading scene from: {json_path}")

    with open(json_path, 'r') as f:
        scene_data = json.load(f)

    # Create Scene xform
    scene_xform = UsdGeom.Xform.Define(stage, "/World/Scene")

    # Process rooms
    for room in scene_data.get("rooms", []):
        room_id = room["id"]
        room_type = room["room_type"]
        dimensions = room["dimensions"]

        print(f"\nRoom: {room_id} ({room_type})")
        print(f"  Size: {dimensions['width']}m x {dimensions['length']}m x {dimensions['height']}m")

        # Create room xform
        room_path = f"/World/Scene/{room_id}"
        UsdGeom.Xform.Define(stage, room_path)

        # Create floor with collision
        floor_path = f"{room_path}/floor"
        floor_cube = UsdGeom.Cube.Define(stage, floor_path)
        floor_cube.GetSizeAttr().Set(1.0)

        floor_xform = UsdGeom.Xformable(floor_cube)
        floor_xform.ClearXformOpOrder()
        floor_xform.AddTranslateOp().Set(Gf.Vec3d(
            dimensions["width"] / 2,
            dimensions["length"] / 2,
            -0.05
        ))
        floor_xform.AddScaleOp().Set(Gf.Vec3d(
            dimensions["width"],
            dimensions["length"],
            0.1
        ))

        # Add collision to floor
        floor_prim = stage.GetPrimAtPath(floor_path)
        UsdPhysics.CollisionAPI.Apply(floor_prim)

        print(f"  ✓ Created floor with collision")

        # Create walls with collision
        wall_count = 0
        for wall in room.get("walls", []):
            start = wall["start_point"]
            end = wall["end_point"]
            height = wall["height"]
            thickness = wall.get("thickness", 0.1)

            dx = end["x"] - start["x"]
            dy = end["y"] - start["y"]
            length = np.sqrt(dx**2 + dy**2)

            if length < 0.01:
                continue

            wall_path = f"{room_path}/wall_{wall_count}"
            wall_cube = UsdGeom.Cube.Define(stage, wall_path)
            wall_cube.GetSizeAttr().Set(1.0)

            wall_xform = UsdGeom.Xformable(wall_cube)
            wall_xform.ClearXformOpOrder()

            center_x = (start["x"] + end["x"]) / 2
            center_y = (start["y"] + end["y"]) / 2
            center_z = height / 2

            wall_xform.AddTranslateOp().Set(Gf.Vec3d(center_x, center_y, center_z))
            wall_xform.AddScaleOp().Set(Gf.Vec3d(length, thickness, height))

            if abs(dx) > 0.01:
                angle = np.arctan2(dy, dx)
                wall_xform.AddRotateZOp().Set(np.degrees(angle))

            # Add collision to wall
            wall_prim = stage.GetPrimAtPath(wall_path)
            UsdPhysics.CollisionAPI.Apply(wall_prim)

            wall_count += 1

        print(f"  ✓ Created {wall_count} walls with collision")

    print(f"\n✓ Scene loaded: {len(scene_data.get('rooms', []))} rooms")
    return scene_data

def add_robot_to_scene(stage, robot_usd_path: str, position: tuple):
    """Add Go2-X5 robot to the scene."""

    print(f"\nAdding robot to scene...")
    print(f"  Robot USD: {robot_usd_path}")
    print(f"  Position: {position}")

    # Add robot as reference
    robot_path = "/World/Robot"
    robot_prim = stage.DefinePrim(robot_path, "Xform")
    robot_prim.GetReferences().AddReference(robot_usd_path)

    # Set robot position
    robot_prim = stage.GetPrimAtPath(robot_path)
    if robot_prim.IsValid():
        xform = UsdGeom.Xformable(robot_prim)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(position[0], position[1], position[2]))
        print(f"  ✓ Robot added at {position}")
    else:
        print(f"  ✗ Failed to add robot")
        return False

    return True

def setup_physics(stage):
    """Setup physics scene."""

    # Create physics scene
    scene_path = "/World/PhysicsScene"
    scene = UsdPhysics.Scene.Define(stage, scene_path)
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(9.81)

    # Add PhysX scene settings
    physx_scene = PhysxSchema.PhysxSceneAPI.Apply(stage.GetPrimAtPath(scene_path))
    physx_scene.CreateEnableCCDAttr(True)
    physx_scene.CreateEnableStabilizationAttr(True)
    physx_scene.CreateEnableGPUDynamicsAttr(False)
    physx_scene.CreateBroadphaseTypeAttr("MBP")
    physx_scene.CreateSolverTypeAttr("TGS")

    print("✓ Physics scene configured")

def main():
    """Main function."""
    print("=" * 60)
    print("Go2-X5 Robot in SAGE Scene Integration Test")
    print("=" * 60)
    print(f"Scene: {args_cli.scene_path}")
    print(f"Robot: {args_cli.robot_usd}")
    print(f"Spawn position: ({args_cli.spawn_x}, {args_cli.spawn_y}, {args_cli.spawn_z})")
    print()

    try:
        # Create new stage
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()

        # Create World xform
        UsdGeom.Xform.Define(stage, "/World")

        # Setup physics
        setup_physics(stage)

        # Load SAGE scene
        scene_data = load_sage_scene_basic(stage, args_cli.scene_path)

        # Add robot
        robot_added = add_robot_to_scene(
            stage,
            args_cli.robot_usd,
            (args_cli.spawn_x, args_cli.spawn_y, args_cli.spawn_z)
        )

        if robot_added:
            print("\n" + "=" * 60)
            print("✓ Integration successful!")
            print("=" * 60)
            print("\nScene is ready. You can now:")
            print("  - View the scene in Isaac Sim GUI")
            print("  - Run physics simulation")
            print("  - Control the robot")
        else:
            print("\n✗ Failed to add robot to scene")
            return 1

        # Keep app running if not headless
        if not args_cli.headless:
            print("\nPress Ctrl+C to exit...")
            while simulation_app.is_running():
                simulation_app.update()

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        simulation_app.close()

    return 0

if __name__ == "__main__":
    exit(main())
