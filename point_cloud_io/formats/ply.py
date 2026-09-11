"""Pure-Python PLY reader and writer for PointCloud objects.

Handles the Stanford Polygon Format in ASCII and binary (little- and
big-endian) variants. Only the 'vertex' element is interpreted; other
elements are skipped if present.

Read mapping (PLY -> Blender point attribute):
    x, y, z         -> position
    nx, ny, nz      -> normal           (FLOAT_VECTOR)
    red, green, blue, alpha -> color    (FLOAT_COLOR, normalised to 0..1)
    everything else -> kept as-is       (FLOAT scalar attribute)

Write mapping (Blender -> PLY):
    position        -> x, y, z            (float)
    normal role     -> nx, ny, nz         (float)
    color role      -> red, green, blue   (uchar 0..255)
    FLOAT scalar    -> <name>             (float)
    INT / INT8      -> <name>             (int)
    BOOLEAN         -> <name>             (uchar)
    FLOAT_VECTOR    -> <name>_x/_y/_z     (float)
    FLOAT2          -> <name>_x/_y        (float)
    FLOAT_COLOR     -> <name>_r/_g/_b     (uchar 0..255)

Which attribute fills the normal and color roles is resolved by `_attrs` —
the canonical names by default, an export-dialog override otherwise.
"""

import os

import bpy
import numpy as np

from ._attrs import AUTO, resolve, suppressed_name
from ._common import (
    attach_material,
    build_point_cloud,
    get_colors_uint8,
    get_int_scalar,
    get_normals,
    get_positions,
    get_scalar,
    reset_selection,
)


_PLY_TO_NUMPY = {
    'char': 'i1', 'int8': 'i1',
    'uchar': 'u1', 'uint8': 'u1',
    'short': 'i2', 'int16': 'i2',
    'ushort': 'u2', 'uint16': 'u2',
    'int': 'i4', 'int32': 'i4',
    'uint': 'u4', 'uint32': 'u4',
    'float': 'f4', 'float32': 'f4',
    'double': 'f8', 'float64': 'f8',
}

_PLY_POSITION_HANDLED = frozenset({'x', 'y', 'z'})
_PLY_NORMAL_HANDLED = frozenset({'nx', 'ny', 'nz'})
_PLY_COLOR_HANDLED = frozenset({'red', 'green', 'blue', 'alpha'})


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


def _parse_header(file_handle):
    """Parse a PLY header and return (format_str, elements).

    elements is a list of dicts: {'name': str, 'count': int, 'properties': list}
    Each property is a dict: {'kind': 'scalar' | 'list', 'type': str, 'name': str,
                              'count_type': str (list only)}.
    """
    first = file_handle.readline().strip()
    if first != b'ply':
        raise ValueError("Not a PLY file (missing 'ply' magic line).")

    format_str = None
    elements = []
    current = None

    while True:
        raw = file_handle.readline()
        if not raw:
            raise ValueError("Unexpected end of file while reading header.")
        line = raw.strip()

        if line == b'end_header':
            break
        if not line or line.startswith(b'comment') or line.startswith(b'obj_info'):
            continue

        parts = line.split()
        keyword = parts[0]

        if keyword == b'format':
            format_str = parts[1].decode()
            if format_str not in ('ascii', 'binary_little_endian', 'binary_big_endian'):
                raise ValueError(f"Unsupported PLY format: {format_str}")
        elif keyword == b'element':
            current = {
                'name': parts[1].decode(),
                'count': int(parts[2]),
                'properties': [],
            }
            elements.append(current)
        elif keyword == b'property':
            if current is None:
                raise ValueError("'property' line before any 'element'.")
            if parts[1] == b'list':
                current['properties'].append({
                    'kind': 'list',
                    'count_type': parts[2].decode(),
                    'type': parts[3].decode(),
                    'name': parts[4].decode(),
                })
            else:
                current['properties'].append({
                    'kind': 'scalar',
                    'type': parts[1].decode(),
                    'name': parts[2].decode(),
                })

    if format_str is None:
        raise ValueError("PLY header has no 'format' line.")

    return format_str, elements


