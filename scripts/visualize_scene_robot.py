#!/usr/bin/env python3
"""
可视化验证脚本：在Isaac Sim GUI中查看SAGE场景和Go2-X5机器人
- 修复墙体旋转bug
- 加载PLY mesh物体（带纹理）
- 机器人spawn在空旷位置
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

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import json
import os
import numpy as np
from pxr import Usd, UsdGeom, Gf, UsdPhysics, UsdShade, Sdf, Vt
import omni.usd
import trimesh


def create_wall(stage, wall_path, start, end, height, thickness=0.1):
    """正确创建墙体，根据起止点方向放置。"""
    sx, sy = start["x"], start["y"]
    ex, ey = end["x"], end["y"]

    dx = ex - sx
    dy = ey - sy
    length = np.sqrt(dx**2 + dy**2)
    if length < 0.01:
        return

    angle = np.degrees(np.arctan2(dy, dx))

    center_x = (sx + ex) / 2
    center_y = (sy + ey) / 2
    center_z = height / 2

    wall_cube = UsdGeom.Cube.Define(stage, wall_path)
    wall_cube.GetSizeAttr().Set(1.0)

    xf = UsdGeom.Xformable(wall_cube)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(center_x, center_y, center_z))
    xf.AddRotateZOp().Set(angle)
    xf.AddScaleOp().Set(Gf.Vec3d(length, thickness, height))

    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(wall_path))


def load_ply_as_mesh(stage, prim_path, ply_path, texture_path=None):
    """将PLY文件加载为USD Mesh，可选贴纹理。"""
    try:
        mesh = trimesh.load(ply_path, process=False)
    except Exception as e:
        print(f"    ✗ 无法加载PLY: {ply_path}: {e}")
        return False

    vertices = mesh.vertices
    faces = mesh.faces

    # 创建USD Mesh
    usd_mesh = UsdGeom.Mesh.Define(stage, prim_path)
    usd_mesh.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in vertices]))

    # 面索引
    face_vertex_counts = [3] * len(faces)
    face_vertex_indices = faces.flatten().tolist()
    usd_mesh.GetFaceVertexCountsAttr().Set(face_vertex_counts)
    usd_mesh.GetFaceVertexIndicesAttr().Set(face_vertex_indices)

    # 法线
    if mesh.vertex_normals is not None and len(mesh.vertex_normals) > 0:
        usd_mesh.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in mesh.vertex_normals]))
        usd_mesh.SetNormalsInterpolation("vertex")

    # 顶点颜色
    if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
        colors = mesh.visual.vertex_colors[:, :3].astype(np.float32) / 255.0
        color_primvar = UsdGeom.PrimvarsAPI(usd_mesh).CreatePrimvar(
            "displayColor", Sdf.ValueTypeNames.Color3fArray, UsdGeom.Tokens.vertex
        )
        color_primvar.Set(Vt.Vec3fArray([Gf.Vec3f(float(c[0]), float(c[1]), float(c[2])) for c in colors]))

    # 如果有纹理文件，创建材质
    if texture_path and os.path.exists(texture_path):
        mat_path = prim_path + "/Material"
        material = UsdShade.Material.Define(stage, mat_path)
        shader = UsdShade.Shader.Define(stage, mat_path + "/Shader")
        shader.CreateIdAttr("UsdPreviewSurface")

        # 纹理
        tex_reader = UsdShade.Shader.Define(stage, mat_path + "/DiffuseTexture")
        tex_reader.CreateIdAttr("UsdUVTexture")
        tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_path)
        tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            tex_reader.ConnectableAPI(), "rgb"
        )
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

        UsdShade.MaterialBindingAPI(usd_mesh).Bind(material)

    # 碰撞
    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(prim_path))

    return True


def find_free_spawn(room, occupied_positions, margin=0.8):
    """在房间中找一个不与物体重叠的spawn位置。"""
    dims = room["dimensions"]
    w, l = dims["width"], dims["length"]

    # 候选位置：从中心开始，逐步偏移
    candidates = [
        (w * 0.5, l * 0.5),
        (w * 0.3, l * 0.3),
        (w * 0.7, l * 0.3),
        (w * 0.3, l * 0.7),
        (w * 0.7, l * 0.7),
        (w * 0.5, l * 0.3),
        (w * 0.5, l * 0.7),
    ]

    for cx, cy in candidates:
        free = True
        for ox, oy in occupied_positions:
            if abs(cx - ox) < margin and abs(cy - oy) < margin:
                free = False
                break
        if free:
            return cx, cy

    # 如果都被占了，返回第一个候选
    return candidates[0]


def load_scene_and_robot():
    """加载场景和机器人"""

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()

    UsdGeom.Xform.Define(stage, "/World")

    print("=" * 60)
    print("加载SAGE场景...")
    print("=" * 60)

    scene_path = args_cli.scene_path
    json_files = [f for f in os.listdir(scene_path) if f.endswith('.json')]
    if not json_files:
        print("✗ 未找到场景JSON文件")
        return

    json_path = os.path.join(scene_path, json_files[0])
    with open(json_path, 'r') as f:
        scene_data = json.load(f)

    objects_dir = os.path.join(scene_path, "objects")
    materials_dir = os.path.join(scene_path, "materials")

    occupied_positions = []

    for room in scene_data.get("rooms", []):
        room_id = room["id"]
        room_type = room["room_type"]
        dims = room["dimensions"]

        print(f"\n房间: {room_type}")
        print(f"  尺寸: {dims['width']}m × {dims['length']}m × {dims['height']}m")

        room_path = f"/World/Scene/{room_id}"
        UsdGeom.Xform.Define(stage, room_path)

        # --- 地板 ---
        floor_path = f"{room_path}/floor"

        # 检查是否有地板纹理
        floor_tex = os.path.join(materials_dir, f"{room_id}_floor.png")
        if os.path.exists(floor_tex):
            # 用带纹理的平面
            floor_mesh = UsdGeom.Mesh.Define(stage, floor_path)
            w, l = dims['width'], dims['length']
            floor_mesh.GetPointsAttr().Set(Vt.Vec3fArray([
                Gf.Vec3f(0, 0, 0), Gf.Vec3f(w, 0, 0),
                Gf.Vec3f(w, l, 0), Gf.Vec3f(0, l, 0)
            ]))
            floor_mesh.GetFaceVertexCountsAttr().Set([4])
            floor_mesh.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
            floor_mesh.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0, 0, 1)] * 4))
            floor_mesh.SetNormalsInterpolation("vertex")

            # UV
            uv_primvar = UsdGeom.PrimvarsAPI(floor_mesh).CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex
            )
            uv_primvar.Set(Vt.Vec2fArray([
                Gf.Vec2f(0, 0), Gf.Vec2f(1, 0),
                Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)
            ]))

            # 材质
            mat_path = floor_path + "/Material"
            material = UsdShade.Material.Define(stage, mat_path)
            shader = UsdShade.Shader.Define(stage, mat_path + "/Shader")
            shader.CreateIdAttr("UsdPreviewSurface")

            tex_reader = UsdShade.Shader.Define(stage, mat_path + "/DiffuseTexture")
            tex_reader.CreateIdAttr("UsdUVTexture")
            tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(floor_tex)
            tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

            st_reader = UsdShade.Shader.Define(stage, mat_path + "/UVReader")
            st_reader.CreateIdAttr("UsdPrimvarReader_float2")
            st_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
            st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

            tex_reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
                st_reader.ConnectableAPI(), "result"
            )
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                tex_reader.ConnectableAPI(), "rgb"
            )
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            UsdShade.MaterialBindingAPI(floor_mesh).Bind(material)

            print(f"  ✓ 地板（带纹理）")
        else:
            # 简单立方体地板
            floor_cube = UsdGeom.Cube.Define(stage, floor_path)
            floor_cube.GetSizeAttr().Set(1.0)
            xf = UsdGeom.Xformable(floor_cube)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(dims['width']/2, dims['length']/2, -0.05))
            xf.AddScaleOp().Set(Gf.Vec3d(dims['width'], dims['length'], 0.1))
            print(f"  ✓ 地板（无纹理）")

        UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(floor_path))

        # --- 墙体 ---
        wall_count = 0
        for i, wall in enumerate(room.get("walls", [])):
            wall_path = f"{room_path}/wall_{i}"

            # 检查墙面纹理
            wall_mat = wall.get("material", "")
            wall_tex = os.path.join(materials_dir, f"{wall_mat}.png")

            create_wall(stage, wall_path,
                        wall["start_point"], wall["end_point"],
                        wall["height"], wall.get("thickness", 0.1))

            # 如果有墙面纹理，绑定材质
            if os.path.exists(wall_tex):
                mat_path = wall_path + "/Material"
                material = UsdShade.Material.Define(stage, mat_path)
                shader = UsdShade.Shader.Define(stage, mat_path + "/Shader")
                shader.CreateIdAttr("UsdPreviewSurface")

                tex_reader = UsdShade.Shader.Define(stage, mat_path + "/DiffuseTexture")
                tex_reader.CreateIdAttr("UsdUVTexture")
                tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(wall_tex)
                tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)

                shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                    tex_reader.ConnectableAPI(), "rgb"
                )
                material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
                UsdShade.MaterialBindingAPI(stage.GetPrimAtPath(wall_path)).Bind(material)

            wall_count += 1

        print(f"  ✓ {wall_count}面墙")

        # --- 物体（PLY mesh） ---
        obj_count = 0
        ply_loaded = 0
        for obj in room.get("objects", []):
            obj_type = obj.get("type", "unknown")
            position = obj.get("position", {"x": 0, "y": 0, "z": 0})
            rotation = obj.get("rotation", {"x": 0, "y": 0, "z": 0})
            dimensions = obj.get("dimensions", {"width": 0.5, "length": 0.5, "height": 0.5})
            source_id = obj.get("source_id", "")

            occupied_positions.append((position["x"], position["y"]))

            obj_path = f"{room_path}/obj_{obj_count}"

            # 尝试加载PLY文件
            ply_file = os.path.join(objects_dir, f"{source_id}.ply") if source_id else ""
            tex_file = os.path.join(objects_dir, f"{source_id}_texture.png") if source_id else ""

            loaded = False
            if ply_file and os.path.exists(ply_file):
                # 创建Xform容器
                obj_xform_prim = UsdGeom.Xform.Define(stage, obj_path)
                xf = UsdGeom.Xformable(obj_xform_prim)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(
                    position["x"], position["y"], position["z"]
                ))
                xf.AddRotateXYZOp().Set(Gf.Vec3d(
                    rotation.get("x", 0),
                    rotation.get("y", 0),
                    rotation.get("z", 0)
                ))

                mesh_path = obj_path + "/mesh"
                tex = tex_file if os.path.exists(tex_file) else None
                loaded = load_ply_as_mesh(stage, mesh_path, ply_file, tex)
                if loaded:
                    ply_loaded += 1

            if not loaded:
                # fallback: 立方体
                obj_cube = UsdGeom.Cube.Define(stage, obj_path)
                obj_cube.GetSizeAttr().Set(1.0)
                xf = UsdGeom.Xformable(obj_cube)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(
                    position["x"], position["y"],
                    position["z"] + dimensions["height"] / 2
                ))
                xf.AddScaleOp().Set(Gf.Vec3d(
                    dimensions["width"], dimensions["length"], dimensions["height"]
                ))
                UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(obj_path))

            obj_count += 1

        print(f"  ✓ {obj_count}个物体（{ply_loaded}个PLY mesh，{obj_count - ply_loaded}个立方体）")

    # --- 机器人 ---
    print("\n" + "=" * 60)
    print("加载Go2-X5机器人...")
    print("=" * 60)

    robot_path = "/World/Robot"
    robot_prim = stage.DefinePrim(robot_path, "Xform")
    robot_prim.GetReferences().AddReference(args_cli.robot_usd)

    first_room = scene_data.get("rooms", [{}])[0]
    spawn_x, spawn_y = find_free_spawn(first_room, occupied_positions)
    spawn_z = 0.6

    robot_xform = UsdGeom.Xformable(robot_prim)
    robot_xform.ClearXformOpOrder()
    robot_xform.AddTranslateOp().Set(Gf.Vec3d(spawn_x, spawn_y, spawn_z))

    print(f"  ✓ 机器人已加载")
    print(f"  位置: ({spawn_x:.2f}, {spawn_y:.2f}, {spawn_z:.2f})")

    # --- 物理 ---
    scene = UsdPhysics.Scene.Define(stage, "/World/PhysicsScene")
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(9.81)

    print("\n" + "=" * 60)
    print("✓ 场景和机器人加载完成！")
    print("=" * 60)
    print("\n操作提示：")
    print("  - 鼠标拖拽旋转视角，滚轮缩放")
    print("  - 点击Play按钮开始物理仿真")
    print("  - 按Ctrl+C退出")
    print()


def main():
    try:
        load_scene_and_robot()
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
