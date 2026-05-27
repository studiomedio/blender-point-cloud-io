import bpy

from .import_e57 import IMPORT_OT_e57, menu_func_import_e57

_classes = (IMPORT_OT_e57,)
_menu_funcs = (menu_func_import_e57,)


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    for fn in _menu_funcs:
        bpy.types.TOPBAR_MT_file_import.append(fn)


def unregister():
    for fn in reversed(_menu_funcs):
        bpy.types.TOPBAR_MT_file_import.remove(fn)
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)
