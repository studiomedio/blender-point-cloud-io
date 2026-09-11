import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.xyz import export_xyz_file
from ._base import PointCloudExportBase, role_property


class EXPORT_OT_xyz(PointCloudExportBase, bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as an XYZ text file"""

    bl_idname = "export_scene.point_cloud_xyz"
    bl_label = "Export XYZ"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".xyz"
    filter_glob: StringProperty(default="*.xyz", options={'HIDDEN'}, maxlen=255)

    attribute_roles = ('intensity', 'color', 'normal')

    intensity_attribute: role_property('intensity')
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
    write_colors: BoolProperty(
        name="Write Colors",
        description="Include RGB columns (r g b as uint8) when a color attribute is present",
        default=True,
    )
    write_normals: BoolProperty(
        name="Write Normals",
        description="Include nx ny nz columns when a normal attribute is present",
        default=False,
    )
    write_intensity: BoolProperty(
        name="Write Intensity",
        description="Include an intensity column when the attribute is present",
        default=False,
    )

    def enabled_roles(self):
        return tuple(
            role for role, on in (
                ('intensity', self.write_intensity),
                ('color', self.write_colors),
                ('normal', self.write_normals),
            ) if on
        )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Columns")
        col.prop(self, "write_intensity")
        col.prop(self, "write_colors")
        col.prop(self, "write_normals")

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
            total = export_xyz_file(
                objects,
                self.filepath,
                apply_transforms=self.apply_transforms,
                write_colors=self.write_colors,
                write_normals=self.write_normals,
                write_intensity=self.write_intensity,
                overrides=self.attribute_overrides(),
            )
        except Exception as err:
            self.report({'ERROR'}, f"XYZ export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {self.filepath}.")
        self.report_unwritten(plan, "XYZ")
        return {'FINISHED'}


def menu_func_export_xyz(self, context):
    self.layout.operator(EXPORT_OT_xyz.bl_idname, text="XYZ Point Cloud (.xyz)")
