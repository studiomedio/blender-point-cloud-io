import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.pts import export_pts_file
from ._base import PointCloudExportBase, role_property


class EXPORT_OT_pts(PointCloudExportBase, bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as a PTS (Leica Cyclone) text file"""

    bl_idname = "export_scene.point_cloud_pts"
    bl_label = "Export PTS"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".pts"
    filter_glob: StringProperty(default="*.pts", options={'HIDDEN'}, maxlen=255)

    attribute_roles = ('intensity', 'color')

    intensity_attribute: role_property('intensity')
    color_attribute: role_property('color')

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
    write_intensity: BoolProperty(
        name="Write Intensity",
        description="Include an intensity column (scaled to 0..2047, the Leica convention)",
        default=True,
    )
    write_colors: BoolProperty(
        name="Write Colors",
        description="Include RGB columns (r g b as uint8) when a color attribute is present",
        default=True,
    )

    def enabled_roles(self):
        return tuple(
            role for role, on in (
                ('intensity', self.write_intensity),
                ('color', self.write_colors),
            ) if on
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Columns")
        col.prop(self, "write_intensity")
        col.prop(self, "write_colors")

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
            total = export_pts_file(
                objects,
                self.filepath,
                apply_transforms=self.apply_transforms,
                write_colors=self.write_colors,
                write_intensity=self.write_intensity,
                overrides=self.attribute_overrides(),
            )
        except Exception as err:
            self.report({'ERROR'}, f"PTS export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {self.filepath}.")
        self.report_unwritten(plan, "PTS")
        return {'FINISHED'}


def menu_func_export_pts(self, context):
    self.layout.operator(EXPORT_OT_pts.bl_idname, text="PTS Point Cloud (.pts)")
