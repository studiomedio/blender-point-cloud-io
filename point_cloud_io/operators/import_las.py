import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

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
    scale_factor: FloatProperty(
        name="Scale",
        description="Global scale multiplier for imported coordinates",
        default=1.0,
        min=0.0001,
    )
    point_radius: FloatProperty(
        name="Point Radius",
        description="Visible radius of each point",
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
        col.prop(self, "scale_factor")
        col.prop(self, "point_radius")

    def execute(self, context):
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
            )
        except Exception as err:
            self.report({'ERROR'}, f"LAS import failed: {err}")
            return {'CANCELLED'}

        for obj in objects:
            obj.data.uniform_radius = self.point_radius

        total = sum(len(obj.data.attributes['position'].data) for obj in objects)
        self.report({'INFO'}, f"Imported {total:,} points.")
        return {'FINISHED'}


def menu_func_import_las(self, context):
    self.layout.operator(IMPORT_OT_las.bl_idname, text="LAS/LAZ Point Cloud (.las, .laz)")