def _read_binary_vertex(file_handle, properties, count, endian_prefix):
    """Read a vertex element with only scalar properties as a structured array."""
    fields = []
    for prop in properties:
        if prop['kind'] != 'scalar':
            raise ValueError(
                "PLY list properties on the 'vertex' element are not supported."
            )
        np_type = _PLY_TO_NUMPY.get(prop['type'])
        if np_type is None:
            raise ValueError(f"Unsupported PLY property type: {prop['type']}")
        fields.append((prop['name'], endian_prefix + np_type))

    dtype = np.dtype(fields)
    raw = file_handle.read(count * dtype.itemsize)
    if len(raw) != count * dtype.itemsize:
        raise ValueError("PLY file ended before vertex data was complete.")
    array = np.frombuffer(raw, dtype=dtype, count=count)
    return {prop['name']: array[prop['name']].copy() for prop in properties}


def _skip_binary_element(file_handle, element, endian_prefix):
    """Advance past a non-vertex binary element."""
    if any(prop['kind'] == 'list' for prop in element['properties']):
        for _ in range(element['count']):
            for prop in element['properties']:
                if prop['kind'] == 'list':
                    count_dtype = np.dtype(endian_prefix + _PLY_TO_NUMPY[prop['count_type']])
                    item_dtype = np.dtype(endian_prefix + _PLY_TO_NUMPY[prop['type']])
                    n = int(np.frombuffer(file_handle.read(count_dtype.itemsize),
                                          dtype=count_dtype, count=1)[0])
                    file_handle.read(n * item_dtype.itemsize)
                else:
                    item_dtype = np.dtype(endian_prefix + _PLY_TO_NUMPY[prop['type']])
                    file_handle.read(item_dtype.itemsize)
    else:
        row_size = sum(np.dtype(_PLY_TO_NUMPY[p['type']]).itemsize
                       for p in element['properties'])
        file_handle.read(element['count'] * row_size)


def _read_ascii_vertex(file_handle, properties, count):
    """Read a vertex element from an ASCII PLY (loadtxt-based, vectorised)."""
    if any(prop['kind'] == 'list' for prop in properties):
        raise ValueError(
            "PLY list properties on the 'vertex' element are not supported."
        )

    column_dtypes = [_PLY_TO_NUMPY[p['type']] for p in properties]
    column_names = [p['name'] for p in properties]

    arr = np.loadtxt(file_handle, max_rows=count, dtype=np.float64, ndmin=2)
    if arr.shape[0] != count:
        raise ValueError("PLY file ended before vertex data was complete.")

    data = {}
    for idx, (name, dt) in enumerate(zip(column_names, column_dtypes)):
        data[name] = arr[:, idx].astype(dt)
    return data


def _read_vertex_data(file_handle, elements, format_str):
    endian_prefix = '<' if format_str == 'binary_little_endian' else (
        '>' if format_str == 'binary_big_endian' else ''
    )

    data = None
    for element in elements:
        if element['name'] == 'vertex':
            if format_str == 'ascii':
                data = _read_ascii_vertex(file_handle, element['properties'], element['count'])
            else:
                data = _read_binary_vertex(
                    file_handle, element['properties'], element['count'], endian_prefix
                )
        elif format_str != 'ascii':
            _skip_binary_element(file_handle, element, endian_prefix)
        else:
            # ASCII: skip lines (count is rows for non-list elements; we don't
            # bother supporting list-bearing non-vertex elements in ASCII).
            for _ in range(element['count']):
                file_handle.readline()

    if data is None:
        raise ValueError("PLY file has no 'vertex' element.")
    return data


def _split_extras(data, want_colors, want_normals):
    """Split a vertex data dict into (positions, extras) honoring user flags."""
    for required in ('x', 'y', 'z'):
        if required not in data:
            raise ValueError(f"PLY vertex element missing '{required}' property.")

    positions = np.column_stack((data['x'], data['y'], data['z'])).astype(np.float32)

    extras = {}

    if want_colors and {'red', 'green', 'blue'}.issubset(data):
        r = np.asarray(data['red'], dtype=np.float32)
        g = np.asarray(data['green'], dtype=np.float32)
        b = np.asarray(data['blue'], dtype=np.float32)
        peak = max(
            r.max() if r.size else 0.0,
            g.max() if g.size else 0.0,
            b.max() if b.size else 0.0,
        )
        if peak > 1.0:
            r /= 255.0
            g /= 255.0
            b /= 255.0
        if 'alpha' in data:
            a = np.asarray(data['alpha'], dtype=np.float32)
            if peak > 1.0:
                a /= 255.0
        else:
            a = np.ones_like(r)
        extras['color'] = np.column_stack((r, g, b, a))

    if want_normals and _PLY_NORMAL_HANDLED.issubset(data):
        extras['normal'] = np.column_stack(
            (data['nx'], data['ny'], data['nz'])
        ).astype(np.float32)

    handled = set(_PLY_POSITION_HANDLED)
    if 'color' in extras:
        handled |= _PLY_COLOR_HANDLED
    if 'normal' in extras:
        handled |= _PLY_NORMAL_HANDLED

    for name, values in data.items():
        if name in handled:
            continue
        arr = np.asarray(values, dtype=np.float32)
        if arr.ndim == 1:
            extras[name] = arr

    return positions, extras


