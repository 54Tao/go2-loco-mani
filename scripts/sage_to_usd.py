#!/usr/bin/env python3
"""
将SAGE场景（JSON+PLY）转换为USD文件，供play_cs.py的--map参数使用。
复用visualize_scene_robot.py中的场景加载逻辑。

用法：
    conda run -n lab python scripts/sage_to_usd.py \
        --scene_path datasets/sage-10k/scenes/test_scene \
        --output assets/test_scene.usd
"""

import argparse
from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Convert SAGE scene to USD")
parser.add_argument("--scene_path", type=str, required=True, help="Path to SAGE scene directory")
parser.add_argument("--output", type=str, required=True, help="Output USD file path")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
args_cli.headless = True

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import json
import os
import numpy as np
from pxr import Usd, UsdGeom, Gf, UsdPhysics, UsdShade, Sdf, Vt
import omni.usd
import trimesh


def create_wall(stage, wall_path, start, end, height, thickness=0.1):
    sx, sy = start["x"], start["y"]
    ex, ey = end["x"], end["y"]
    dx, dy = ex - sx, ey - sy
    length = np.sqrt(dx**2 + dy**2)
    if length < 0.01:
        return
    angle = np.degrees(np.arctan2(dy, dx))
    center_x, center_y, center_z = (sx + ex) / 2, (sy + ey) / 2, height / 2

    wall_cube = UsdGeom.Cube.Define(stage, wall_path)
    wall_cube.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(wall_cube)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(center_x, center_y, center_z))
    xf.AddRotateZOp().Set(angle)
    xf.AddScaleOp().Set(Gf.Vec3d(length, thickness, height))
    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(wall_path))


def load_ply_as_mesh(stage, prim_path, ply_path, texture_path=None):
    try:
        mesh = trimesh.load(ply_path, process=False)
    except Exception as e:
        print(f"  Failed to load PLY: {ply_path}: {e}")
        return False

    vertices = mesh.vertices
    faces = mesh.faces

    usd_mesh = UsdGeom.Mesh.Define(stage, prim_path)
    usd_mesh.GetPointsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in vertices]))
    usd_mesh.GetFaceVertexCountsAttr().Set([3] * len(faces))
    usd_mesh.GetFaceVertexIndicesAttr().Set(faces.flatten().tolist())

    if mesh.vertex_normals is not None and len(mesh.vertex_normals) > 0:
        usd_mesh.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in mesh.vertex_normals]))
        usd_mesh.SetNormalsInterpolation("vertex")

    if hasattr(mesh.visual, 'vertex_colors') and mesh.visual.vertex_colors is not None:
        colors = mesh.visual.vertex_colors[:, :3].astype(np.float32) / 255.0
        color_primvar = UsdGeom.PrimvarsAPI(usd_mesh).CreatePrimvar(
            "displayColor", Sdf.ValueTypeNames.Color3fArray, UsdGeom.Tokens.vertex
        )
        color_primvar.Set(Vt.Vec3fArray([Gf.Vec3f(float(c[0]), float(c[1]), float(c[2])) for c in colors]))

    if texture_path and os.path.exists(texture_path):
        mat_path = prim_path + "/Material"
        material = UsdShade.Material.Define(stage, mat_path)
        shader = UsdShade.Shader.Define(stage, mat_path + "/Shader")
        shader.CreateIdAttr("UsdPreviewSurface")
        tex_reader = UsdShade.Shader.Define(stage, mat_path + "/DiffuseTexture")
        tex_reader.CreateIdAttr("UsdUVTexture")
        tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(texture_path)
        tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            tex_reader.ConnectableAPI(), "rgb"
        )
        material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
        UsdShade.MaterialBindingAPI(usd_mesh).Bind(material)

    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(prim_path))
    return True


