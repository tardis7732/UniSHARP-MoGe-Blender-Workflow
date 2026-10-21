"""Create a colored Gaussian point-cloud Blender scene with its source camera."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector


VERTEX_DTYPE = np.dtype([(f"v{i}", "<f4") for i in range(14)])


def arguments() -> argparse.Namespace:
    values = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_ply", type=Path)
    parser.add_argument("colored_ply", type=Path)
    parser.add_argument("source_image", type=Path)
    parser.add_argument("output_blend", type=Path)
    parser.add_argument("--point-radius", type=float, default=0.006, help="Viewport point radius in meters.")
    parser.add_argument("--output-camera-fbx", type=Path, help="Optional Unreal-compatible FBX containing only the source camera.")
    parser.add_argument("--no-background", action="store_true", help="Do not embed the source image in the camera background.")
    parser.add_argument("--no-metric-reference", action="store_true", help="Do not add the 1 m cube and origin reference.")
    parser.add_argument("--orientation", choices=("negative_x_xminus90", "source"), default="negative_x_xminus90")
    return parser.parse_args(values)


def read_camera(source_ply: Path) -> tuple[np.ndarray, np.ndarray, int, int]:
    vertex_count: int | None = None
    with source_ply.open("rb") as stream:
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header ended unexpectedly.")
            text = line.decode("ascii").strip()
            if text.startswith("element vertex "):
                vertex_count = int(text.rsplit(" ", 1)[1])
            if text == "end_header":
                break
        if vertex_count is None:
            raise ValueError("PLY has no vertices.")
        stream.seek(stream.tell() + vertex_count * VERTEX_DTYPE.itemsize)
        w2c = np.fromfile(stream, dtype="<f4", count=16).reshape(4, 4)
        intrinsic = np.fromfile(stream, dtype="<f4", count=9).reshape(3, 3)
        width, height = np.fromfile(stream, dtype="<u4", count=2)
    return w2c, intrinsic, int(width), int(height)


def make_color_material() -> bpy.types.Material:
    material = bpy.data.materials.new("Gaussian vertex colors")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()
    color = nodes.new("ShaderNodeVertexColor")
    color.layer_name = "Col"
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Roughness"].default_value = 1.0
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(color.outputs["Color"], shader.inputs["Base Color"])
    links.new(color.outputs["Alpha"], shader.inputs["Alpha"])
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    return material


def add_metric_reference_cube() -> bpy.types.Object:
    """Add a world-space 1 m cube with its bottom-center pivot at Z=0."""
    # The object origin is intentionally on the ground plane, rather than at
    # the cube centre. Its mesh therefore occupies Z=0 through Z=1 m.
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.25, 0.55, 0.0))
    cube = bpy.context.active_object
    cube.name = "REFERENCE — 1 meter cube"
    cube.data.transform(Matrix.Translation((0.0, 0.0, 0.5)))
    cube.display_type = "WIRE"
    cube.color = (1.0, 0.18, 0.05, 1.0)
    cube.show_name = True
    return cube


def parent_keep_world_transform(child: bpy.types.Object, parent: bpy.types.Object) -> None:
    """Parent an object without changing its current location, rotation, or scale."""
    world_matrix = child.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()
    child.matrix_world = world_matrix


def export_unreal_camera_fbx(camera: bpy.types.Object, output_path: Path) -> None:
    """Export only the reconstructed source camera using Unreal's FBX axis convention."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Blender cameras look along local -Z. Unreal's FBX camera importer reads
    # this source transform with its optical direction reversed. Export an
    # unparented duplicate with a local 180-degree yaw so it faces the Gaussian
    # scene in Unreal, without changing the camera saved in the .blend file.
    export_camera = camera.copy()
    export_camera.data = camera.data.copy()
    export_camera.name = "Unreal source camera"
    bpy.context.collection.objects.link(export_camera)
    export_camera.parent = None
    export_camera.matrix_world = camera.matrix_world @ Matrix.Rotation(np.pi, 4, "Y")
    try:
        bpy.ops.object.select_all(action="DESELECT")
        export_camera.select_set(True)
        bpy.context.view_layer.objects.active = export_camera
        bpy.ops.export_scene.fbx(
            filepath=str(output_path),
            use_selection=True,
            object_types={"CAMERA"},
            axis_forward="-Z",
            axis_up="Y",
            apply_unit_scale=True,
            apply_scale_options="FBX_SCALE_UNITS",
            bake_anim=False,
            add_leaf_bones=False,
        )
    finally:
        export_camera_data = export_camera.data
        bpy.data.objects.remove(export_camera, do_unlink=True)
        bpy.data.cameras.remove(export_camera_data)


