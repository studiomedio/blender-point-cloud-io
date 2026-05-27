import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..formats.ply import import_ply_file


class IMPORT_OT_ply(bpy.types.Operator, ImportHelper):
    """Import a PLY point cloud file as a PointCloud object"""

    bl_idname = "import_scene.point_cloud_ply"
    bl_label = "Import PLY"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".ply"
    filter_glob: StringProperty(default="*.ply", options={'HIDDEN'}, maxlen=255)

    import_colors: BoolProperty(
        name="Colors",
        description="Import RGB / alpha data if present",
        default=True,
    )
    import_normals: BoolProperty(
        name="Normals",
        description="Import normal vectors if present",
        default=True,
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
        col.prop(self, "import_normals")

        col = layout.column()
        col.prop(self, "scale_factor")
        col.prop(self, "point_radius")

    def execute(self, context):
        try:
            objects = import_ply_file(
                context,
                self.filepath,
                import_colors=self.import_colors,
                import_normals=self.import_normals,
                scale_factor=self.scale_factor,
                point_radius=self.point_radius,
            )
        except Exception as err:
            self.report({'ERROR'}, f"PLY import failed: {err}")
            return {'CANCELLED'}

        for obj in objects:
            obj.data.uniform_radius = self.point_radius

        total = sum(len(obj.data.attributes['position'].data) for obj in objects)
        self.report({'INFO'}, f"Imported {total:,} points.")
        return {'FINISHED'}


def menu_func_import_ply(self, context):
    self.layout.operator(IMPORT_OT_ply.bl_idname, text="PLY Point Cloud (.ply)")
