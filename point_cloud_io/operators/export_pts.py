import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.pts import export_pts_file


class EXPORT_OT_pts(bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as a PTS (Leica Cyclone) text file"""

    bl_idname = "export_scene.point_cloud_pts"
    bl_label = "Export PTS"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".pts"
    filter_glob: StringProperty(default="*.pts", options={'HIDDEN'}, maxlen=255)

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

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Columns")
        col.prop(self, "write_intensity")
        col.prop(self, "write_colors")

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

    def execute(self, context):
        objects = self._resolve_objects(context)
        if not objects:
            self.report({'WARNING'}, "No PointCloud objects to export.")
            return {'CANCELLED'}

        try:
            total = export_pts_file(
                objects,
                self.filepath,
                apply_transforms=self.apply_transforms,
                write_colors=self.write_colors,
                write_intensity=self.write_intensity,
            )
        except Exception as err:
            self.report({'ERROR'}, f"PTS export failed: {err}")
            return {'CANCELLED'}

        self.report({'INFO'}, f"Exported {total:,} points to {self.filepath}.")
        return {'FINISHED'}


def menu_func_export_pts(self, context):
    self.layout.operator(EXPORT_OT_pts.bl_idname, text="PTS Point Cloud (.pts)")
