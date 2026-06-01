# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Zenodo DOI** — releases are now archived on Zenodo and the project has a citation DOI ([10.5281/zenodo.20488833](https://doi.org/10.5281/zenodo.20488833)). A DOI badge linking to the concept DOI is shown at the top of the README.

## [0.5.1] – 2026-06-01

### Fixed

- **Tagline shortened** to fit Blender Extensions' 64-character limit. The v0.5.0 tagline ("Import and export E57, PLY, LAS, LAZ, PCD, XYZ and PTS point cloud files", 71 chars) was rejected on upload; the manifest now reads "Import and export E57, PLY, LAS, LAZ, PCD, XYZ, PTS files" (57 chars). No code changes.

## [0.5.0] – 2026-06-01

### Added

- **PTS import** via `File > Import > PTS Point Cloud (.pts)`.
  - Reads the Leica Cyclone text format: integer count header line, then one point per line.
  - Auto-detects the column layout from row width — 3 (`x y z`), 4 (`+ intensity`), 6 (`+ rgb`), or 7 (`+ intensity + rgb`, Leica canonical).
  - Intensity is normalised to 0–1; RGB auto-detects 0–255 vs 0–1.
- **PTS export** via `File > Export > PTS Point Cloud (.pts)`.
  - Writes the count header followed by `x y z [intensity] [r g b]` rows.
  - Intensity is scaled back to the 0–2047 Leica integer range; RGB written as uint8 0–255.
  - Independent **Write Intensity** / **Write Colors** tickboxes.
- Pure-Python + numpy implementation — no new wheel dependencies.

## [0.4.0] – 2026-05-28

### Added

- **PCD import** via `File > Import > PCD Point Cloud (.pcd)`.
  - Reads positions, packed RGB / RGBA (PCL float-packed convention), normals (`normal_x/y/z`), intensity, and other per-point scalar fields as point attributes.
  - Supports `ascii` and `binary` DATA modes. `binary_compressed` (LZF) raises a clear "convert first" error rather than failing silently.
- **PCD export** via `File > Export > PCD Point Cloud (.pcd)`.
  - Writes a single unordered cloud (`HEIGHT = 1`) with `x y z` + optional `normal_x/y/z`, packed `rgb`, and `intensity`.
  - Binary by default; ASCII tickbox for debugging.
- **PCD `binary_compressed` (LZF) read and write support.** A pure-Python LZF codec ([`formats/_lzf.py`](point_cloud_io/formats/_lzf.py)) handles both decompression on read and compression on write — no new wheels. The PCD exporter's previous **ASCII** tickbox is replaced with a **Data Mode** dropdown: `Binary` (default) / `Binary Compressed (LZF)` / `ASCII`.
- **XYZ import** via `File > Import > XYZ Point Cloud (.xyz, .txt, .csv)`.
  - Plain text with no header; column layout inferred from column count (3 / 4 / 6 / 7 / 9 columns recognised; anything else becomes opaque `extra_*` FLOAT attributes).
  - Auto-detects comma vs whitespace separator; skips `#`-prefixed comment lines.
- **XYZ export** via `File > Export > XYZ Point Cloud (.xyz)`.
  - ASCII output. Independent tickboxes for intensity, RGB, and normals.

### Bundled wheels

- No new wheels — both PCD and XYZ readers/writers are pure-Python + numpy.

### Fixed

- **NaN-positioned points are dropped on import** (`_common.build_point_cloud`). PCL convention is that depth-camera pixels with invalid range get NaN coordinates; one of those slipping into the bbox computation poisoned `suggest_radius` (which then returned NaN), so the radius shown in the N-panel was NaN and the cloud rendered invisibly. Triggered most visibly by `office1.pcd` and other organized RGB-D PCDs.
- **`suggest_radius` is now NaN-safe** as a defense-in-depth — strays in scenes created by other paths (Geometry Nodes, scripts) no longer break the panel's Auto button either.

## [0.3.0] – 2026-05-28

### Added

