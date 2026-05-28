import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..formats._common import suggest_radius
from ..formats.e57 import import_e57_file


class IMPORT_OT_e57(bpy.types.Operator, ImportHelper):
    """Import an E57 point cloud file"""

    bl_idname = "import_scene.point_cloud_e57"
    bl_label = "Import E57"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".e57"
    filter_glob: StringProperty(default="*.e57", options={'HIDDEN'}, maxlen=255)

    import_colors: BoolProperty(
        name="Colors",
        description="Import RGB color data if present",
        default=True,
    )
    import_normals: BoolProperty(
        name="Normals",
        description="Import normal vectors if present",
        default=True,
    )
    import_intensity: BoolProperty(
        name="Intensity",
        description="Import scalar intensity (laser return strength) if present",
        default=False,
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
        default=0.01,
        min=0.0,
        step=0.01,
    )
    merge_scans: BoolProperty(
        name="Merge Scans",
        description="Combine all scans from the file into a single object",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Attributes")
        col.prop(self, "import_colors")
        col.prop(self, "import_normals")
        col.prop(self, "import_intensity")

        col = layout.column()
        col.prop(self, "scale_factor")
        col.prop(self, "auto_radius")
        row = col.row()
        row.active = not self.auto_radius
        row.prop(self, "point_radius")
        col.prop(self, "merge_scans")

    def execute(self, context):
        try:
            objects = import_e57_file(
                context,
                self.filepath,
                import_colors=self.import_colors,
                import_normals=self.import_normals,
                import_intensity=self.import_intensity,
                scale_factor=self.scale_factor,
                point_radius=self.point_radius,
                merge_scans=self.merge_scans,
            )
        except Exception as err:
            self.report({'ERROR'}, f"E57 import failed: {err}")
            return {'CANCELLED'}

        for obj in objects:
            radius = suggest_radius(obj.data) if self.auto_radius else self.point_radius
            obj.data.uniform_radius = radius

        total_points = sum(len(obj.data.attributes['position'].data) for obj in objects)
        self.report(
            {'INFO'},
            f"Imported {len(objects)} object(s), {total_points:,} points total.",
        )
        return {'FINISHED'}


def menu_func_import_e57(self, context):
    self.layout.operator(IMPORT_OT_e57.bl_idname, text="E57 Point Cloud (.e57)")
