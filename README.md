# Point Cloud I/O for Blender

A Blender 5.0+ extension for importing and exporting point cloud files. Built around Blender's native **PointCloud** object type.

## Supported formats

| Format | Import | Export |
|--------|:------:|:------:|
| E57 (`.e57`) | ✅ | ✅ (no normals) |

Other formats (LAS/LAZ, PCD, XYZ, PLY) are planned.

## About E57

ASTM E57 is a compact, vendor-neutral container for point clouds, images, and metadata produced by 3D imaging systems — LiDAR, terrestrial laser scanners, structured-light rigs. A single `.e57` file can carry multiple scans, each with its own pose, color, intensity, and (via extensions) normals.

- [libe57.org](http://www.libe57.org/) — official format home and specification
- [Sample E57 files](http://www.libe57.org/data.html) — public test datasets (Stanford bunny, scan stations, etc.)
- [Coordinate system conventions](http://www.libe57.org/bestCoordinates.html) — how scanners encode pose and orientation; useful when imported clouds appear flipped or rotated

## Requirements

- **Blender 5.0** or newer (Python 3.13)

The required Python wheels (`pye57`, `pyquaternion`) are bundled with the extension — no internet needed at install time.

## Installation

1. Build a ZIP from the `point_cloud_io/` directory (or download a release):

   ```bash
   cd point_cloud_io
   zip -r ../point_cloud_io.zip .
   ```

2. In Blender: `Edit > Preferences > Get Extensions`.
3. Click the drop-down (top right) → **Install from Disk**.
4. Pick `point_cloud_io.zip` and enable the extension.

## Usage

### Importing E57

`File > Import > E57 Point Cloud (.e57)`

Options in the sidebar:

- **Colors** — extract RGB and write a `color` point attribute.
- **Normals** — extract normal vectors as a `normal` point attribute.
- **Intensity** — extract scalar intensity (LiDAR return strength) normalised to 0–1.
- **Scale** — global multiplier applied to coordinates.
- **Point Radius** — visible radius written to the `radius` point attribute.
- **Merge Scans** — combine all scans in the file into one PointCloud object.

To see colors in the viewport, switch to **Material Preview** or **Rendered** shading.

### Exporting E57

`File > Export > E57 Point Cloud (.e57)`

Each selected PointCloud object becomes one scan in the output file.

Options:

- **Colors** — write the `color` attribute as RGB uint8 (0–255).
- **Intensity** — write the `intensity` attribute as a float field.
- **Apply Modifiers** — evaluate the depsgraph first so Geometry Nodes-driven clouds are captured at their final state.
- **Apply Transforms** — bake object Location/Rotation/Scale into the exported coordinates.
- **Selection Only** — when off, every PointCloud in the scene is exported.

**Note:** normals are not written. `pye57`'s writer (which wraps libE57Format) only exposes cartesian / spherical / intensity / color / index fields. Normals are an extension field and would require bypassing `write_scan_raw`.

### Sidebar panel

After importing, press **N** in the 3D Viewport → **Point Cloud** tab. The panel shows point count and present attributes, plus a radius control with a logarithmic slider and `÷10 / ÷2 / Auto / ×2 / ×10` buttons for quick magnitude changes.

## Project layout

```
point_cloud_io/
├── __init__.py              # extension entry point
├── blender_manifest.toml    # Blender extension manifest
├── operators/
│   ├── __init__.py          # operator registration + menu wiring
│   ├── import_e57.py        # File > Import > E57 operator
│   └── export_e57.py        # File > Export > E57 operator
├── formats/
│   ├── __init__.py
│   └── e57.py               # E57 read + write logic
├── ui/
│   ├── __init__.py
│   └── panel.py             # 3D Viewport sidebar (N-panel)
└── wheels/                  # bundled cp313 wheels (pye57, pyquaternion)
```

Adding a new format means dropping `formats/<format>.py` and a matching `operators/import_<format>.py` (or `export_<format>.py`) and wiring it up in `operators/__init__.py`.

## Credits

Uses [pye57](https://github.com/davidcaron/pye57) (libE57Format Python bindings).

## License

GPL-3.0-or-later. Bundled wheels (`pye57`, `pyquaternion`) remain under their original licenses (MIT).
