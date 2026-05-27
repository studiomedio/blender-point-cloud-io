import bpy

from .export_e57 import EXPORT_OT_e57, menu_func_export_e57
from .import_e57 import IMPORT_OT_e57, menu_func_import_e57

_classes = (IMPORT_OT_e57, EXPORT_OT_e57)
_import_menu_funcs = (menu_func_import_e57,)
_export_menu_funcs = (menu_func_export_e57,)


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
