"""Point Cloud Data (.pcd) reader and writer.

PCD is the Point Cloud Library's native format. Each file has an ASCII header
followed by per-point data in `ascii`, `binary`, or `binary_compressed` form.

Read mapping (PCD field -> Blender point attribute):
    x, y, z                      -> position
    normal_x, normal_y, normal_z -> normal           (FLOAT_VECTOR)
    rgb / rgba (packed uint32)   -> color            (FLOAT_COLOR)
    intensity                    -> intensity        (FLOAT)
    other scalar fields          -> kept as-is

Write mapping (Blender -> PCD):
    position  -> x, y, z         (float32)
    normal    -> normal_x/y/z    (float32)
    color     -> rgb             (float32 packed: 0x00RRGGBB)
    intensity -> intensity       (float32)
    other FLOAT POINT-domain attributes go through as float32

binary_compressed (LZF) is not supported in this release — the reader raises a
clear error and points users to convert via `pcl_convert_pcd_ascii_binary` or
CloudCompare.
"""

import os
import struct

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
from ._lzf import lzf_compress, lzf_decompress


# PCD TYPE/SIZE combinations -> numpy dtype suffix.
_PCD_NUMPY_DTYPES = {
    ('I', 1): 'i1',
    ('I', 2): 'i2',
    ('I', 4): 'i4',
    ('I', 8): 'i8',
    ('U', 1): 'u1',
    ('U', 2): 'u2',
    ('U', 4): 'u4',
    ('U', 8): 'u8',
    ('F', 4): 'f4',
    ('F', 8): 'f8',
}


def _parse_header(file_handle):
    """Read the ASCII header. Returns (header_dict, data_mode_str)."""
    header = {
        'fields': None,
        'size': None,
        'type': None,
        'count': None,
        'width': None,
        'height': 1,
        'points': None,
    }
    while True:
        raw = file_handle.readline()
        if not raw:
            raise ValueError("Unexpected end of file in PCD header.")
        line = raw.decode('ascii', errors='replace').strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split()
        keyword = parts[0].upper()
        values = parts[1:]
        if keyword == 'DATA':
            mode = values[0].lower() if values else 'ascii'
            if mode not in ('ascii', 'binary', 'binary_compressed'):
                raise ValueError(f"Unsupported PCD DATA mode: {mode!r}")
            # Fill in derived values.
            if header['fields'] is None:
                raise ValueError("PCD header missing FIELDS entry.")
            if header['count'] is None:
                header['count'] = [1] * len(header['fields'])
            if header['points'] is None:
                if header['width'] is not None and header['height'] is not None:
                    header['points'] = header['width'] * header['height']
                else:
                    raise ValueError("PCD header missing POINTS / WIDTH / HEIGHT.")
            return header, mode
        if keyword == 'FIELDS':
            header['fields'] = values
        elif keyword == 'TYPE':
            header['type'] = [v.upper() for v in values]
        elif keyword == 'SIZE':
            header['size'] = [int(v) for v in values]
        elif keyword == 'COUNT':
            header['count'] = [int(v) for v in values]
        elif keyword == 'WIDTH':
            header['width'] = int(values[0])
        elif keyword == 'HEIGHT':
            header['height'] = int(values[0])
        elif keyword == 'POINTS':
            header['points'] = int(values[0])


def _dtype_for_field(header, field_index):
    type_char = header['type'][field_index]
    size = header['size'][field_index]
    np_type = _PCD_NUMPY_DTYPES.get((type_char, size))
    if np_type is None:
        raise ValueError(f"Unsupported PCD field type/size: {type_char}{size}")
    return np_type


def _read_data_binary(file_handle, header):
    fields = header['fields']
    counts = header['count']
    points = header['points']

    # Build a structured dtype that mirrors the on-disk layout.
    dtype_entries = []
    for idx, name in enumerate(fields):
        np_type = _dtype_for_field(header, idx)
        if counts[idx] == 1:
            dtype_entries.append((name, '<' + np_type))
        else:
            dtype_entries.append((name, '<' + np_type, counts[idx]))
    dtype = np.dtype(dtype_entries)

    raw = file_handle.read(points * dtype.itemsize)
    if len(raw) != points * dtype.itemsize:
        raise ValueError("PCD file ended before all binary data was read.")
    array = np.frombuffer(raw, dtype=dtype, count=points)

    data = {}
    for idx, name in enumerate(fields):
        if counts[idx] == 1:
            data[name] = array[name].copy()
        else:
            # Split into per-component arrays so downstream code can mix them.
            for c in range(counts[idx]):
                data[f"{name}_{c}"] = array[name][:, c].copy()
    return data


