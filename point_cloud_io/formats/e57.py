import os

import bpy
import numpy as np


def _create_point_cloud_material(name, has_color, has_normal):
    material = bpy.data.materials.new(name=name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (0, 0)
    output = nodes.new('ShaderNodeOutputMaterial')
    output.location = (300, 0)
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    if has_color:
        attr = nodes.new('ShaderNodeAttribute')
        attr.attribute_name = "color"
        attr.location = (-300, 100)
        links.new(attr.outputs['Color'], bsdf.inputs['Base Color'])
    elif has_normal:
        attr = nodes.new('ShaderNodeAttribute')
        attr.attribute_name = "normal"
        attr.location = (-600, -100)
        remap = nodes.new('ShaderNodeVectorMath')
        remap.operation = 'MULTIPLY_ADD'
        remap.inputs[1].default_value = (0.5, 0.5, 0.5)
        remap.inputs[2].default_value = (0.5, 0.5, 0.5)
        remap.location = (-300, -100)
        links.new(attr.outputs['Vector'], remap.inputs[0])
        links.new(remap.outputs['Vector'], bsdf.inputs['Base Color'])

    return material


def _read_scan(e57_file, scan_index, options):
    """Read one scan from an E57 file and return (points, extras) or None."""
    data = e57_file.read_scan_raw(scan_index)

    x = data.get('cartesianX')
    y = data.get('cartesianY')
    z = data.get('cartesianZ')
    if x is None or y is None or z is None:
        return None

    invalid = data.get('cartesianInvalidState')
    if invalid is not None:
        mask = np.asarray(invalid) == 0
    else:
        mask = None

    def _take(arr):
        a = np.asarray(arr)
        return a[mask] if mask is not None and len(a) == len(mask) else a

    points = np.column_stack((_take(x), _take(y), _take(z))).astype(np.float32)
    points *= options['scale']

    extras = {}

    if options['colors']:
        r = data.get('colorRed')
        g = data.get('colorGreen')
        b = data.get('colorBlue')
        if r is not None and g is not None and b is not None:
            r = _take(r).astype(np.float32)
            g = _take(g).astype(np.float32)
            b = _take(b).astype(np.float32)
            peak = max(r.max() if r.size else 0.0,
                       g.max() if g.size else 0.0,
                       b.max() if b.size else 0.0)
            if peak > 1.0:
                r /= 255.0
                g /= 255.0
                b /= 255.0
            a = np.ones_like(r)
            extras['color'] = np.column_stack((r, g, b, a))

    if options['normals']:
        nx = data.get('normalX')
        ny = data.get('normalY')
        nz = data.get('normalZ')
        if nx is not None and ny is not None and nz is not None:
            extras['normal'] = np.column_stack(
                (_take(nx), _take(ny), _take(nz))
            ).astype(np.float32)

    if options['intensity']:
        intensity = data.get('intensity')
        if intensity is not None:
            intensity = _take(intensity).astype(np.float32)
            if intensity.size:
                lo, hi = float(intensity.min()), float(intensity.max())
                if hi > lo:
                    intensity = (intensity - lo) / (hi - lo)
            extras['intensity'] = intensity

    return points, extras


def _build_point_cloud(context, name, points, extras, point_radius):
    # Blender's Python API doesn't expose direct point allocation on PointCloud,
    # so we populate a mesh then convert — the same approach used by the
    # official PointCloud workflows.
    mesh = bpy.data.meshes.new(name=f"{name}_mesh")
    mesh.vertices.add(len(points))
    mesh.vertices.foreach_set("co", points.ravel())
    mesh.update()

    obj = bpy.data.objects.new(name=name, object_data=mesh)
    context.collection.objects.link(obj)
    obj.select_set(True)
    context.view_layer.objects.active = obj
    bpy.ops.object.convert(target='POINTCLOUD')
    pc = context.active_object

    attrs = pc.data.attributes

    if 'color' in extras:
        a = attrs.new(name="color", type='FLOAT_COLOR', domain='POINT')
        a.data.foreach_set("color", extras['color'].ravel())

    if 'normal' in extras:
        a = attrs.new(name="normal", type='FLOAT_VECTOR', domain='POINT')
        a.data.foreach_set("vector", extras['normal'].ravel())

    if 'intensity' in extras:
        a = attrs.new(name="intensity", type='FLOAT', domain='POINT')
        a.data.foreach_set("value", extras['intensity'])

    radius_attr = attrs.new(name="radius", type='FLOAT', domain='POINT')
    radius_attr.data.foreach_set(
        "value", np.full(len(points), point_radius, dtype=np.float32)
    )

    pc.select_set(False)
    return pc


def _attach_material(pc, name, extras):
    has_color = 'color' in extras
    has_normal = 'normal' in extras
    if not (has_color or has_normal):
        return
    material = _create_point_cloud_material(name, has_color, has_normal)
    pc.data.materials.append(material)


def import_e57_file(
    context,
    filepath,
    *,
    import_colors,
    import_normals,
    import_intensity,
    scale_factor,
    point_radius,
    merge_scans,
):
    """Read an E57 file and create one or more PointCloud objects in the scene."""
    import pye57

    options = {
        'colors': import_colors,
        'normals': import_normals,
        'intensity': import_intensity,
        'scale': scale_factor,
    }

    if context.active_object and context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')

    e57_file = pye57.E57(filepath)
    base_name = os.path.splitext(os.path.basename(filepath))[0]

    scans = []
    for index in range(e57_file.scan_count):
        result = _read_scan(e57_file, index, options)
        if result is not None and len(result[0]) > 0:
            scans.append(result)

    if not scans:
        raise RuntimeError("No valid scans found in E57 file.")

    if merge_scans:
        all_points = np.concatenate([s[0] for s in scans])
        common_keys = set(scans[0][1].keys())
        for _, extras in scans[1:]:
            common_keys &= set(extras.keys())
        merged_extras = {
            k: np.concatenate([s[1][k] for s in scans]) for k in common_keys
        }
        pc = _build_point_cloud(context, base_name, all_points, merged_extras, point_radius)
        _attach_material(pc, f"Mat_{base_name}", merged_extras)
        return [pc]

    created = []
    for index, (points, extras) in enumerate(scans):
        name = base_name if len(scans) == 1 else f"{base_name}_scan_{index}"
        pc = _build_point_cloud(context, name, points, extras, point_radius)
        _attach_material(pc, f"Mat_{name}", extras)
        created.append(pc)

    return created


def _get_positions(obj, count, apply_transforms):
    arr = np.empty(count * 3, dtype=np.float32)
    obj.data.attributes['position'].data.foreach_get('vector', arr)
    positions = arr.reshape(-1, 3).astype(np.float64)
    if apply_transforms:
        matrix = np.array(obj.matrix_world)
        rotation = matrix[:3, :3]
        translation = matrix[:3, 3]
        positions = positions @ rotation.T + translation
    return positions


def _get_colors_uint8(obj, count):
    if 'color' not in obj.data.attributes:
        return None
    arr = np.empty(count * 4, dtype=np.float32)
    obj.data.attributes['color'].data.foreach_get('color', arr)
    colors = arr.reshape(-1, 4)
    return np.clip(colors[:, :3] * 255.0, 0.0, 255.0).astype(np.uint8)


def _get_intensity(obj, count):
    if 'intensity' not in obj.data.attributes:
        return None
    arr = np.empty(count, dtype=np.float32)
    obj.data.attributes['intensity'].data.foreach_get('value', arr)
    return arr


def export_e57_file(
    objects,
    filepath,
    *,
    export_colors,
    export_intensity,
    apply_transforms,
):
    """Write a list of PointCloud objects as scans in an E57 file.

    Returns the total number of points written. Each PointCloud becomes one
    E57 scan. pye57's writer does not expose a normals field, so normals are
    not exported.
    """
    import pye57

    if not objects:
        raise RuntimeError("No PointCloud objects to export.")

    writer = pye57.E57(filepath, mode='w')
    total_points = 0

    for obj in objects:
        attrs = obj.data.attributes
        if 'position' not in attrs:
            continue
        count = len(attrs['position'].data)
        if count == 0:
            continue

        positions = _get_positions(obj, count, apply_transforms)
        data = {
            'cartesianX': np.ascontiguousarray(positions[:, 0]),
            'cartesianY': np.ascontiguousarray(positions[:, 1]),
            'cartesianZ': np.ascontiguousarray(positions[:, 2]),
        }

        if export_colors:
            colors = _get_colors_uint8(obj, count)
            if colors is not None:
                data['colorRed'] = np.ascontiguousarray(colors[:, 0])
                data['colorGreen'] = np.ascontiguousarray(colors[:, 1])
                data['colorBlue'] = np.ascontiguousarray(colors[:, 2])

        if export_intensity:
            intensity = _get_intensity(obj, count)
            if intensity is not None:
                data['intensity'] = intensity

        writer.write_scan_raw(data, name=obj.name)
        total_points += count

    return total_points
