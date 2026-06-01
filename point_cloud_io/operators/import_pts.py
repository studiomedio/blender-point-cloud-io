import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..formats._common import suggest_radius
from ..formats.pts import import_pts_file


class IMPORT_OT_pts(bpy.types.Operator, ImportHelper):
    """Import a PTS (Leica Cyclone) text point cloud file as a PointCloud object"""

    bl_idname = "import_scene.point_cloud_pts"
    bl_label = "Import PTS"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".pts"
    filter_glob: StringProperty(default="*.pts", options={'HIDDEN'}, maxlen=255)

    import_colors: BoolProperty(
        name="Colors",
        description="Interpret columns 4-6 (or 5-7) as RGB when present",
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
        default=0.005,
        min=0.0,
        step=0.01,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Attributes")
        col.prop(self, "import_colors")

        col = layout.column()
        col.prop(self, "scale_factor")
        col.prop(self, "auto_radius")
        row = col.row()
        row.active = not self.auto_radius
        row.prop(self, "point_radius")

    def execute(self, context):
        try:
            objects = import_pts_file(
                context,
                self.filepath,
                import_colors=self.import_colors,
                scale_factor=self.scale_factor,
                point_radius=self.point_radius,
            )
        except Exception as err:
            self.report({'ERROR'}, f"PTS import failed: {err}")
            return {'CANCELLED'}

        for obj in objects:
            radius = suggest_radius(obj.data) if self.auto_radius else self.point_radius
            obj.data.uniform_radius = radius

        total = sum(len(obj.data.attributes['position'].data) for obj in objects)
        self.report({'INFO'}, f"Imported {total:,} points.")
        return {'FINISHED'}


def menu_func_import_pts(self, context):
    self.layout.operator(IMPORT_OT_pts.bl_idname, text="PTS Point Cloud (.pts)")
