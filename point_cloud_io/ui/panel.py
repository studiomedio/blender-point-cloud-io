import math

import bpy
import numpy as np
from bpy.props import FloatProperty
from bpy.types import Operator, Panel

from ..formats._common import suggest_radius as _common_suggest_radius


_DEFAULT_RADIUS = 0.005
_MIN_RADIUS = 1e-6


def _set_radius_attribute(point_cloud, value):
    attrs = point_cloud.attributes
    if 'position' not in attrs:
        return
    count = len(attrs['position'].data)
    if count == 0:
        return
    if 'radius' not in attrs:
        attrs.new(name="radius", type='FLOAT', domain='POINT')
    attrs['radius'].data.foreach_set(
        "value", np.full(count, max(value, 0.0), dtype=np.float32)
    )
    point_cloud.update_tag()


def _on_uniform_radius_update(point_cloud, _context):
    _set_radius_attribute(point_cloud, point_cloud.uniform_radius)


def _get_radius_log(point_cloud):
    return math.log10(max(point_cloud.uniform_radius, _MIN_RADIUS))


def _set_radius_log(point_cloud, value):
    point_cloud.uniform_radius = max(10.0 ** value, _MIN_RADIUS)


def _suggest_radius(point_cloud):
    return _common_suggest_radius(point_cloud, fallback=_DEFAULT_RADIUS)


class POINTCLOUD_OT_scale_radius(Operator):
    """Multiply the active point cloud's radius by a factor"""

    bl_idname = "point_cloud_io.scale_radius"
    bl_label = "Scale Point Radius"
    bl_options = {'REGISTER', 'UNDO'}

    factor: FloatProperty(name="Factor", default=2.0, min=1e-6)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'POINTCLOUD'

    def execute(self, context):
        pc = context.active_object.data
        pc.uniform_radius = max(pc.uniform_radius * self.factor, _MIN_RADIUS)
        return {'FINISHED'}


class POINTCLOUD_OT_auto_radius(Operator):
    """Pick a point radius from the cloud's bounding box and density"""

    bl_idname = "point_cloud_io.auto_radius"
    bl_label = "Auto Fit Point Radius"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'POINTCLOUD'

    def execute(self, context):
        pc = context.active_object.data
        pc.uniform_radius = _suggest_radius(pc)
        return {'FINISHED'}


class POINTCLOUD_PT_io_panel(Panel):
    bl_label = "Point Cloud I/O"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Point Cloud"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.type == 'POINTCLOUD'

    def draw(self, context):
        layout = self.layout
        pc = context.active_object.data
        attrs = pc.attributes

        info = layout.column(align=True)
        count = len(attrs['position'].data) if 'position' in attrs else 0
        info.label(text=f"Points: {count:,}")

        present = [name for name in ('color', 'normal', 'intensity') if name in attrs]
        if present:
            info.label(text="Attributes: " + ", ".join(present))

        layout.separator()

        col = layout.column(align=True)
        col.prop(pc, "uniform_radius", text="Point Radius")
        # Log-scale slider gives even resolution across orders of magnitude;
        # drag here for fine control at very small radii.
        col.prop(pc, "uniform_radius_log", text="", slider=True)

        row = layout.row(align=True)
        row.operator("point_cloud_io.scale_radius", text="÷10").factor = 0.1
        row.operator("point_cloud_io.scale_radius", text="÷2").factor = 0.5
        row.operator("point_cloud_io.auto_radius", text="Auto", icon='SHADERFX')
        row.operator("point_cloud_io.scale_radius", text="×2").factor = 2.0
        row.operator("point_cloud_io.scale_radius", text="×10").factor = 10.0


_classes = (
    POINTCLOUD_OT_scale_radius,
    POINTCLOUD_OT_auto_radius,
    POINTCLOUD_PT_io_panel,
)


def register():
    bpy.types.PointCloud.uniform_radius = FloatProperty(
        name="Point Radius",
        description="Visible radius of every point in this cloud",
        default=_DEFAULT_RADIUS,
        min=0.0,
        soft_min=0.00001,
        soft_max=1.0,
        step=0.01,
        precision=6,
        update=_on_uniform_radius_update,
    )
    bpy.types.PointCloud.uniform_radius_log = FloatProperty(
        name="Radius (log)",
        description="Logarithmic slider for the point radius — drag for "
                    "smooth scaling across orders of magnitude",
        soft_min=-5.0,
        soft_max=0.0,
        step=10,
        precision=2,
        get=_get_radius_log,
        set=_set_radius_log,
    )
    for cls in _classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.PointCloud.uniform_radius_log
    del bpy.types.PointCloud.uniform_radius
