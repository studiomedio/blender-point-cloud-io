"""PTS (Leica Cyclone text format) reader and writer.

PTS is a plain-text point cloud format introduced by Leica's Cyclone and
adopted by many terrestrial-scanner toolchains. Structurally it is XYZ with
a single header line:

    <point_count>
    x y z [intensity] [r g b]
    x y z [intensity] [r g b]
    ...

Supported column layouts on read (after the count line):
    3 columns  : x y z
    4 columns  : x y z intensity
    6 columns  : x y z r g b           (RGB; auto-detects 0..1 vs 0..255)
    7 columns  : x y z intensity r g b (Leica canonical)
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


def _read_pts(filepath):
    """Read a PTS file and return the data array (N, C) and the header count."""
    with open(filepath, 'r') as fh:
        first = fh.readline().strip()
        if not first:
            raise ValueError("PTS file is empty.")
        try:
            declared_count = int(first)
        except ValueError as err:
            raise ValueError(
                "PTS file does not start with a point-count integer; "
                "if this is a plain XYZ file, use the XYZ importer instead."
            ) from err

    # Read the data rows. `skiprows=1` skips the count header.
    arr = np.loadtxt(filepath, dtype=np.float64, skiprows=1, ndmin=2)

    if arr.shape[0] != declared_count:
        # Some writers lie about the count, or include trailing blank lines.
        # We trust what we actually read, but flag the mismatch.
        print(
            f"[Point Cloud I/O] PTS header declared {declared_count:,} points, "
            f"actually read {arr.shape[0]:,}. Using the actual count."
        )

    return arr, declared_count


def _interpret_columns(arr, want_colors):
    """Map a (N, C) float64 array to (positions, extras)."""
    if arr.shape[1] < 3:
        raise ValueError(
            f"PTS data row has only {arr.shape[1]} column(s); need at least 3 for x y z."
        )

    positions = arr[:, :3].astype(np.float32)
    extras = {}
    col_count = arr.shape[1]

    if col_count == 4:
        intensity = arr[:, 3].astype(np.float32)
        if intensity.size and intensity.max() > 1.0:
            intensity = intensity / max(float(intensity.max()), 1.0)
        extras['intensity'] = intensity
    elif col_count == 6 and want_colors:
        rgb = arr[:, 3:6].astype(np.float32)
        if rgb.max() > 1.0:
            rgb /= 255.0
        a = np.ones((rgb.shape[0], 1), dtype=np.float32)
        extras['color'] = np.concatenate((rgb, a), axis=1)
    elif col_count == 7:
        intensity = arr[:, 3].astype(np.float32)
        if intensity.size and intensity.max() > 1.0:
            intensity = intensity / max(float(intensity.max()), 1.0)
        extras['intensity'] = intensity
        if want_colors:
            rgb = arr[:, 4:7].astype(np.float32)
            if rgb.max() > 1.0:
                rgb /= 255.0
            a = np.ones((rgb.shape[0], 1), dtype=np.float32)
            extras['color'] = np.concatenate((rgb, a), axis=1)
    else:
        # Unrecognised column count: keep extras as opaque scalars.
        for offset, idx in enumerate(range(3, col_count)):
            extras[f'extra_{offset}'] = arr[:, idx].astype(np.float32)

    return positions, extras


def import_pts_file(
    context,
    filepath,
    *,
    import_colors,
    scale_factor,
    point_radius,
):
    """Read a PTS file and create a PointCloud object."""
    reset_selection(context)

    arr, _ = _read_pts(filepath)
    positions, extras = _interpret_columns(arr, import_colors)
    positions *= scale_factor

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    pc = build_point_cloud(context, base_name, positions, extras, point_radius)
    attach_material(pc, f"Mat_{base_name}", extras)
    return [pc]


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def export_pts_file(
    objects,
    filepath,
    *,
    apply_transforms,
    write_colors,
    write_intensity,
):
    """Write a single PTS file from one or more PointCloud objects.

    Output layout: count header line, then `x y z [intensity] [r g b]` per
    point. Columns are added only when the underlying attribute is present
    on every object — otherwise the file would be ragged.
    """
    if not objects:
        raise RuntimeError("No PointCloud objects to export.")

    positions_list, colors_list, intensity_list = [], [], []
    have_color = write_colors
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
        # PTS intensity is conventionally 16-bit signed (-2048..2047) for Leica
        # files. We write 0..2047 from our normalised 0..1 range so values stay
        # inside the typical envelope without negative numbers (which most PTS
        # readers handle fine, but positive-only is more portable).
        intensity = np.concatenate(intensity_list).astype(np.float64)
        intensity = np.clip(intensity * 2047.0, 0.0, 2047.0).astype(np.int32)
        columns.append(intensity)
        fmts.append('%d')

    if have_color:
        colors = np.concatenate(colors_list)
        columns.extend([colors[:, 0], colors[:, 1], colors[:, 2]])
        fmts.extend(['%d', '%d', '%d'])

    with open(filepath, 'w') as out:
        out.write(f"{total}\n")
        np.savetxt(out, np.column_stack(columns), fmt=' '.join(fmts))

    return total
