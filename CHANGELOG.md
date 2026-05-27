# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