def _read_data_binary_compressed(file_handle, header):
    """Read the LZF-compressed SoA payload of a PCD binary_compressed file.

    Layout after the header newline:
        uint32 LE  compressed_size
        uint32 LE  uncompressed_size
        compressed_size bytes  LZF-compressed Structure-of-Arrays buffer

    The decompressed buffer concatenates one packed array per field,
    in declaration order — NOT interleaved like `binary` mode.
    """
    fields = header['fields']
    counts = header['count']
    points = header['points']

    size_header = file_handle.read(8)
    if len(size_header) != 8:
        raise ValueError("PCD binary_compressed: missing size header.")
    compressed_size, uncompressed_size = struct.unpack('<II', size_header)

    compressed = file_handle.read(compressed_size)
    if len(compressed) != compressed_size:
        raise ValueError(
            f"PCD binary_compressed: expected {compressed_size} compressed bytes, "
            f"got {len(compressed)}."
        )

    buf = lzf_decompress(compressed, uncompressed_size)

    data = {}
    offset = 0
    for idx, name in enumerate(fields):
        np_type = _dtype_for_field(header, idx)
        elem_size = np.dtype(np_type).itemsize
        block_size = points * counts[idx] * elem_size

        if offset + block_size > uncompressed_size:
            raise ValueError("PCD binary_compressed: field block overruns buffer.")

        array = np.frombuffer(
            buf, dtype='<' + np_type, count=points * counts[idx], offset=offset
        )
        if counts[idx] == 1:
            data[name] = array.copy()
        else:
            reshaped = array.reshape(points, counts[idx])
            for c in range(counts[idx]):
                data[f"{name}_{c}"] = reshaped[:, c].copy()

        offset += block_size

    return data


def _read_data_ascii(file_handle, header):
    fields = header['fields']
    counts = header['count']
    points = header['points']

    column_count = sum(counts)
    arr = np.loadtxt(file_handle, max_rows=points, dtype=np.float64, ndmin=2)
    if arr.shape[0] != points or arr.shape[1] != column_count:
        raise ValueError("PCD ASCII data did not match POINTS × total-COUNT.")

    data = {}
    column = 0
    for idx, name in enumerate(fields):
        np_type = _dtype_for_field(header, idx)
        if counts[idx] == 1:
            data[name] = arr[:, column].astype(np_type)
            column += 1
        else:
            for c in range(counts[idx]):
                data[f"{name}_{c}"] = arr[:, column].astype(np_type)
                column += 1
    return data


def _unpack_rgb(packed):
    """PCL packs RGB into a single value (float32 or uint32) as 0x00RRGGBB."""
    if packed.dtype != np.uint32:
        packed_uint32 = packed.view(np.uint32) if packed.dtype.itemsize == 4 else packed.astype(np.uint32)
    else:
        packed_uint32 = packed
    r = ((packed_uint32 >> 16) & 0xFF).astype(np.float32) / 255.0
    g = ((packed_uint32 >> 8) & 0xFF).astype(np.float32) / 255.0
    b = (packed_uint32 & 0xFF).astype(np.float32) / 255.0
    return r, g, b


def _split_extras(data, want_colors, want_normals):
    for required in ('x', 'y', 'z'):
        if required not in data:
            raise ValueError(f"PCD file missing required field '{required}'.")

    positions = np.column_stack(
        (data['x'].astype(np.float32),
         data['y'].astype(np.float32),
         data['z'].astype(np.float32))
    )

    extras = {}
    handled = {'x', 'y', 'z'}

    if want_colors and 'rgb' in data:
        r, g, b = _unpack_rgb(np.asarray(data['rgb']))
        a = np.ones_like(r)
        extras['color'] = np.column_stack((r, g, b, a))
        handled.add('rgb')
    elif want_colors and 'rgba' in data:
        packed = np.asarray(data['rgba'])
        if packed.dtype.itemsize == 4:
            packed_uint32 = packed.view(np.uint32) if packed.dtype != np.uint32 else packed
        else:
            packed_uint32 = packed.astype(np.uint32)
        r = ((packed_uint32 >> 16) & 0xFF).astype(np.float32) / 255.0
        g = ((packed_uint32 >> 8) & 0xFF).astype(np.float32) / 255.0
        b = (packed_uint32 & 0xFF).astype(np.float32) / 255.0
        a = ((packed_uint32 >> 24) & 0xFF).astype(np.float32) / 255.0
        extras['color'] = np.column_stack((r, g, b, a))
        handled.add('rgba')

    if want_normals and {'normal_x', 'normal_y', 'normal_z'}.issubset(data):
        extras['normal'] = np.column_stack(
            (data['normal_x'].astype(np.float32),
             data['normal_y'].astype(np.float32),
             data['normal_z'].astype(np.float32))
        )
        handled |= {'normal_x', 'normal_y', 'normal_z'}

    for name, values in data.items():
        if name in handled:
            continue
        arr = np.asarray(values)
        if arr.ndim == 1:
            extras[name] = arr

    return positions, extras


def import_pcd_file(
    context,
    filepath,
    *,
    import_colors,
    import_normals,
    scale_factor,
    point_radius,
):
    """Read a PCD file and create a PointCloud object."""
    reset_selection(context)

    with open(filepath, 'rb') as file_handle:
        header, mode = _parse_header(file_handle)
        if mode == 'binary_compressed':
            data = _read_data_binary_compressed(file_handle, header)
        elif mode == 'binary':
            data = _read_data_binary(file_handle, header)
        else:
            data = _read_data_ascii(file_handle, header)

    positions, extras = _split_extras(data, import_colors, import_normals)
    positions *= scale_factor

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    pc = build_point_cloud(context, base_name, positions, extras, point_radius)
    attach_material(pc, f"Mat_{base_name}", extras)
    return [pc]


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


