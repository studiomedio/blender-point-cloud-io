"""XYZ point cloud reader and writer.

XYZ is the simplest possible point cloud format: one point per line, columns
separated by whitespace or comma. There is no header — the column layout is
inferred from the first non-comment data line. Comment lines starting with `#`
are skipped.

Supported column layouts on read:
    3 columns  : x y z
    4 columns  : x y z intensity
    6 columns  : x y z r g b               (RGB; auto-detects 0..1 vs 0..255)
    7 columns  : x y z intensity r g b
    9 columns  : x y z r g b nx ny nz
    other      : first 3 columns become positions; the rest are stored as
                 extra_0, extra_1, ... FLOAT attributes
"""

import os

import bpy
import numpy as np

from ._common import (
    attach_material,
    build_point_cloud,
    get_colors_uint8,
    get_normals,
    get_positions,
    get_scalar,
    reset_selection,
)


def _detect_separator(first_data_line):
    """Heuristic: comma if the first line has at least one, else whitespace."""
    return ',' if ',' in first_data_line else None  # None = any whitespace for np.loadtxt


def _read_columns(filepath):
    """Read all data rows from an XYZ file as a 2-D float64 array."""
    with open(filepath, 'r') as fh:
        # Peek to detect separator and count columns.
        first = None
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            first = stripped
            break

    if first is None:
        raise ValueError("XYZ file has no data rows.")

    sep = _detect_separator(first)

    # np.loadtxt is happy to take a file path, skip '#'-prefixed lines, and
    # auto-detect whitespace separators. For commas we pass explicit `,`.
    return np.loadtxt(filepath, comments='#', delimiter=sep, dtype=np.float64, ndmin=2)


def _interpret_columns(arr, want_colors, want_normals):
    """Map a (N, C) float64 array to (positions, extras) based on column count."""
    if arr.shape[1] < 3:
        raise ValueError(
            f"XYZ file has only {arr.shape[1]} column(s); need at least 3 for x y z."
        )

    positions = arr[:, :3].astype(np.float32)
    extras = {}
    col_count = arr.shape[1]
    remaining_start = 3

    if col_count == 4:
        extras['intensity'] = arr[:, 3].astype(np.float32)
        remaining_start = 4
    elif col_count == 6 and want_colors:
        rgb = arr[:, 3:6].astype(np.float32)
        if rgb.max() > 1.0:
            rgb /= 255.0
        a = np.ones((rgb.shape[0], 1), dtype=np.float32)
        extras['color'] = np.concatenate((rgb, a), axis=1)
        remaining_start = 6
    elif col_count == 7 and want_colors:
        extras['intensity'] = arr[:, 3].astype(np.float32)
        rgb = arr[:, 4:7].astype(np.float32)
        if rgb.max() > 1.0:
            rgb /= 255.0
        a = np.ones((rgb.shape[0], 1), dtype=np.float32)
        extras['color'] = np.concatenate((rgb, a), axis=1)
        remaining_start = 7
    elif col_count == 9 and want_colors and want_normals:
        rgb = arr[:, 3:6].astype(np.float32)
        if rgb.max() > 1.0:
            rgb /= 255.0
        a = np.ones((rgb.shape[0], 1), dtype=np.float32)
        extras['color'] = np.concatenate((rgb, a), axis=1)
        extras['normal'] = arr[:, 6:9].astype(np.float32)
        remaining_start = 9

    # Any leftover columns become opaque scalar FLOAT attributes.
    for offset, idx in enumerate(range(remaining_start, col_count)):
        extras[f'extra_{offset}'] = arr[:, idx].astype(np.float32)

    return positions, extras


def import_xyz_file(
    context,
    filepath,
    *,
    import_colors,
    import_normals,
    scale_factor,
    point_radius,
):
    """Read an XYZ file and create a PointCloud object."""
    reset_selection(context)

    arr = _read_columns(filepath)
    positions, extras = _interpret_columns(arr, import_colors, import_normals)
    positions *= scale_factor

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    pc = build_point_cloud(context, base_name, positions, extras, point_radius)
    attach_material(pc, f"Mat_{base_name}", extras)
    return [pc]


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def export_xyz_file(
    objects,
    filepath,
    *,
    apply_transforms,
    write_colors,
    write_normals,
    write_intensity,
):
    """Write a single XYZ file from one or more PointCloud objects.

    Column order: x y z [intensity] [r g b] [nx ny nz]. Extra columns are added
    only when the underlying attribute is actually present on every object —
    otherwise the file would be ragged.
    """
    if not objects:
        raise RuntimeError("No PointCloud objects to export.")

    positions_list, colors_list, normals_list, intensity_list = [], [], [], []
    have_color = write_colors
    have_normal = write_normals
    have_intensity = write_intensity

    for obj in objects:
        attrs = obj.data.attributes
        if 'position' not in attrs:
            continue
        count = len(attrs['position'].data)
        if count == 0:
            continue

        positions_list.append(get_positions(obj, count, apply_transforms))

        if have_color:
            c = get_colors_uint8(obj, count)
            if c is None:
                have_color = False
            else:
                colors_list.append(c)

        if have_normal:
            n = get_normals(obj, count, apply_transforms)
            if n is None:
                have_normal = False
            else:
                normals_list.append(n)

        if have_intensity:
            i = get_scalar(obj, count, 'intensity')
            if i is None:
                have_intensity = False
            else:
                intensity_list.append(i)

    if not positions_list:
        raise RuntimeError("Selected PointCloud objects contain no points.")

    positions = np.concatenate(positions_list).astype(np.float64)
    total = len(positions)
    columns = [positions[:, 0], positions[:, 1], positions[:, 2]]
    fmts = ['%.6f', '%.6f', '%.6f']

    if have_intensity:
        columns.append(np.concatenate(intensity_list).astype(np.float64))
        fmts.append('%.6f')

    if have_color:
        colors = np.concatenate(colors_list)
        columns.extend([colors[:, 0], colors[:, 1], colors[:, 2]])
        fmts.extend(['%d', '%d', '%d'])

    if have_normal:
        normals = np.concatenate(normals_list).astype(np.float64)
        columns.extend([normals[:, 0], normals[:, 1], normals[:, 2]])
        fmts.extend(['%.6f', '%.6f', '%.6f'])

    np.savetxt(filepath, np.column_stack(columns), fmt=' '.join(fmts))
    return total
