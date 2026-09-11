import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.pcd import export_pcd_file
from ._base import PointCloudExportBase, role_property


class EXPORT_OT_pcd(PointCloudExportBase, bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as a PCD file"""

    bl_idname = "export_scene.point_cloud_pcd"
    bl_label = "Export PCD"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".pcd"
    filter_glob: StringProperty(default="*.pcd", options={'HIDDEN'}, maxlen=255)

    attribute_roles = ('color', 'normal', 'intensity')

    color_attribute: role_property('color')
    normal_attribute: role_property('normal')
    intensity_attribute: role_property('intensity')

    selection_only: BoolProperty(
        name="Selection Only",
        description="Export only selected PointCloud objects",
        default=True,
    )
    apply_modifiers: BoolProperty(
        name="Apply Modifiers",
        description="Evaluate modifiers (e.g. Geometry Nodes) before export",
        default=True,
    )
    apply_transforms: BoolProperty(
        name="Apply Transforms",
        description="Bake object Location/Rotation/Scale into the exported coordinates",
        default=True,
    )
    data_mode: EnumProperty(
        name="Data Mode",
        description="How the per-point data block is written",
        items=(
            ('binary', "Binary", "Raw little-endian binary (default; widely compatible, fast)"),
            ('binary_compressed', "Binary Compressed (LZF)",
             "LZF-compressed Structure-of-Arrays payload — same as PCL writes by default. "
             "Smaller files, slightly slower write"),
            ('ascii', "ASCII", "Human-readable text (larger files, useful for debugging)"),
        ),
        default='binary',
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Format")
        col.prop(self, "data_mode")

        self.draw_attribute_roles(layout, context)

        col = layout.column(heading="Geometry")
        col.prop(self, "apply_modifiers")
        col.prop(self, "apply_transforms")

        col = layout.column()
        col.prop(self, "selection_only")

        self.draw_skipped_objects(layout, context)

    def execute(self, context):
        objects = self._resolve_objects(context)
        if not objects:
            self.report({'WARNING'}, "No PointCloud objects to export.")
            return {'CANCELLED'}

        plan = self.export_plan(objects)
        try:
            total = export_pcd_file(
                objects,
                self.filepath,
                mode=self.data_mode,
                apply_transforms=self.apply_transforms,
                overrides=self.attribute_overrides(),
            )
        except Exception as err:
            self.report({'ERROR'}, f"PCD export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {self.filepath}.")
        self.report_unwritten(plan, "PCD")
        return {'FINISHED'}


def menu_func_export_pcd(self, context):
    self.layout.operator(EXPORT_OT_pcd.bl_idname, text="PCD Point Cloud (.pcd)")
