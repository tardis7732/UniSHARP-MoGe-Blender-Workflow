"""Export a UV-textured depth mesh and cameras to Blender and Unreal FBX."""
import argparse
import json
from pathlib import Path
import sys
import bpy
import numpy as np
from mathutils import Matrix

sys.path.insert(0, str(Path(__file__).resolve().parent))
from moge_geometry import depth_mesh


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--folder', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--no-background', action='store_true')
    p.add_argument('--no-metric-reference', action='store_true')
    p.add_argument('--edge-threshold', type=float, default=0.04)
    p.add_argument('--fbx', action='store_true')
    p.add_argument('--mesh-fbx', action='store_true')
    p.add_argument('--camera-fbx', action='store_true')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out = Path(a.folder).resolve()
    data = np.load(out/'depth_data.npz')
    depth, mask, k = data['depth'], data['mask'], data['intrinsics'].copy()
    h, w = depth.shape
    axes = np.array([[0, 0, -1, 0], [1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
    verts, faces, uv = depth_mesh(depth, mask, k, a.edge_threshold)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.scale_length = 1.0
    s.unit_settings.length_unit = 'METERS'
    root = bpy.data.objects.new('Depth scene - move this', None)
    s.collection.objects.link(root)
    mesh = bpy.data.meshes.new('MoGe-3 depth surface')
    mesh.vertices.add(len(verts)); mesh.vertices.foreach_set('co', verts.ravel())
    mesh.loops.add(faces.size); mesh.loops.foreach_set('vertex_index', faces.ravel())
    mesh.polygons.add(len(faces))
    mesh.polygons.foreach_set('loop_start', np.arange(len(faces), dtype=np.int32)*3)
    mesh.polygons.foreach_set('loop_total', np.full(len(faces), 3, dtype=np.int32))
    mesh.update(calc_edges=True)
    mesh.uv_layers.new(name='Photo UV').data.foreach_set('uv', uv[faces.ravel()].ravel())
    obj = bpy.data.objects.new('MoGe-3 textured depth mesh', mesh)
    s.collection.objects.link(obj); obj.parent = root
    obj.matrix_world = Matrix(axes.tolist())
    obj['depth_to_scene_scale'] = 1.0
    obj['depth_units'] = 'estimated meters'
    obj['source'] = 'MoGe-3; visible surfaces only; hidden geometry is not reconstructed.'
    image = bpy.data.images.load(str(out/'texture.png')); image.pack()
    mat = bpy.data.materials.new('Photo - unlit'); mat.use_nodes = True
    nodes = mat.node_tree.nodes; nodes.clear()
    tex = nodes.new('ShaderNodeTexImage'); tex.image = image
    emission = nodes.new('ShaderNodeEmission')
    output = nodes.new('ShaderNodeOutputMaterial')
    mat.node_tree.links.new(tex.outputs['Color'], emission.inputs['Color'])
    mat.node_tree.links.new(emission.outputs[0], output.inputs['Surface'])
    mesh.materials.append(mat)

    pixel_aspect = float(k[0, 0]*w/(k[1, 1]*h))
    lens = float(k[0, 0]*36)
    shift = [.5-float(k[0, 2]), (float(k[1, 2])-.5)*h/w*pixel_aspect]

    def camera(name, matrix, focal=lens, sensor=36., offsets=shift):
        d = bpy.data.cameras.new(name); ob = bpy.data.objects.new(name, d)
        s.collection.objects.link(ob); ob.parent = root
        d.sensor_fit = 'HORIZONTAL'; d.sensor_width = sensor
        d.sensor_height = sensor*h/w*pixel_aspect
        d.lens = focal; d.shift_x, d.shift_y = offsets
        d.clip_start = .01; d.clip_end = max(10000, float(verts[:, 2].max())*10)
        ob.matrix_world = Matrix(matrix.tolist())
        return ob

    source = camera('01 Original photo camera', axes@np.diag([1, -1, -1, 1]))
    s.camera = source
    if not a.no_background:
        source.data.show_background_images = True
        background = source.data.background_images.new()
        background.image = image
        background.alpha = .75
        background.display_depth = 'BACK'
    if not a.no_metric_reference:
        from make_blender_camera_preview import add_metric_reference_cube
        cube = add_metric_reference_cube()
        cube.hide_render = True
        cube['purpose'] = 'World-space 1 m reference; not an inferred object or a scale calibration.'
    s.render.engine = 'BLENDER_EEVEE'; s.eevee.taa_render_samples = 32
    s.render.resolution_x = w
    s.render.resolution_y = h
    s.render.resolution_percentage = 100
    s.render.pixel_aspect_x = 1; s.render.pixel_aspect_y = pixel_aspect
    s.render.film_transparent = True
    s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGBA'
    s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
    s.view_settings.exposure = 0; s.view_settings.gamma = 1
    s.world = bpy.data.worlds.new('Neutral world'); s.world.use_nodes = True
    s.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = obj; obj.select_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
    bpy.data.texts.new('READ ME').write(
        'MoGe-3 textured depth mesh.\nNumpad 0: camera view. N > View > Lock Camera to View: move the camera.\n'
        'The original photograph is packed into this file. Hidden surfaces are missing.\n'
        'The default camera uses the same estimated intrinsics as the mesh projection.\n'
        'Scene coordinates preserve MoGe estimated meters (1 Blender unit = 1 meter).\n'
        'The optional 1 m reference cube is independent of the scene root and excluded from FBX export.\n'
        'Unreal: import FBX as Static Mesh; import texture.png; use Unlit, Texture RGB -> Emissive Color.\n')
    blend = out/f'{a.name}_moge3.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    if a.fbx or a.mesh_fbx:
        # FBX understands Principled base-color textures. Unreal's final unlit
        # material must still be set explicitly, as documented in the guide.
        fbxmat = bpy.data.materials.new('Photo texture'); fbxmat.use_nodes = True
        t = fbxmat.node_tree.nodes.new('ShaderNodeTexImage'); t.image = image
        fbxmat.node_tree.links.new(t.outputs['Color'], fbxmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
        mesh.materials[0] = fbxmat
        bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=str(out/f'{a.name}_unreal_mesh.fbx'),
            use_selection=True, object_types={'MESH'}, axis_forward='-Z', axis_up='Y',
            apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
            bake_anim=False, add_leaf_bones=False, path_mode='COPY', embed_textures=True)
        mesh.materials[0] = mat
    if a.fbx or a.camera_fbx:
        from make_blender_camera_preview import export_unreal_camera_fbx
        export_unreal_camera_fbx(source, out/f'{a.name}_unreal_camera.fbx')
    (out/'mesh_info.json').write_text(json.dumps({
        'vertices': len(verts), 'triangles': len(faces), 'scale': 1.0,
        'units': 'estimated meters',
        'edge_threshold': a.edge_threshold, 'active_camera': source.name,
        'camera_source': 'MoGe estimated intrinsics', 'pixel_aspect': pixel_aspect,
        'camera_background': not a.no_background, 'metric_reference_cube': not a.no_metric_reference,
        'intrinsics': k.tolist(), 'camera_matrix': [list(row) for row in source.matrix_world]
    }, indent=2), encoding='utf-8')
    print('Blender and FBX export complete.', flush=True)


if __name__ == '__main__':
    main()
