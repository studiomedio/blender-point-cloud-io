import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..formats.e57 import export_e57_file


class EXPORT_OT_e57(bpy.types.Operator, ExportHelper):
    """Export PointCloud objects as an E57 file"""

    bl_idname = "export_scene.point_cloud_e57"
    bl_label = "Export E57"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".e57"
    filter_glob: StringProperty(default="*.e57", options={'HIDDEN'}, maxlen=255)

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
        description="Export RGB if the 'color' attribute is present",
        default=True,
    )
    export_intensity: BoolProperty(
        name="Intensity",
        description="Export the 'intensity' attribute if present",
        default=True,
    )

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(heading="Attributes")
        col.prop(self, "export_colors")
        col.prop(self, "export_intensity")

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

        layout.label(
            text="Normals are not written (pye57 limitation).",
            icon='INFO',
        )

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
            total = export_e57_file(
                objects,
                self.filepath,
                export_colors=self.export_colors,
                export_intensity=self.export_intensity,
                apply_transforms=self.apply_transforms,
            )
        except Exception as err:
            self.report({'ERROR'}, f"E57 export failed: {err}")
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Exported {len(objects)} scan(s), {total:,} points.",
        )
        return {'FINISHED'}


def menu_func_export_e57(self, context):
    self.layout.operator(EXPORT_OT_e57.bl_idname, text="E57 Point Cloud (.e57)")
