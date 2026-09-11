import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.las import export_las_file
from ._base import PointCloudExportBase, role_property


class EXPORT_OT_las(PointCloudExportBase, bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as a LAS or LAZ file"""

    bl_idname = "export_scene.point_cloud_las"
    bl_label = "Export LAS/LAZ"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".las"
    filter_glob: StringProperty(default="*.las;*.laz", options={'HIDDEN'}, maxlen=255)

    attribute_roles = (
        'color', 'intensity', 'classification', 'return_number', 'number_of_returns',
    )

    color_attribute: role_property('color')
    intensity_attribute: role_property('intensity')
    classification_attribute: role_property('classification')
    return_number_attribute: role_property('return_number')
    number_of_returns_attribute: role_property('number_of_returns')

    use_laz: BoolProperty(
        name="Compress (LAZ)",
        description="Write as LAZ (compressed) instead of LAS. Switches the file extension to .laz",
        default=False,
    )
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

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Format")
        col.prop(self, "use_laz")

        self.draw_attribute_roles(layout, context)

        col = layout.column(heading="Geometry")
        col.prop(self, "apply_modifiers")
        col.prop(self, "apply_transforms")

        col = layout.column()
        col.prop(self, "selection_only")

        self.draw_skipped_objects(layout, context)

    def _final_filepath(self):
        base, ext = os.path.splitext(self.filepath)
        if self.use_laz:
            return base + ".laz"
        return base + ".las"

    def execute(self, context):
        objects = self._resolve_objects(context)
        if not objects:
            self.report({'WARNING'}, "No PointCloud objects to export.")
            return {'CANCELLED'}

        target = self._final_filepath()
        plan = self.export_plan(objects)
        try:
            total = export_las_file(
                objects,
                target,
                apply_transforms=self.apply_transforms,
                overrides=self.attribute_overrides(),
            )
        except Exception as err:
            self.report({'ERROR'}, f"LAS export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {target}.")
        self.report_unwritten(plan, "LAS")
        return {'FINISHED'}


def menu_func_export_las(self, context):
    self.layout.operator(EXPORT_OT_las.bl_idname, text="LAS/LAZ Point Cloud (.las, .laz)")
