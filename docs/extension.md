Import and export point cloud files in **six formats** — E57, PLY, LAS/LAZ, PCD, XYZ, and PTS — directly into Blender's native **PointCloud** object. Colors, normals, intensity, classification, and per-point custom fields land as point attributes you can drive with Geometry Nodes or shaders.

## Supported formats

| Format | Import | Export | Notes |
|---|:---:|:---:|---|
| **E57** (`.e57`) | ✅ | ✅ | ASTM standard for LiDAR / terrestrial scanners. Multi-scan files supported. |
| **PLY** (`.ply`) | ✅ | ✅ | Stanford Polygon Format. ASCII + binary (LE/BE). Distinct from Blender's built-in PLY, which produces a **mesh** — ours produces a **PointCloud**. |
| **LAS / LAZ** (`.las`, `.laz`) | ✅ | ✅ | ASPRS LiDAR format. `.laz` decompression via the bundled `lazrs` codec. |
| **PCD** (`.pcd`) | ✅ | ✅ | Point Cloud Library format. ASCII, binary, and `binary_compressed` (LZF) all supported. |
| **XYZ** (`.xyz`, `.txt`, `.csv`) | ✅ | ✅ | Plain-text positions, with auto-detected column layout for color / normal / intensity columns. |
| **PTS** (`.pts`) | ✅ | ✅ | Leica Cyclone text format — XYZ with a count header line. Canonical 7-column `x y z intensity r g b` layout, plus shorter variants auto-detected. |

## Installation

In Blender, open `Edit > Preferences > Get Extensions`, search for "Point Cloud I/O", and click **Install**.

## Features

- **Native PointCloud objects** — uses Blender's optimised point cloud geometry, not a mesh fallback. Handles million-point datasets smoothly.
- **All per-point attributes preserved** — RGB, normals, intensity, ASPRS classification (uint8 → INT attribute), LiDAR return numbers, and any custom scalar fields from the file land as point attributes you can read in Geometry Nodes or shaders.
- **Auto-generated material** — a Principled BSDF wired to the imported color or normal attribute, so points display correctly in Material Preview and Rendered shading right after import.
- **Auto Point Radius** — picks a sensible point radius from the cloud's bounding box and density, on by default for every format. Kilometre-scale LiDAR scans are no longer invisible at the default 5 cm radius.
- **Center on Origin** for georeferenced LiDAR — large LAS/LAZ files in UTM or State Plane coordinates are millions of metres from origin; the importer subtracts the data minimum so the cloud lands in float32-precision range. The offset is stashed on the object as `las_origin_offset` and added back automatically on export, preserving the original CRS.
- **Sidebar panel (N-key)** — shows point count, present attributes, and a **logarithmic point-radius slider** plus `÷10 / ÷2 / Auto / ×2 / ×10` quick buttons. Works on any active PointCloud, not only freshly imported ones.
- **Bundled dependencies** — `pye57`, `pyquaternion`, `laspy`, and `lazrs` ship with the extension. `laspy` and `pyquaternion` are pure Python; `pye57` and `lazrs` ship as both Python 3.13 and Python 3.14 wheels, so the extension installs on official Blender builds and on distribution-packaged builds linked against a newer system Python. PCD, XYZ, PTS and PLY are pure Python + numpy — no extra wheels. No internet or manual pip step at install time.

## Usage

### E57

`File > Import > E57 Point Cloud (.e57)` · `File > Export > E57 Point Cloud (.e57)`