- **LAS / LAZ import** via `File > Import > LAS/LAZ Point Cloud (.las, .laz)`.
  - Reads positions (with file scale + offset applied), 16-bit RGB normalised to 0–1, intensity normalised to 0–1, ASPRS classification (uint8 → INT attribute), and optional return-number / number-of-returns.
  - LAZ decompression via the bundled `lazrs` codec.
  - **Center on Origin** option (on by default) subtracts the data minimum from positions before casting to float32, so georeferenced LiDAR (UTM, State Plane, etc.) lands near the world origin and stays within float32 precision. The subtracted offset is stored as a `las_origin_offset` custom property on the object and added back automatically on export, preserving the original coordinate system through a Blender round-trip.
- **LAS / LAZ export** via `File > Export > LAS/LAZ Point Cloud (.las, .laz)`.
  - Writes Point Data Record Format 3 (LAS 1.2) — positions, RGB, intensity, classification, return info, GPS time slot.
  - Positions quantised to millimeter precision with offset set to the data minimum.
  - `Compress (LAZ)` tickbox writes `.laz`.
- `_common.build_point_cloud` now picks INT / BOOLEAN / FLOAT attribute types based on the numpy dtype of each `extras` array, instead of forcing every scalar to FLOAT.

### Changed

- All three importers (E57, PLY, LAS/LAZ) gained an **Auto Point Radius** toggle, on by default. When enabled, the radius is picked from the cloud's bounding box and point density instead of using the manual field. Without this, large LiDAR clouds (kilometre-scale extents) were invisible because the default 5 cm radius was sub-pixel against the scene. The manual **Point Radius** field is greyed out when Auto is on.
- `suggest_radius` moved from `ui/panel.py` to `formats/_common.py` so importers and the sidebar's **Auto** button share one implementation.

### Diagnostics

- LAS import now logs point count, bounding box, extent, attribute names, and the effective radius to the console; the info-bar success message includes the bbox extent and selected radius.

### Bundled wheels

- `laspy-2.7.0-py3-none-any`
- `lazrs-0.8.1-cp313-cp313` for macOS arm64, manylinux x86_64, Windows x86_64

## [0.2.0] – 2026-05-28

### Added

- **PLY import** via `File > Import > PLY Point Cloud (.ply)`.
  - Reads positions, colors (auto-detects 0–255 vs 0–1 ranges), normals, and any other per-vertex scalar properties as point attributes.
  - ASCII and binary little-endian / big-endian formats supported.
  - Pure-Python + numpy parser — no additional bundled wheels.
- **PLY export** via `File > Export > PLY Point Cloud (.ply)`.
  - Writes positions, normals, colors (as RGB uint8), and `FLOAT` / `INT` / `BOOLEAN` POINT-domain attributes.
  - ASCII and binary little-endian output.
  - Concatenates multiple selected PointCloud objects into a single PLY file.
- Internal `formats/_common.py` module factoring out shared PointCloud build / read helpers used by both E57 and PLY paths.

## [0.1.0] – 2026-05-27

Initial release.

### Added

- **E57 import** via `File > Import > E57 Point Cloud (.e57)`.
  - Imports positions, colors, normals, and intensity as point attributes.
  - Filters out points flagged by `cartesianInvalidState`.
  - Optional global scale, initial point radius, and a "Merge Scans" toggle.
  - Auto-generates a Principled BSDF material wired to color or normal attributes.
- **E57 export** via `File > Export > E57 Point Cloud (.e57)`.
  - Writes one scan per selected PointCloud object.
  - Optional Apply Modifiers (depsgraph evaluation) and Apply Transforms.
  - Colors written as RGB uint8, intensity as float.
  - Lists non-PointCloud objects that will be skipped before writing.
- **3D Viewport sidebar panel** (`N` → Point Cloud tab).
  - Shows point count and present attributes.
  - Numeric point-radius field plus a logarithmic slider for smooth scaling across orders of magnitude.
  - Quick magnitude buttons: `÷10 / ÷2 / Auto / ×2 / ×10`. The `Auto` button picks a radius from the cloud's bounding-box diagonal and density.
- Bundled `pye57` 0.4.19 and `pyquaternion` 0.9.9 cp313 wheels for macOS arm64, Linux x86_64, and Windows x86_64.

### Known limitations

- Export does not write normals (pye57's writer has no normal field).
- Intel Mac (cp313 x86_64) wheels for `pye57` are not published on PyPI; that platform is not supported in this release.
