import os

import bpy
import numpy as np

from ._common import (
    attach_material,
    build_point_cloud,
    get_colors_uint8,
    get_positions,
    get_scalar,
    reset_selection,
)


def _read_scan(e57_file, scan_index, options):
    """Read one scan from an E57 file and return (points, extras) or None."""
    data = e57_file.read_scan_raw(scan_index)

    x = data.get('cartesianX')
    y = data.get('cartesianY')
    z = data.get('cartesianZ')
    if x is None or y is None or z is None:
        return None

    invalid = data.get('cartesianInvalidState')
    mask = np.asarray(invalid) == 0 if invalid is not None else None

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

    reset_selection(context)

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
        pc = build_point_cloud(context, base_name, all_points, merged_extras, point_radius)
        attach_material(pc, f"Mat_{base_name}", merged_extras)
        return [pc]

    created = []
    for index, (points, extras) in enumerate(scans):
        name = base_name if len(scans) == 1 else f"{base_name}_scan_{index}"
        pc = build_point_cloud(context, name, points, extras, point_radius)
        attach_material(pc, f"Mat_{name}", extras)
        created.append(pc)

    return created


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

        positions = get_positions(obj, count, apply_transforms)
        data = {
            'cartesianX': np.ascontiguousarray(positions[:, 0]),
            'cartesianY': np.ascontiguousarray(positions[:, 1]),
            'cartesianZ': np.ascontiguousarray(positions[:, 2]),
        }

        if export_colors:
            colors = get_colors_uint8(obj, count)
            if colors is not None:
                data['colorRed'] = np.ascontiguousarray(colors[:, 0])
                data['colorGreen'] = np.ascontiguousarray(colors[:, 1])
                data['colorBlue'] = np.ascontiguousarray(colors[:, 2])

        if export_intensity:
            intensity = get_scalar(obj, count, 'intensity')
            if intensity is not None:
                data['intensity'] = intensity

        writer.write_scan_raw(data, name=obj.name)
        total_points += count

    return total_points
