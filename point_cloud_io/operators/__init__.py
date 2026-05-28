import bpy

from .export_e57 import EXPORT_OT_e57, menu_func_export_e57
from .export_las import EXPORT_OT_las, menu_func_export_las
from .export_pcd import EXPORT_OT_pcd, menu_func_export_pcd
from .export_ply import EXPORT_OT_ply, menu_func_export_ply
from .export_xyz import EXPORT_OT_xyz, menu_func_export_xyz
from .import_e57 import IMPORT_OT_e57, menu_func_import_e57
from .import_las import IMPORT_OT_las, menu_func_import_las
from .import_pcd import IMPORT_OT_pcd, menu_func_import_pcd
from .import_ply import IMPORT_OT_ply, menu_func_import_ply
from .import_xyz import IMPORT_OT_xyz, menu_func_import_xyz

_classes = (
    IMPORT_OT_e57,
    EXPORT_OT_e57,
    IMPORT_OT_ply,
    EXPORT_OT_ply,
    IMPORT_OT_las,
    EXPORT_OT_las,
    IMPORT_OT_pcd,
    EXPORT_OT_pcd,
    IMPORT_OT_xyz,
    EXPORT_OT_xyz,
)
_import_menu_funcs = (
    menu_func_import_e57,
    menu_func_import_ply,
    menu_func_import_las,
    menu_func_import_pcd,
    menu_func_import_xyz,
)
_export_menu_funcs = (
    menu_func_export_e57,
    menu_func_export_ply,
    menu_func_export_las,
    menu_func_export_pcd,
    menu_func_export_xyz,
)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    for fn in _import_menu_funcs:
        bpy.types.TOPBAR_MT_file_import.append(fn)
    for fn in _export_menu_funcs:
        bpy.types.TOPBAR_MT_file_export.append(fn)


def unregister():
    for fn in reversed(_export_menu_funcs):
        bpy.types.TOPBAR_MT_file_export.remove(fn)
    for fn in reversed(_import_menu_funcs):
        bpy.types.TOPBAR_MT_file_import.remove(fn)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
