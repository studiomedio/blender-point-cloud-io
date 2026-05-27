# Point Cloud I/O for Blender

A Blender 5.0+ extension for importing and exporting point cloud files. Built around Blender's native **PointCloud** object type.

## Supported formats

| Format | Import | Export |
|--------|:------:|:------:|
| E57 (`.e57`) | ✅ | — |

Other formats (LAS/LAZ, PCD, XYZ, PLY) are planned.

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

## Project layout

```
point_cloud_io/
├── __init__.py              # extension entry point
├── blender_manifest.toml    # Blender extension manifest
├── operators/
│   ├── __init__.py          # operator registration
│   └── import_e57.py        # File > Import > E57 operator
├── formats/
│   ├── __init__.py
│   └── e57.py               # E57 reading + PointCloud creation
└── wheels/                  # bundled cp313 wheels (pye57, pyquaternion)
```

Adding a new format means dropping `formats/<format>.py` and a matching `operators/import_<format>.py` (or `export_<format>.py`) and wiring it up in `operators/__init__.py`.

## Credits

Uses [pye57](https://github.com/davidcaron/pye57) (libE57Format Python bindings).

## License

GPL-3.0-or-later. Bundled wheels (`pye57`, `pyquaternion`) remain under their original licenses (MIT).
