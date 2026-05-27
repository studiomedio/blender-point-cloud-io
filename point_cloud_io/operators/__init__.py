import bpy

from .export_e57 import EXPORT_OT_e57, menu_func_export_e57
from .export_ply import EXPORT_OT_ply, menu_func_export_ply
from .import_e57 import IMPORT_OT_e57, menu_func_import_e57
from .import_ply import IMPORT_OT_ply, menu_func_import_ply

_classes = (
    IMPORT_OT_e57,
    EXPORT_OT_e57,
    IMPORT_OT_ply,
    EXPORT_OT_ply,
)
_import_menu_funcs = (menu_func_import_e57, menu_func_import_ply)
_export_menu_funcs = (menu_func_export_e57, menu_func_export_ply)


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
