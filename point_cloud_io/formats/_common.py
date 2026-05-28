"""Shared helpers used by every format module.

Functions here build PointCloud objects from numpy arrays, attach a material
that surfaces color or normal attributes, and pull data back out of PointCloud
objects for export. Format modules (e57.py, ply.py, ...) only handle the
format-specific read/write logic.
"""

import bpy
import numpy as np


def create_material(name, has_color, has_normal):
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


def attach_material(pc, name, extras):
    has_color = 'color' in extras
    has_normal = 'normal' in extras
    if not (has_color or has_normal):
        return
    material = create_material(name, has_color, has_normal)
    pc.data.materials.append(material)


def build_point_cloud(context, name, points, extras, point_radius):
    """Create a PointCloud object from a positions array and an extras dict.

    extras may contain:
        'color'     -> (N, 4) float32 in 0..1
        'normal'    -> (N, 3) float32
        'intensity' -> (N,)   float32
        any other key -> (N,) float32 scalar attribute

    NaN-positioned points are dropped (and their extras filtered to match)
    before the PointCloud is built. PCL's convention is that depth-camera
    pixels with invalid range get NaN coordinates, and one of those slipping
    through poisons the bbox / radius calculation downstream.

    Returns the created object.
    """
    points = np.asarray(points)
    if len(points) > 0:
        finite_mask = np.isfinite(points).all(axis=1)
        if not finite_mask.all():
            points = points[finite_mask]
            extras = {
                key: (value[finite_mask]
                      if isinstance(value, np.ndarray) and len(value) == len(finite_mask)
                      else value)
                for key, value in extras.items()
            }

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
    reserved = {'color', 'normal'}

    if 'color' in extras:
        a = attrs.new(name="color", type='FLOAT_COLOR', domain='POINT')
        a.data.foreach_set("color", extras['color'].ravel())

    if 'normal' in extras:
        a = attrs.new(name="normal", type='FLOAT_VECTOR', domain='POINT')
        a.data.foreach_set("vector", extras['normal'].ravel())

    for key, values in extras.items():
        if key in reserved:
            continue
        arr = np.asarray(values)
        if arr.dtype.kind in ('i', 'u'):
            a = attrs.new(name=key, type='INT', domain='POINT')
            a.data.foreach_set("value", arr.astype(np.int32))
        elif arr.dtype.kind == 'b':
            a = attrs.new(name=key, type='BOOLEAN', domain='POINT')
            a.data.foreach_set("value", arr.astype(np.bool_))
        else:
            a = attrs.new(name=key, type='FLOAT', domain='POINT')
            a.data.foreach_set("value", arr.astype(np.float32))

    radius_attr = attrs.new(name="radius", type='FLOAT', domain='POINT')
    radius_attr.data.foreach_set(
        "value", np.full(len(points), point_radius, dtype=np.float32)
    )

    pc.select_set(False)
    return pc


def reset_selection(context):
    if context.active_object and context.active_object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    if bpy.ops.object.select_all.poll():
        bpy.ops.object.select_all(action='DESELECT')


def get_positions(obj, count, apply_transforms):
    arr = np.empty(count * 3, dtype=np.float32)
    obj.data.attributes['position'].data.foreach_get('vector', arr)
    positions = arr.reshape(-1, 3).astype(np.float64)
    if apply_transforms:
        matrix = np.array(obj.matrix_world)
        rotation = matrix[:3, :3]
        translation = matrix[:3, 3]
        positions = positions @ rotation.T + translation
    return positions


def get_normals(obj, count, apply_transforms):
    if 'normal' not in obj.data.attributes:
        return None
    arr = np.empty(count * 3, dtype=np.float32)
    obj.data.attributes['normal'].data.foreach_get('vector', arr)
    normals = arr.reshape(-1, 3).astype(np.float64)
    if apply_transforms:
        norm_mat = np.array(
            obj.matrix_world.to_3x3().inverted_safe().transposed()
        )
        normals = normals @ norm_mat.T
        lengths = np.linalg.norm(normals, axis=1, keepdims=True)
        lengths[lengths == 0] = 1.0
        normals = normals / lengths
    return normals


def get_colors_uint8(obj, count):
    if 'color' not in obj.data.attributes:
        return None
    arr = np.empty(count * 4, dtype=np.float32)
    obj.data.attributes['color'].data.foreach_get('color', arr)
    colors = arr.reshape(-1, 4)
    return np.clip(colors[:, :3] * 255.0, 0.0, 255.0).astype(np.uint8)


def get_scalar(obj, count, name):
    if name not in obj.data.attributes:
        return None
    arr = np.empty(count, dtype=np.float32)
    obj.data.attributes[name].data.foreach_get('value', arr)
    return arr


_DEFAULT_RADIUS = 0.005


def suggest_radius(point_cloud, fallback=_DEFAULT_RADIUS):
    """Pick a radius based on the cloud's bounding box and point count.

    Uses the average inter-point spacing for a roughly uniform distribution
    (`diagonal / count**(1/3)`) and halves it so points sit just shy of each
    other rather than overlapping. Returns `fallback` when no points are
    available, when the cloud has zero extent, or when positions contain
    NaN / Inf that would otherwise propagate into the result.
    """
    attrs = point_cloud.attributes
    if 'position' not in attrs:
        return fallback
    count = len(attrs['position'].data)
    if count == 0:
        return fallback

    positions = np.empty(count * 3, dtype=np.float32)
    attrs['position'].data.foreach_get('vector', positions)
    positions = positions.reshape(-1, 3)

    finite_mask = np.isfinite(positions).all(axis=1)
    if not finite_mask.any():
        return fallback
    positions = positions[finite_mask]

    extent = positions.max(axis=0) - positions.min(axis=0)
    diagonal = float(np.linalg.norm(extent))
    if not np.isfinite(diagonal) or diagonal <= 0.0:
        return fallback

    spacing = diagonal / max(len(positions) ** (1.0 / 3.0), 1.0)
    return max(spacing * 0.5, 1e-6)