def convert_scene():
    scene_path = args_cli.scene_path
    output_path = args_cli.output

    # Load scene JSON
    json_file = None
    for f in os.listdir(scene_path):
        if f.endswith(".json"):
            json_file = os.path.join(scene_path, f)
            break
    if not json_file:
        print(f"No JSON file found in {scene_path}")
        return

    with open(json_file) as f:
        scene_data = json.load(f)

    objects_dir = os.path.join(scene_path, "objects")
    materials_dir = os.path.join(scene_path, "materials")

    # Create new stage
    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.Xform.Define(stage, "/World")

    print(f"Converting: {json_file}")

    for room_idx, room in enumerate(scene_data.get("rooms", [])):
        room_type = room.get("room_type", "unknown")
        dims = room.get("dimensions", {})
        print(f"  Room {room_idx}: {room_type} ({dims.get('width', 0):.1f}x{dims.get('length', 0):.1f})")

        room_path = f"/World/room_{room_idx}"
        UsdGeom.Xform.Define(stage, room_path)

        # Floor
        floor_path = f"{room_path}/floor"
        floor_mat_file = None
        if os.path.isdir(materials_dir):
            for mf in os.listdir(materials_dir):
                if "floor" in mf.lower() and mf.endswith(".png"):
                    floor_mat_file = os.path.join(materials_dir, mf)
                    break

        if floor_mat_file:
            floor_mesh = UsdGeom.Mesh.Define(stage, floor_path)
            w, l = dims.get("width", 5), dims.get("length", 5)
            floor_mesh.GetPointsAttr().Set(Vt.Vec3fArray([
                Gf.Vec3f(0, 0, 0), Gf.Vec3f(float(w), 0, 0),
                Gf.Vec3f(float(w), float(l), 0), Gf.Vec3f(0, float(l), 0)
            ]))
            floor_mesh.GetFaceVertexCountsAttr().Set([4])
            floor_mesh.GetFaceVertexIndicesAttr().Set([0, 1, 2, 3])
            floor_mesh.GetNormalsAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0, 0, 1)] * 4))
            floor_mesh.SetNormalsInterpolation("vertex")
            st = UsdGeom.PrimvarsAPI(floor_mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
            st.Set(Vt.Vec2fArray([Gf.Vec2f(0, 0), Gf.Vec2f(1, 0), Gf.Vec2f(1, 1), Gf.Vec2f(0, 1)]))

            mat_path = floor_path + "/Material"
            material = UsdShade.Material.Define(stage, mat_path)
            shader = UsdShade.Shader.Define(stage, mat_path + "/Shader")
            shader.CreateIdAttr("UsdPreviewSurface")
            tex_reader = UsdShade.Shader.Define(stage, mat_path + "/DiffuseTexture")
            tex_reader.CreateIdAttr("UsdUVTexture")
            tex_reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(floor_mat_file)
            tex_reader.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
            shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
                tex_reader.ConnectableAPI(), "rgb"
            )
            material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
            UsdShade.MaterialBindingAPI(floor_mesh).Bind(material)
        else:
            floor_cube = UsdGeom.Cube.Define(stage, floor_path)
            floor_cube.GetSizeAttr().Set(1.0)
            xf = UsdGeom.Xformable(floor_cube)
            xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(dims.get('width', 5) / 2, dims.get('length', 5) / 2, -0.05))
            xf.AddScaleOp().Set(Gf.Vec3d(dims.get('width', 5), dims.get('length', 5), 0.1))

        UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(floor_path))

        # Walls
        for i, wall in enumerate(room.get("walls", [])):
            wall_path = f"{room_path}/wall_{i}"
            create_wall(stage, wall_path, wall["start_point"], wall["end_point"],
                        wall["height"], wall.get("thickness", 0.1))

            wall_mat = wall.get("material", "")
            wall_tex = os.path.join(materials_dir, f"{wall_mat}.png") if materials_dir else ""
            if wall_tex and os.path.exists(wall_tex):
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

        # Objects
        obj_count = 0
        for obj in room.get("objects", []):
            position = obj.get("position", {"x": 0, "y": 0, "z": 0})
            rotation = obj.get("rotation", {"x": 0, "y": 0, "z": 0})
            dimensions = obj.get("dimensions", {"width": 0.5, "length": 0.5, "height": 0.5})
            source_id = obj.get("source_id", "")

            obj_path = f"{room_path}/obj_{obj_count}"
            ply_file = os.path.join(objects_dir, f"{source_id}.ply") if source_id else ""
            tex_file = os.path.join(objects_dir, f"{source_id}_texture.png") if source_id else ""

            loaded = False
            if ply_file and os.path.exists(ply_file):
                obj_xform = UsdGeom.Xform.Define(stage, obj_path)
                xf = UsdGeom.Xformable(obj_xform)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(position["x"], position["y"], position["z"]))
                xf.AddRotateXYZOp().Set(Gf.Vec3d(rotation.get("x", 0), rotation.get("y", 0), rotation.get("z", 0)))
                tex = tex_file if os.path.exists(tex_file) else None
                loaded = load_ply_as_mesh(stage, obj_path + "/mesh", ply_file, tex)

            if not loaded:
                obj_cube = UsdGeom.Cube.Define(stage, obj_path)
                obj_cube.GetSizeAttr().Set(1.0)
                xf = UsdGeom.Xformable(obj_cube)
                xf.ClearXformOpOrder()
                xf.AddTranslateOp().Set(Gf.Vec3d(position["x"], position["y"], position["z"] + dimensions["height"] / 2))
                xf.AddScaleOp().Set(Gf.Vec3d(dimensions["width"], dimensions["length"], dimensions["height"]))
                UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(obj_path))

            obj_count += 1

        print(f"    {len(room.get('walls', []))} walls, {obj_count} objects")

    # Save
    stage.GetRootLayer().Export(output_path)
    print(f"\nExported: {output_path}")


if __name__ == "__main__":
    try:
        convert_scene()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulation_app.close()