def main() -> None:
    args = arguments()
    source_ply = args.source_ply
    colored_ply = args.colored_ply
    source_image = args.source_image
    output_path = args.output_blend
    if args.point_radius <= 0.0:
        raise ValueError("--point-radius must be greater than zero.")
    w2c_cv, intrinsic, width, height = read_camera(source_ply)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene_axis = bpy.data.objects.new("UniSHARP Scene Axis (move this)", None)
    scene_axis.empty_display_type = "ARROWS"
    scene_axis.empty_display_size = 0.6
    scene_axis.show_name = True
    bpy.context.collection.objects.link(scene_axis)
    bpy.ops.wm.ply_import(filepath=str(colored_ply))
    points = bpy.context.selected_objects[0]
    points.name = "UniSHARP Colored Gaussians"
    # UniSHARP's source camera initially looks along +Z.  First rotate the
    # reconstruction toward Blender's global -X axis, then apply the requested
    # global X -90° orientation adjustment without changing that forward axis.
    scene_rotation = (
        Matrix.Rotation(-np.pi / 2.0, 4, "X") @ Matrix.Rotation(-np.pi / 2.0, 4, "Y")
        if args.orientation == "negative_x_xminus90"
        else Matrix.Identity(4)
    )
    points.matrix_world = scene_rotation

    material = make_color_material()
    tree = bpy.data.node_groups.new("Display Gaussian points", "GeometryNodeTree")
    tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    group_input = tree.nodes.new("NodeGroupInput")
    group_output = tree.nodes.new("NodeGroupOutput")
    mesh_to_points = tree.nodes.new("GeometryNodeMeshToPoints")
    mesh_to_points.mode = "VERTICES"
    mesh_to_points.inputs["Radius"].default_value = float(args.point_radius)
    set_material = tree.nodes.new("GeometryNodeSetMaterial")
    set_material.inputs["Material"].default_value = material
    tree.links.new(group_input.outputs["Geometry"], mesh_to_points.inputs["Mesh"])
    tree.links.new(mesh_to_points.outputs["Points"], set_material.inputs["Geometry"])
    tree.links.new(set_material.outputs["Geometry"], group_output.inputs["Geometry"])
    modifier = points.modifiers.new("Render colored Gaussian points", "NODES")
    modifier.node_group = tree

    camera_data = bpy.data.cameras.new("UniSHARP source camera")
    camera = bpy.data.objects.new("UniSHARP source camera", camera_data)
    bpy.context.collection.objects.link(camera)
    # Preserve the full fitted pinhole K matrix. Older previews only used a
    # single averaged focal length, which can visibly squash the source-image
    # overlay when fx != fy or the principal point is off-center.
    fx, fy = float(intrinsic[0, 0]), float(intrinsic[1, 1])
    cx, cy = float(intrinsic[0, 2]), float(intrinsic[1, 2])
    camera_data.sensor_fit = "HORIZONTAL"
    camera_data.sensor_width = 36.0
    # Preserve the source camera's vertical FOV in FBX. Unreal otherwise
    # imports the camera as a 36x24 mm (3:2) full-frame camera, which shows
    # extra image above and below a 16:9 source. With the horizontal focal
    # length fixed below, this sensor height yields the fitted source fy.
    camera_data.sensor_height = camera_data.sensor_width * (height / width) * (fx / max(fy, 1e-6))
    camera_data.lens = fx * camera_data.sensor_width / width
    c2w_cv = np.linalg.inv(w2c_cv)
    cv_from_blender_camera = np.diag([1.0, -1.0, -1.0, 1.0])
    camera.matrix_world = scene_rotation @ Matrix(c2w_cv @ cv_from_blender_camera)
    if not args.no_background:
        camera_data.show_background_images = True
        background = camera_data.background_images.new()
        background.image = bpy.data.images.load(str(source_image))
        background.image.pack()
        background.alpha = 0.75

    scene = bpy.context.scene
    scene.camera = camera
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    pixel_aspect = fx / fy if fy > 1e-6 else 1.0
    scene.render.pixel_aspect_x = 1.0
    scene.render.pixel_aspect_y = pixel_aspect
    camera_data.shift_x = -(cx - width * 0.5) / width
    camera_data.shift_y = ((cy - height * 0.5) / width) * pixel_aspect
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.length_unit = "METERS"
    managed_objects = [points, camera]
    if not args.no_metric_reference:
        # Keep the metric cube in world space.  It is a fixed-size reference
        # for adjusting the UniSHARP Scene Axis, so it must not follow that
        # axis when the reconstruction is moved, rotated, or scaled.
        add_metric_reference_cube()
    for obj in managed_objects:
        parent_keep_world_transform(obj, scene_axis)
    bpy.ops.object.select_all(action="DESELECT")
    scene_axis.select_set(True)
    bpy.context.view_layer.objects.active = scene_axis
    output_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path))
    if args.output_camera_fbx is not None:
        export_unreal_camera_fbx(camera, args.output_camera_fbx)
        print(f"Saved Unreal camera FBX {args.output_camera_fbx}")
    print(
        f"Saved {output_path}; image={width}x{height}; "
        f"fx={fx:.2f}; filmback={camera_data.sensor_width:.3f}x{camera_data.sensor_height:.3f}mm"
    )


if __name__ == "__main__":
    main()
