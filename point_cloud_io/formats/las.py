"""LAS / LAZ import and export via laspy.

Reads positions, RGB, intensity, classification, and return number into Blender
point attributes. Writes back to LAS / LAZ using Point Data Record Format 3
(LAS 1.2 with RGB + intensity), which is the most broadly compatible PDRF that
covers our attribute set.

LAZ support is provided by the bundled lazrs codec; laspy picks the backend
automatically when the file extension is `.laz`.
"""

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


_COLOR_BITS = 16  # LAS RGB channels are uint16


def import_las_file(
    context,
    filepath,
    *,
    import_colors,
    import_intensity,
    import_classification,
    import_return_info,
    scale_factor,
    point_radius,
    center_on_origin,
):
    """Read a LAS or LAZ file and create a PointCloud object."""
    import laspy

    reset_selection(context)
    las = laspy.read(filepath)

    # laspy returns x/y/z already in real-world units (scale + offset applied).
    # Stay in float64 while we still have raw georeferenced magnitudes; we'll
    # cast to float32 only after subtracting the centering offset, so we don't
    # lose precision on UTM-scale coordinates (millions of metres).
    x = np.asarray(las.x, dtype=np.float64)
    y = np.asarray(las.y, dtype=np.float64)
    z = np.asarray(las.z, dtype=np.float64)

    if center_on_origin and x.size:
        origin_offset = np.array([x.min(), y.min(), z.min()], dtype=np.float64)
    else:
        origin_offset = np.zeros(3, dtype=np.float64)

    positions = np.column_stack(
        (x - origin_offset[0], y - origin_offset[1], z - origin_offset[2])
    ).astype(np.float32)
    positions *= scale_factor

    extras = {}

    if import_colors and {'red', 'green', 'blue'}.issubset(las.point_format.dimension_names):
        max_value = float((1 << _COLOR_BITS) - 1)
        r = np.asarray(las.red, dtype=np.float32) / max_value
        g = np.asarray(las.green, dtype=np.float32) / max_value
        b = np.asarray(las.blue, dtype=np.float32) / max_value
        a = np.ones_like(r)
        extras['color'] = np.column_stack((r, g, b, a))

    if import_intensity:
        intensity = np.asarray(las.intensity, dtype=np.float32)
        if intensity.size:
            peak = float(intensity.max())
            if peak > 0.0:
                intensity = intensity / peak
        extras['intensity'] = intensity

    if import_classification:
        # Stored as int32 attribute so users can branch on it in Geometry Nodes.
        extras['classification'] = np.asarray(las.classification, dtype=np.int32)

    if import_return_info:
        extras['return_number'] = np.asarray(las.return_number, dtype=np.int32)
        extras['number_of_returns'] = np.asarray(las.number_of_returns, dtype=np.int32)

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    pc = build_point_cloud(context, base_name, positions, extras, point_radius)
    attach_material(pc, f"Mat_{base_name}", extras)

    # Stash the centering offset so it can be inspected in the N-panel
    # (Item > Custom Properties) and used to round-trip the georeference
    # back to LAS on export. Only present when actually non-zero.
    if np.any(origin_offset):
        pc["las_origin_offset"] = origin_offset.tolist()

    return [pc]


