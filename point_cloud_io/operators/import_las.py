import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..formats._common import suggest_radius
from ..formats.las import import_las_file


class IMPORT_OT_las(bpy.types.Operator, ImportHelper):
    """Import a LAS or LAZ LiDAR file as a PointCloud object"""

    bl_idname = "import_scene.point_cloud_las"
    bl_label = "Import LAS/LAZ"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".las"
    filter_glob: StringProperty(default="*.las;*.laz", options={'HIDDEN'}, maxlen=255)

    import_colors: BoolProperty(
        name="Colors",
        description="Import RGB color data if present (Point Data Record Formats 2, 3, 5, 7, 8)",
        default=True,
    )
    import_intensity: BoolProperty(
        name="Intensity",
        description="Import the intensity field (laser return strength), normalised to 0..1",
        default=True,
    )
    import_classification: BoolProperty(
        name="Classification",
        description="Import the classification code (ground, building, vegetation, etc.) as an INT point attribute",
        default=True,
    )
    import_return_info: BoolProperty(
        name="Return Info",
        description="Import return number and number-of-returns fields (multi-return LiDAR)",
        default=False,
    )
    center_on_origin: BoolProperty(
        name="Center on Origin",
        description=(
            "Subtract the data minimum from positions so the cloud is near "
            "the world origin. Required for georeferenced LAS (UTM, State "
            "Plane, etc.) — without it the cloud lands millions of metres "
            "from origin and float32 precision drops below 1 metre"
        ),
        default=True,
    )
    scale_factor: FloatProperty(
        name="Scale",
        description="Global scale multiplier for imported coordinates",
        default=1.0,
        min=0.0001,
    )
    auto_radius: BoolProperty(
        name="Auto Point Radius",
        description=(
            "Pick a sensible point radius from the cloud's bounding box "
            "and density. Disable to use the value below verbatim"
        ),
        default=True,
    )
    point_radius: FloatProperty(
        name="Point Radius",
        description="Visible radius of each point (ignored when Auto Point Radius is on)",
        default=0.05,
        min=0.0,
        step=0.01,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Attributes")
        col.prop(self, "import_colors")
        col.prop(self, "import_intensity")
        col.prop(self, "import_classification")
        col.prop(self, "import_return_info")

        col = layout.column()
        col.prop(self, "center_on_origin")
        col.prop(self, "scale_factor")
        col.prop(self, "auto_radius")
        row = col.row()
        row.active = not self.auto_radius
        row.prop(self, "point_radius")

    def execute(self, context):
        import numpy as np

        try:
            objects = import_las_file(
                context,
                self.filepath,
                import_colors=self.import_colors,
                import_intensity=self.import_intensity,
                import_classification=self.import_classification,
                import_return_info=self.import_return_info,
                scale_factor=self.scale_factor,
                point_radius=self.point_radius,
                center_on_origin=self.center_on_origin,
            )
        except Exception as err:
            self.report({'ERROR'}, f"LAS import failed: {err}")
            return {'CANCELLED'}

        for obj in objects:
            radius = suggest_radius(obj.data) if self.auto_radius else self.point_radius
            obj.data.uniform_radius = radius

        # Frame the new object so it lands inside whatever the viewport is showing.
        for obj in objects:
            obj.select_set(True)
        if objects:
            context.view_layer.objects.active = objects[0]

        total = 0
        bbox_min = np.array([float('inf')] * 3)
        bbox_max = np.array([-float('inf')] * 3)
        for obj in objects:
            attrs = obj.data.attributes
            if 'position' not in attrs:
                continue
            count = len(attrs['position'].data)
            total += count
            if count == 0:
                continue
            positions = np.empty(count * 3, dtype=np.float32)
            attrs['position'].data.foreach_get('vector', positions)
            positions = positions.reshape(-1, 3)
            bbox_min = np.minimum(bbox_min, positions.min(axis=0))
            bbox_max = np.maximum(bbox_max, positions.max(axis=0))

        if total == 0:
            self.report({'WARNING'}, "LAS import produced 0 points — file may be empty.")
            return {'FINISHED'}

        extent = bbox_max - bbox_min
        attr_names = sorted(
            a.name for a in objects[0].data.attributes if a.name != 'position'
        )

        effective_radius = objects[0].data.uniform_radius if objects else 0.0

        # Console output for full diagnostics.
        print(
            f"[Point Cloud I/O] LAS import:\n"
            f"  file       : {self.filepath}\n"
            f"  points     : {total:,}\n"
            f"  bbox min   : {bbox_min.tolist()}\n"
            f"  bbox max   : {bbox_max.tolist()}\n"
            f"  extent     : {extent.tolist()}\n"
            f"  attributes : {attr_names}\n"
            f"  radius     : {effective_radius:.6g} ({'auto' if self.auto_radius else 'manual'})\n"
            f"  center?    : {self.center_on_origin}"
        )

        self.report(
            {'INFO'},
            f"Imported {total:,} points "
            f"(extent: {extent[0]:.2f} × {extent[1]:.2f} × {extent[2]:.2f}, "
            f"radius: {effective_radius:.4g}). Press numpad-. to frame the view."
        )
        return {'FINISHED'}


def menu_func_import_las(self, context):
    self.layout.operator(IMPORT_OT_las.bl_idname, text="LAS/LAZ Point Cloud (.las, .laz)")
