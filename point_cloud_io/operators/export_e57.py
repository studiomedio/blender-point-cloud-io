import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.e57 import export_e57_file
from ._base import PointCloudExportBase, role_property


class EXPORT_OT_e57(PointCloudExportBase, bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as an E57 file"""

    bl_idname = "export_scene.point_cloud_e57"
    bl_label = "Export E57"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".e57"
    filter_glob: StringProperty(default="*.e57", options={'HIDDEN'}, maxlen=255)

    attribute_roles = ('color', 'intensity')
    # pye57's writer exposes no normals field; the dialog says so in place,
    # so a normal attribute is not also flagged as an unexpected drop.
    consumed_roles = ('normal',)

    color_attribute: role_property('color')
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
    export_colors: BoolProperty(
        name="Colors",
        description="Export RGB if a color attribute is present",
        default=True,
    )
    export_intensity: BoolProperty(
        name="Intensity",
        description="Export intensity if the attribute is present",
        default=True,
    )

    def enabled_roles(self):
        return tuple(
            role for role, on in (
                ('color', self.export_colors),
                ('intensity', self.export_intensity),
            ) if on
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Attributes")
        col.prop(self, "export_colors")
        col.prop(self, "export_intensity")

        self.draw_attribute_roles(layout, context)

        col = layout.column(heading="Geometry")
        col.prop(self, "apply_modifiers")
        col.prop(self, "apply_transforms")

        col = layout.column()
        col.prop(self, "selection_only")

        self.draw_skipped_objects(layout, context)

        layout.label(
            text="Normals are not written (pye57 limitation).",
            icon='INFO',
        )

    def execute(self, context):
        objects = self._resolve_objects(context)
        if not objects:
            self.report({'WARNING'}, "No PointCloud objects to export.")
            return {'CANCELLED'}

        plan = self.export_plan(objects)
        try:
            total = export_e57_file(
                objects,
                self.filepath,
                export_colors=self.export_colors,
                export_intensity=self.export_intensity,
                apply_transforms=self.apply_transforms,
                overrides=self.attribute_overrides(),
            )
        except Exception as err:
            self.report({'ERROR'}, f"E57 export failed: {err}")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Exported {len(objects)} scan(s), {total:,} points.",
        )
        self.report_unwritten(plan, "E57")
        return {'FINISHED'}


def menu_func_export_e57(self, context):
    self.layout.operator(EXPORT_OT_e57.bl_idname, text="E57 Point Cloud (.e57)")