def _pack_rgb(colors_uint8):
    """Pack uint8 (N, 3) RGB columns into a (N,) float32 array as PCL expects."""
    r = colors_uint8[:, 0].astype(np.uint32)
    g = colors_uint8[:, 1].astype(np.uint32)
    b = colors_uint8[:, 2].astype(np.uint32)
    packed = (r << 16) | (g << 8) | b
    return packed.astype(np.uint32).view(np.float32)


def export_pcd_file(
    objects,
    filepath,
    *,
    mode,
    apply_transforms,
):
    """Write a single PCD from one or more PointCloud objects.

    `mode` is one of ``'ascii'``, ``'binary'``, or ``'binary_compressed'``.

    Multiple selected objects are concatenated into a single unordered cloud
    (HEIGHT = 1). PCD is a flat single-cloud format; there's no per-scan slot.

    Returns the total number of points written.
    """
    if mode not in ('ascii', 'binary', 'binary_compressed'):
        raise ValueError(f"Unknown PCD write mode: {mode!r}")
    if not objects:
        raise RuntimeError("No PointCloud objects to export.")

    positions_list, colors_list, normals_list, intensity_list = [], [], [], []
    have_color = True
    have_normal = True
    have_intensity = True

    for obj in objects:
        attrs = obj.data.attributes
        if 'position' not in attrs:
            continue
        count = len(attrs['position'].data)
        if count == 0:
            continue

        positions_list.append(get_positions(obj, count, apply_transforms))

        colors = get_colors_uint8(obj, count)
        if colors is None:
            have_color = False
        else:
            colors_list.append(colors)

        normals = get_normals(obj, count, apply_transforms)
        if normals is None:
            have_normal = False
        else:
            normals_list.append(normals)

        intensity = get_scalar(obj, count, 'intensity')
        if intensity is None:
            have_intensity = False
        else:
            intensity_list.append(intensity)

    if not positions_list:
        raise RuntimeError("Selected PointCloud objects contain no points.")

    positions = np.concatenate(positions_list).astype(np.float32)
    total = len(positions)

    fields = ['x', 'y', 'z']
    sizes = [4, 4, 4]
    types = ['F', 'F', 'F']
    counts = [1, 1, 1]
    columns = [positions[:, 0], positions[:, 1], positions[:, 2]]

    if have_normal:
        normals = np.concatenate(normals_list).astype(np.float32)
        fields.extend(['normal_x', 'normal_y', 'normal_z'])
        sizes.extend([4, 4, 4])
        types.extend(['F', 'F', 'F'])
        counts.extend([1, 1, 1])
        columns.extend([normals[:, 0], normals[:, 1], normals[:, 2]])

    if have_color:
        colors = np.concatenate(colors_list)
        rgb = _pack_rgb(colors)
        fields.append('rgb')
        sizes.append(4)
        types.append('F')
        counts.append(1)
        columns.append(rgb)

    if have_intensity:
        intensity = np.concatenate(intensity_list).astype(np.float32)
        fields.append('intensity')
        sizes.append(4)
        types.append('F')
        counts.append(1)
        columns.append(intensity)

    header_text = (
        "# .PCD v0.7 - Point Cloud Data file format\n"
        "VERSION 0.7\n"
        f"FIELDS {' '.join(fields)}\n"
        f"SIZE {' '.join(str(s) for s in sizes)}\n"
        f"TYPE {' '.join(types)}\n"
        f"COUNT {' '.join(str(c) for c in counts)}\n"
        f"WIDTH {total}\n"
        "HEIGHT 1\n"
        "VIEWPOINT 0 0 0 1 0 0 0\n"
        f"POINTS {total}\n"
        f"DATA {mode}\n"
    )

    if mode == 'ascii':
        with open(filepath, 'w') as out:
            out.write(header_text)
            np.savetxt(
                out,
                np.column_stack(columns),
                fmt=' '.join('%.6f' for _ in columns),
            )
        return total

    if mode == 'binary':
        dtype = np.dtype([(name, '<f4') for name in fields])
        structured = np.empty(total, dtype=dtype)
        for name, col in zip(fields, columns):
            structured[name] = col.astype(np.float32)
        with open(filepath, 'wb') as out:
            out.write(header_text.encode('ascii'))
            out.write(structured.tobytes())
        return total

    # binary_compressed: payload is Structure-of-Arrays — each field's packed
    # bytes appear consecutively, not interleaved per-point.
    soa = bytearray()
    for col in columns:
        soa.extend(col.astype(np.float32).tobytes())
    uncompressed_size = len(soa)
    compressed = lzf_compress(bytes(soa))

    with open(filepath, 'wb') as out:
        out.write(header_text.encode('ascii'))
        out.write(struct.pack('<II', len(compressed), uncompressed_size))
        out.write(compressed)

    return total
