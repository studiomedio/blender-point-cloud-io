import os

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.las import export_las_file


class EXPORT_OT_las(bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as a LAS or LAZ file"""

    bl_idname = "export_scene.point_cloud_las"
    bl_label = "Export LAS/LAZ"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".las"
    filter_glob: StringProperty(default="*.las;*.laz", options={'HIDDEN'}, maxlen=255)

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

        col = layout.column(heading="Geometry")
        col.prop(self, "apply_modifiers")
        col.prop(self, "apply_transforms")

        col = layout.column()
        col.prop(self, "selection_only")

        skipped = self._skipped_names(context)
        if skipped:
            box = layout.box()
            box.label(
                text=f"{len(skipped)} non-PointCloud object(s) will be skipped:",
                icon='ERROR',
            )
            for name in skipped[:5]:
                box.label(text=f"  • {name}")
            if len(skipped) > 5:
                box.label(text=f"  ...and {len(skipped) - 5} more")

    def _candidates(self, context):
        if self.selection_only:
            return list(context.selected_objects)
        return list(context.scene.objects)

    def _skipped_names(self, context):
        return [o.name for o in self._candidates(context) if o.type != 'POINTCLOUD']

    def _resolve_objects(self, context):
        candidates = [o for o in self._candidates(context) if o.type == 'POINTCLOUD']
        if not self.apply_modifiers:
            return candidates
        depsgraph = context.evaluated_depsgraph_get()
        return [o.evaluated_get(depsgraph) for o in candidates]

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
        try:
            total = export_las_file(
                objects,
                target,
                apply_transforms=self.apply_transforms,
            )
        except Exception as err:
            self.report({'ERROR'}, f"LAS export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {target}.")
        return {'FINISHED'}


def menu_func_export_las(self, context):
    self.layout.operator(EXPORT_OT_las.bl_idname, text="LAS/LAZ Point Cloud (.las, .laz)")
