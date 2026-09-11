import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.ply import export_ply_file
from ._base import PointCloudExportBase, role_property


class EXPORT_OT_ply(PointCloudExportBase, bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as a PLY file"""

    bl_idname = "export_scene.point_cloud_ply"
    bl_label = "Export PLY"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".ply"
    filter_glob: StringProperty(default="*.ply", options={'HIDDEN'}, maxlen=255)

    attribute_roles = ('color', 'normal')

    # PLY writes every other point attribute through under its own name, so
    # only types with no column layout at all can go missing.
    passthrough_types = frozenset({
        'FLOAT', 'INT', 'INT8', 'BOOLEAN',
        'FLOAT_VECTOR', 'FLOAT2', 'FLOAT_COLOR', 'BYTE_COLOR',
    })

    color_attribute: role_property('color')
    normal_attribute: role_property('normal')

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
    use_ascii: BoolProperty(
        name="ASCII",
        description="Write the PLY in human-readable ASCII (larger files, useful for debugging)",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Format")
        col.prop(self, "use_ascii")

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
            total = export_ply_file(
                objects,
                self.filepath,
                use_ascii=self.use_ascii,
                apply_transforms=self.apply_transforms,
                overrides=self.attribute_overrides(),
            )
        except Exception as err:
            self.report({'ERROR'}, f"PLY export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {self.filepath}.")
        self.report_unwritten(plan, "PLY")
        return {'FINISHED'}


def menu_func_export_ply(self, context):
    self.layout.operator(EXPORT_OT_ply.bl_idname, text="PLY Point Cloud (.ply)")
