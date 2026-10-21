"""Build a UV-textured depth mesh, cameras, Blender renders and Unreal FBX."""
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
    p.add_argument('--camera-json')
    p.add_argument('--edge-threshold', type=float, default=0.04)
    p.add_argument('--fbx', action='store_true')
    a = p.parse_args(sys.argv[sys.argv.index('--')+1:])
    out = Path(a.folder).resolve()
    data = np.load(out/'depth_data.npz')
    depth, mask, k = data['depth'], data['mask'], data['intrinsics'].copy()
    h, w = depth.shape
    axes = np.array([[0, 0, -1, 0], [1, 0, 0, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float)
    ref, scale = None, 1.0
    if a.camera_json:
        ref = json.loads(Path(a.camera_json).read_text(encoding='utf-8'))
        axes = np.array(ref['axes'])
        scale = ref['median_z']/float(np.median(depth[mask]))
        fx = ref['lens']/ref['sensor_width']
        k = np.array([[fx, 0, .5-ref['shift'][0]],
                      [0, fx*w/h/ref['pixel_aspect'], .5+ref['shift'][1]*w/h/ref['pixel_aspect']],
                      [0, 0, 1]])
    verts, faces, uv = depth_mesh(depth, mask, k, a.edge_threshold, scale)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.scale_length = 1.0
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
    obj['depth_to_scene_scale'] = scale
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
    target = camera('02 Your saved Blender camera', np.array(ref['matrix']),
                    ref['target_lens'], ref['target_sensor_width'], ref['target_shift']) if ref else source
    s.camera = target
    s.render.engine = 'BLENDER_EEVEE'; s.eevee.taa_render_samples = 32
    s.render.resolution_x = min(1920, max(w, 1024))
    s.render.resolution_y = round(s.render.resolution_x*h/w)
    s.render.resolution_percentage = 100
    s.render.pixel_aspect_x = 1; s.render.pixel_aspect_y = pixel_aspect
    s.render.film_transparent = True
    s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGBA'
    s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
    s.view_settings.exposure = 0; s.view_settings.gamma = 1
    s.world = bpy.data.worlds.new('Neutral world'); s.world.use_nodes = True
    s.world.node_tree.nodes['Background'].inputs['Strength'].default_value = 0
    bpy.context.view_layer.objects.active = obj; obj.select_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.spaces.active.region_3d.view_perspective = 'CAMERA'
                area.spaces.active.shading.type = 'MATERIAL'
    bpy.data.texts.new('READ ME').write(
        'MoGe-3 textured depth mesh.\nNumpad 0: camera view. N > View > Lock Camera to View: move the camera.\n'
        'The original photograph is packed into this file. Hidden surfaces are missing.\n'
        'A reference camera is copied from the saved file, not live-linked.\n'
        f'Model depth to scene scale: {scale}. Reference alignment uses median depth.\n'
        'Unreal: import FBX as Static Mesh; import texture.png; use Unlit, Texture RGB -> Emissive Color.\n')
    blend = out/f'{a.name}_moge3.blend'
    s.render.filepath = str(out/'camera_preview.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    bpy.ops.render.render(write_still=True)
    if a.fbx:
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
        from make_blender_camera_preview import export_unreal_camera_fbx
        export_unreal_camera_fbx(target, out/f'{a.name}_unreal_camera.fbx')
    (out/'mesh_info.json').write_text(json.dumps({
        'vertices': len(verts), 'triangles': len(faces), 'scale': scale,
        'edge_threshold': a.edge_threshold, 'active_camera': target.name,
        'reference_camera': bool(ref), 'pixel_aspect': pixel_aspect,
        'intrinsics': k.tolist(), 'camera_matrix': [list(row) for row in target.matrix_world]
    }, indent=2), encoding='utf-8')
    # Render true camera-space Z, without persisting the temporary depth material.
    dm = bpy.data.materials.new('Temporary camera Z'); dm.use_nodes = True
    nd = dm.node_tree.nodes; nd.clear()
    cd = nd.new('ShaderNodeCameraData'); em = nd.new('ShaderNodeEmission'); op = nd.new('ShaderNodeOutputMaterial')
    dm.node_tree.links.new(cd.outputs['View Z Depth'], em.inputs['Color'])
    dm.node_tree.links.new(em.outputs[0], op.inputs['Surface']); mesh.materials[0] = dm
    s.render.image_settings.file_format = 'OPEN_EXR'; s.render.image_settings.color_depth = '32'
    s.render.image_settings.color_mode = 'RGBA'; s.render.image_settings.exr_codec = 'ZIP'
    s.render.filepath = str(out/'camera_depth_Z.exr')
    bpy.ops.render.render(write_still=True)
    depth_image = bpy.data.images.load(s.render.filepath, check_existing=False)
    dw, dh = depth_image.size
    rgba = np.empty(dw*dh*4, np.float32); depth_image.pixels.foreach_get(rgba)
    np.save(out/'camera_depth_rgba.npy', rgba.reshape(dh, dw, 4)[::-1])
    print('Blender, preview, depth and FBX export complete.', flush=True)


if __name__ == '__main__':
    main()