def import_ply_file(
    context,
    filepath,
    *,
    import_colors,
    import_normals,
    scale_factor,
    point_radius,
):
    """Read a PLY file and create a PointCloud object in the scene."""
    reset_selection(context)

    with open(filepath, 'rb') as file_handle:
        format_str, elements = _parse_header(file_handle)
        data = _read_vertex_data(file_handle, elements, format_str)

    positions, extras = _split_extras(data, import_colors, import_normals)
    positions *= scale_factor

    base_name = os.path.splitext(os.path.basename(filepath))[0]
    pc = build_point_cloud(context, base_name, positions, extras, point_radius)
    attach_material(pc, f"Mat_{base_name}", extras)
    return [pc]


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


# Per-object property record:
#   (ply_name, ply_type, attr_name, sub_index, kind)
# attr_name is the Blender attribute; sub_index picks the component (0..n-1)
# for vector / color attributes, or 0 for scalar attributes. `kind` tells the
# column reader how to interpret the source — 'position' and 'normal' need the
# world transform, 'color' needs 0..1 -> 0..255 scaling, 'scalar' is verbatim.

_PLY_VECTOR_AXES = ('x', 'y', 'z')
_PLY_COLOR_CHANNELS = ('r', 'g', 'b')


def _build_writer_properties(obj, overrides=None):
    overrides = overrides or {}
    attrs = obj.data.attributes
    if 'position' not in attrs:
        return None, "Point cloud has no 'position' attribute."

    props = [
        ('x', 'float', 'position', 0, 'position'),
        ('y', 'float', 'position', 1, 'position'),
        ('z', 'float', 'position', 2, 'position'),
    ]
    handled = {'position', 'radius'}

    # A role set to None must not reappear as generic per-component columns,
    # so the attribute it would have used is suppressed outright.
    for role_key in ('normal', 'color'):
        omitted = suppressed_name(obj, role_key, overrides.get(role_key, AUTO))
        if omitted is not None:
            handled.add(omitted)

    normal_name = resolve(obj, 'normal', overrides.get('normal', AUTO))
    if normal_name is not None:
        props.extend([
            ('nx', 'float', normal_name, 0, 'normal'),
            ('ny', 'float', normal_name, 1, 'normal'),
            ('nz', 'float', normal_name, 2, 'normal'),
        ])
        handled.add(normal_name)

    color_name = resolve(obj, 'color', overrides.get('color', AUTO))
    if color_name is not None:
        props.extend([
            ('red',   'uchar', color_name, 0, 'color'),
            ('green', 'uchar', color_name, 1, 'color'),
            ('blue',  'uchar', color_name, 2, 'color'),
        ])
        handled.add(color_name)

    for attr in attrs:
        if attr.domain != 'POINT' or attr.name in handled or attr.name.startswith('.'):
            continue
        dt = attr.data_type
        name = attr.name
        if dt == 'FLOAT':
            props.append((name, 'float', name, 0, 'scalar'))
        elif dt in ('INT', 'INT8'):
            props.append((name, 'int', name, 0, 'scalar'))
        elif dt == 'BOOLEAN':
            props.append((name, 'uchar', name, 0, 'scalar'))
        # Multi-component attributes that no role claimed still round-trip if
        # each component gets its own column, which is what other PLY writers
        # do. Dropping them is what made unrecognised names disappear.
        elif dt == 'FLOAT_VECTOR':
            props.extend(
                (f"{name}_{axis}", 'float', name, index, 'vector3')
                for index, axis in enumerate(_PLY_VECTOR_AXES)
            )
        elif dt == 'FLOAT2':
            props.extend(
                (f"{name}_{axis}", 'float', name, index, 'vector2')
                for index, axis in enumerate(_PLY_VECTOR_AXES[:2])
            )
        elif dt in ('FLOAT_COLOR', 'BYTE_COLOR'):
            props.extend(
                (f"{name}_{channel}", 'uchar', name, index, 'color')
                for index, channel in enumerate(_PLY_COLOR_CHANNELS)
            )

    return props, None