def _gather_export_data(objects, apply_transforms):
    """Concatenate all selected PointClouds into single-cloud LAS arrays."""
    positions_list = []
    colors_list = []
    intensity_list = []
    classification_list = []
    return_number_list = []
    number_of_returns_list = []

    have_color = True
    have_intensity = True
    have_classification = True
    have_return_info = True

    for obj in objects:
        attrs = obj.data.attributes
        if 'position' not in attrs:
            continue
        count = len(attrs['position'].data)
        if count == 0:
            continue

        positions = get_positions(obj, count, apply_transforms)
        # If this object was imported from a georeferenced LAS, add the
        # centering offset back so the output file carries the original
        # coordinate system.
        offset = obj.get('las_origin_offset')
        if offset is not None:
            positions = positions + np.asarray(offset, dtype=np.float64)
        positions_list.append(positions)

        colors = get_colors_uint8(obj, count)
        if colors is None:
            have_color = False
        else:
            colors_list.append(colors)

        intensity = get_scalar(obj, count, 'intensity')
        if intensity is None:
            have_intensity = False
        else:
            intensity_list.append(intensity)

        if 'classification' in attrs:
            arr = np.empty(count, dtype=np.int32)
            attrs['classification'].data.foreach_get('value', arr)
            classification_list.append(arr)
        else:
            have_classification = False

        if 'return_number' in attrs and 'number_of_returns' in attrs:
            rn = np.empty(count, dtype=np.int32)
            attrs['return_number'].data.foreach_get('value', rn)
            nr = np.empty(count, dtype=np.int32)
            attrs['number_of_returns'].data.foreach_get('value', nr)
            return_number_list.append(rn)
            number_of_returns_list.append(nr)
        else:
            have_return_info = False

    if not positions_list:
        return None

    return {
        'positions': np.concatenate(positions_list),
        'colors': np.concatenate(colors_list) if have_color else None,
        'intensity': np.concatenate(intensity_list) if have_intensity else None,
        'classification': np.concatenate(classification_list) if have_classification else None,
        'return_number': np.concatenate(return_number_list) if have_return_info else None,
        'number_of_returns': np.concatenate(number_of_returns_list) if have_return_info else None,
    }


def export_las_file(
    objects,
    filepath,
    *,
    apply_transforms,
):
    """Write a LAS or LAZ file from one or more PointCloud objects.

    All selected PointClouds are concatenated into a single LAS point block
    (LAS is a single-cloud format with no scan separation).

    Format is inferred from the extension: `.las` writes uncompressed, `.laz`
    compresses via the bundled lazrs codec.

    Returns the total number of points written.
    """
    import laspy

    data = _gather_export_data(objects, apply_transforms)
    if data is None:
        raise RuntimeError("No PointCloud objects to export.")

    positions = data['positions']
    count = len(positions)

    # PDRF 3 = positions + intensity + RGB + GPS time + classification + returns.
    # LAS 1.2 to maximise downstream tool compatibility.
    las = laspy.LasData(header=laspy.LasHeader(point_format=3, version="1.2"))

    offset = positions.min(axis=0)
    las.header.offsets = offset
    las.header.scales = np.array([0.001, 0.001, 0.001])

    las.x = positions[:, 0]
    las.y = positions[:, 1]
    las.z = positions[:, 2]

    if data['colors'] is not None:
        # Blender stores 0..255 uint8; LAS expects 0..65535 uint16.
        scale = float(((1 << _COLOR_BITS) - 1) / 255.0)
        las.red = (data['colors'][:, 0].astype(np.uint32) * scale).astype(np.uint16)
        las.green = (data['colors'][:, 1].astype(np.uint32) * scale).astype(np.uint16)
        las.blue = (data['colors'][:, 2].astype(np.uint32) * scale).astype(np.uint16)

    if data['intensity'] is not None:
        intensity = data['intensity']
        peak = float(intensity.max()) if intensity.size else 0.0
        if peak <= 1.0:
            intensity = intensity * float((1 << _COLOR_BITS) - 1)
        las.intensity = np.clip(intensity, 0, (1 << _COLOR_BITS) - 1).astype(np.uint16)

    if data['classification'] is not None:
        las.classification = np.clip(data['classification'], 0, 31).astype(np.uint8)

    if data['return_number'] is not None and data['number_of_returns'] is not None:
        las.return_number = np.clip(data['return_number'], 0, 7).astype(np.uint8)
        las.number_of_returns = np.clip(data['number_of_returns'], 0, 7).astype(np.uint8)

    las.write(filepath)
    return count
