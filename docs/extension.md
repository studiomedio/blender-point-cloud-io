Import and export ASTM E57 point cloud files directly into Blender's native **PointCloud** object — with colors, normals, intensity, and a sidebar panel for live radius control.

## Features

- **Native PointCloud objects** — uses Blender's optimised point cloud geometry, not a mesh fallback.
- **Multi-scan E57 import** — each scan in the file becomes its own object, or merge them all into one with a single toggle.
- **Color, normal, and intensity attributes** — extracted automatically from the file when present and written as point attributes you can read in Geometry Nodes or shaders.
- **Auto-generated material** — a Principled BSDF wired to the imported color or normal attribute, so points display correctly in Material Preview and Rendered shading right after import.
- **Sidebar panel (N-key)** — shows point count, present attributes, and a **logarithmic point-radius slider** plus `÷10 / ÷2 / Auto / ×2 / ×10` quick buttons. Works on any active PointCloud, not only freshly imported ones.
- **E57 export** — write any PointCloud back to E57. Position, color, and intensity are preserved.
- **Bundled dependencies** — `pye57` (libE57Format Python bindings) and `pyquaternion` ship with the extension as Python 3.13 wheels for macOS arm64, Linux x86_64, and Windows x86_64. No internet, no manual pip step.

## Usage

### Import

`File > Import > E57 Point Cloud (.e57)`

Options in the file dialog:

- **Colors / Normals / Intensity** — extract these attributes when present.
- **Scale** — global multiplier on coordinates.
- **Point Radius** — initial visible radius for every point.
- **Merge Scans** — collapse multi-scan files into a single object.

### Export

`File > Export > E57 Point Cloud (.e57)`

Each selected PointCloud object becomes one scan in the output file. Options for **Apply Modifiers** (evaluate Geometry Nodes before writing) and **Apply Transforms** (bake object location/rotation/scale into the coordinates) are available.

### Sidebar panel

Press **N** in the 3D Viewport → **Point Cloud** tab. Live radius adjustment works on any selected PointCloud, including ones created by Geometry Nodes or other add-ons.

## Limitations

- **Export does not write normals.** `pye57`'s writer does not expose the normal extension fields. Imported normals are still preserved as a point attribute inside Blender — they're just not round-tripped back to E57.
- **Intel Mac is not supported** out of the box. `pye57` provides cp313 wheels for macOS arm64, Linux x86_64, and Windows x86_64 only. Intel Mac users would need to build a wheel from source.

## About E57

ASTM E57 is a compact, vendor-neutral standard for storing point clouds, images, and metadata produced by 3D imaging systems such as LiDAR, terrestrial laser scanners, and structured-light rigs.

- Format home: [libe57.org](http://www.libe57.org/)
- Sample files: [libe57.org/data.html](http://www.libe57.org/data.html)
- Coordinate conventions: [libe57.org/bestCoordinates.html](http://www.libe57.org/bestCoordinates.html)

## Source

Source code, issue tracker, and development docs: [github.com/studiomedio/blender-point-cloud-io](https://github.com/studiomedio/blender-point-cloud-io)
