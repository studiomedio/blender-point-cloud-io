import bpy
from bpy.props import BoolProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from ..formats._common import suggest_radius
from ..formats.xyz import import_xyz_file


class IMPORT_OT_xyz(bpy.types.Operator, ImportHelper):
    """Import an XYZ text point cloud file as a PointCloud object"""

    bl_idname = "import_scene.point_cloud_xyz"
    bl_label = "Import XYZ"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".xyz"
    filter_glob: StringProperty(
        default="*.xyz;*.txt;*.csv",
        options={'HIDDEN'},
        maxlen=255,
    )

    import_colors: BoolProperty(
        name="Colors",
        description="Interpret columns 4-6 (or 5-7) as RGB when present",
        default=True,
    )
    import_normals: BoolProperty(
        name="Normals",
        description="Interpret columns 7-9 as nx ny nz when 9 columns are present",
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
        col.prop(self, "import_normals")

        col = layout.column()
        col.prop(self, "scale_factor")
        col.prop(self, "auto_radius")
        row = col.row()
        row.active = not self.auto_radius
        row.prop(self, "point_radius")

    def execute(self, context):
        try:
            objects = import_xyz_file(
                context,
                self.filepath,
                import_colors=self.import_colors,
                import_normals=self.import_normals,
                scale_factor=self.scale_factor,
                point_radius=self.point_radius,
            )
        except Exception as err:
            self.report({'ERROR'}, f"XYZ import failed: {err}")
            return {'CANCELLED'}

        for obj in objects:
            radius = suggest_radius(obj.data) if self.auto_radius else self.point_radius
            obj.data.uniform_radius = radius

        total = sum(len(obj.data.attributes['position'].data) for obj in objects)
        self.report({'INFO'}, f"Imported {total:,} points.")
        return {'FINISHED'}


def menu_func_import_xyz(self, context):
    self.layout.operator(IMPORT_OT_xyz.bl_idname, text="XYZ Point Cloud (.xyz, .txt, .csv)")