def _read_attr_column(obj, count, attr_name, sub_index, ply_type, kind, apply_transforms):
    """Pull one PLY column from the object's attributes (with transforms)."""
    np_type = _PLY_TO_NUMPY[ply_type]
    missing = np.zeros(count, dtype=np_type)

    if kind == 'position':
        positions = get_positions(obj, count, apply_transforms)
        return positions[:, sub_index].astype(np_type)

    if kind == 'normal':
        normals = get_normals(obj, count, apply_transforms, attr_name)
        return missing if normals is None else normals[:, sub_index].astype(np_type)

    if kind == 'color':
        colors = get_colors_uint8(obj, count, attr_name)
        return missing if colors is None else colors[:, sub_index].astype(np_type)

    if kind in ('vector3', 'vector2'):
        attr = obj.data.attributes.get(attr_name)
        if attr is None:
            return missing
        width = 3 if kind == 'vector3' else 2
        arr = np.empty(count * width, dtype=np.float32)
        attr.data.foreach_get('vector', arr)
        return arr.reshape(-1, width)[:, sub_index].astype(np_type)

    values = (
        get_scalar(obj, count, attr_name)
        if ply_type in ('float', 'double')
        else get_int_scalar(obj, count, attr_name)
    )
    return missing if values is None else values.astype(np_type)


def export_ply_file(
    objects,
    filepath,
    *,
    use_ascii,
    apply_transforms,
    overrides=None,
):
    """Write a list of PointCloud objects as a single PLY file.

    All objects are concatenated into one vertex element. The property layout
    of the first object determines the PLY columns; subsequent objects must
    share the same attribute set or missing fields will be zero-filled.

    `overrides` maps attribute roles ('color', 'normal') to a source attribute
    name, or to the AUTO / NONE sentinels; see `_attrs`. Attributes no role
    claims are still written through under their own name.

    Returns the total number of points written.
    """
    if not objects:
        raise RuntimeError("No PointCloud objects to export.")

    properties, error = _build_writer_properties(objects[0], overrides)
    if error:
        raise RuntimeError(error)

    total_count = sum(
        len(obj.data.attributes['position'].data)
        for obj in objects
        if 'position' in obj.data.attributes
    )
    if total_count == 0:
        raise RuntimeError("Selected PointCloud objects contain no points.")

    mode = 'w' if use_ascii else 'wb'
    with open(filepath, mode) as out:
        def write(line):
            if use_ascii:
                out.write(line)
            else:
                out.write(line.encode())

        write("ply\n")
        write(f"format {'ascii' if use_ascii else 'binary_little_endian'} 1.0\n")
        write(f"element vertex {total_count}\n")
        for ply_name, ply_type, _, _, _ in properties:
            write(f"property {ply_type} {ply_name}\n")
        write("end_header\n")

        binary_dtype = np.dtype([
            (ply_name, '<' + _PLY_TO_NUMPY[ply_type])
            for ply_name, ply_type, _, _, _ in properties
        ])

        for obj in objects:
            if 'position' not in obj.data.attributes:
                continue
            count = len(obj.data.attributes['position'].data)
            if count == 0:
                continue

            columns = [
                _read_attr_column(
                    obj, count, attr_name, sub_index, ply_type, kind, apply_transforms
                )
                for _, ply_type, attr_name, sub_index, kind in properties
            ]

            if use_ascii:
                fmts = []
                for _, ply_type, _, _, _ in properties:
                    if ply_type == 'float':
                        fmts.append('%.6f')
                    else:
                        fmts.append('%d')
                np.savetxt(out, np.column_stack(columns), fmt=' '.join(fmts))
            else:
                structured = np.empty(count, dtype=binary_dtype)
                for (ply_name, _, _, _, _), col in zip(properties, columns):
                    structured[ply_name] = col
                out.write(structured.tobytes())

    return total_count