Each scan in a multi-scan E57 becomes its own PointCloud object, or merge them all with **Merge Scans**. Export writes one scan per selected PointCloud. Normals are not written back (limitation of `pye57`'s writer).

### PLY

`File > Import > PLY Point Cloud (.ply)` · `File > Export > PLY Point Cloud (.ply)`

Reads positions, colors (auto-detects 0–255 vs 0–1 ranges), normals, and every other per-vertex scalar property as point attributes. ASCII and binary (little- and big-endian) both supported. **Distinct from Blender's built-in `Stanford PLY` importer**, which produces a mesh — ours produces a PointCloud, dramatically faster for large clouds.

### LAS / LAZ

`File > Import > LAS/LAZ Point Cloud (.las, .laz)` · `File > Export > LAS/LAZ Point Cloud (.las, .laz)`

Reads positions, 16-bit RGB normalised to 0–1, intensity, ASPRS classification, and optional multi-return info. LAZ decompression via the bundled `lazrs` codec. **Center on Origin** (on by default) keeps georeferenced data inside float32 precision; the original offset is round-tripped on export.

Exports as Point Data Record Format 3 (LAS 1.2) — widely compatible. Tick **Compress (LAZ)** to write `.laz`.

### PCD

`File > Import > PCD Point Cloud (.pcd)` · `File > Export > PCD Point Cloud (.pcd)`

Reads positions, packed RGB / RGBA (PCL's float-packed convention), normals (`normal_x/y/z`), intensity, and any other per-point scalar fields. All three PCD data modes supported: **ascii**, **binary**, and **binary_compressed** (LZF — handled by a pure-Python codec, no extra wheels). The exporter's **Data Mode** dropdown picks between the three.

### XYZ

`File > Import > XYZ Point Cloud (.xyz, .txt, .csv)` · `File > Export > XYZ Point Cloud (.xyz)`

Plain text with no header. Column layout is inferred:

| Columns | Interpretation |
|---:|---|
| 3 | `x y z` |
| 4 | `x y z intensity` |
| 6 | `x y z r g b` |
| 7 | `x y z intensity r g b` |
| 9 | `x y z r g b nx ny nz` |
| other | first 3 are positions, the rest become `extra_0`, `extra_1`, … FLOAT attributes |

Comma vs whitespace separator is auto-detected; `#`-prefixed comment lines are skipped.

### PTS

`File > Import > PTS Point Cloud (.pts)` · `File > Export > PTS Point Cloud (.pts)`

Leica Cyclone text format. Structurally XYZ with a single integer count line at the top. The reader auto-detects the column layout from row width: 3 (`x y z`), 4 (`x y z intensity`), 6 (`x y z r g b`), or 7 (`x y z intensity r g b`, Leica canonical). Intensity is normalised to 0–1 on import and scaled back to the 0–2047 Leica integer range on export.

### Sidebar panel

Press **N** in the 3D Viewport → **Point Cloud** tab. Shows point count and attributes; live radius adjustment works on any selected PointCloud, including ones created by Geometry Nodes or other add-ons.

## Limitations

- **E57 export does not write normals.** `pye57`'s writer does not expose the normal extension fields. Imported normals are still preserved as a point attribute inside Blender — they're just not round-tripped back to E57.
- **E57 is unavailable on Intel Mac.** Upstream `pye57` publishes wheels for macOS arm64, Linux x86_64, and Windows x86_64 only, so on macOS x86_64 the E57 importer/exporter cannot load and you would need to build `pye57` from source. Every other format — including LAS/LAZ, which uses `lazrs` — works there.
- **ARM Linux is not supported.** The Blender Extensions platform does not recognise `linux-arm64` as a hostable platform, so no ARM Linux build is published.
- **LAS scale fixed at 1 mm.** Positions are quantised to millimetre precision on export. For country-scale or astronomical-coordinate clouds this could clip; configurable scale is on the roadmap.
- **NaN-positioned points are dropped on import.** This is intentional — PCL writes NaN coordinates for invalid depth-camera pixels and these would otherwise poison the bounding-box / radius computation.

## About the formats

### E57

ASTM standard for vendor-neutral storage of point clouds, images, and metadata from 3D imaging systems (LiDAR, terrestrial scanners, structured-light rigs).

- Format home: [libe57.org](http://www.libe57.org/)
- Sample files: [libe57.org/data.html](http://www.libe57.org/data.html)
- Coordinate conventions: [libe57.org/bestCoordinates.html](http://www.libe57.org/bestCoordinates.html)

### LAS / LAZ

ASPRS standard for airborne and terrestrial LiDAR. LAS is uncompressed; LAZ is the same content compressed via LASzip (typically 10–20 % of the original size, lossless).

- ASPRS specification: [asprs.org · LAS file format](https://www.asprs.org/divisions-committees/lidar-division/laser-las-file-format-exchange-activities)
- US public LiDAR: [USGS Lidar Explorer](https://apps.nationalmap.gov/lidar-explorer/)
- Global research datasets: [OpenTopography](https://portal.opentopography.org/datasets)

### PCD

Point Cloud Library's native format. Used heavily in robotics (ROS / ROS2), perception, and SLAM. ASCII header + per-point data in `ascii`, `binary`, or `binary_compressed` (LZF) form.

### PLY

The Stanford Polygon Format — one of the oldest 3D file formats. Simple ASCII header + per-vertex data (ASCII or binary). Widely supported by 3D scanning and Gaussian-splatting toolchains.

### XYZ

Not a strict standard — most software writes `x y z` per line, optionally with intensity / RGB / normals columns. The importer infers layout from the column count.

### PTS

Leica Cyclone's plain-text format. Identical in spirit to XYZ but with a single integer count line at the top, and a conventional 7-column layout: `x y z intensity r g b`. Common output from terrestrial laser scanners; less common in airborne LiDAR pipelines.

## Source

Source code, issue tracker, and development docs: [github.com/studiomedio/blender-point-cloud-io](https://github.com/studiomedio/blender-point-cloud-io)
