"""Shared plumbing for the six export operators.

Object resolution (selection filtering, modifier evaluation) was duplicated
verbatim across every exporter; it lives here now, alongside the attribute
role dropdowns and the pre-flight report that tells the user which attributes
the chosen format will not carry.
"""

from zlib import crc32

import bpy
from bpy.props import EnumProperty

from ..formats._attrs import AUTO, NONE, ROLES, candidate_names, naming_hint, plan_export


# Blender's dynamic-enum callback must not be the sole owner of the strings it
# returns, or they are garbage collected while the UI still references them.
# Holding the most recent list per role keeps the displayed items alive.
_ENUM_ITEMS_CACHE = {}

# How many names to spell out before collapsing into "...and N more".
_MAX_LISTED = 6

_AUTO_VALUE = 0
_NONE_VALUE = 1
# Enum values are C ints; stay well inside the positive range.
_VALUE_MASK = 0x3FFFFFFF


def _stable_value(name, taken):
    """A per-name enum value that does not depend on the item list order.

    Blender persists an enum as its integer value, and items generated from
    the current selection would otherwise be numbered positionally — a value
    remembered from the last export could then resolve to a *different*
    attribute the next time round, which is precisely the silent mis-export
    this feature exists to prevent. Deriving the value from the name means a
    remembered choice either finds the same attribute or falls back to Auto.
    """
    value = 2 + (crc32(name.encode('utf-8')) & _VALUE_MASK)
    while value in taken:
        value += 1
    taken.add(value)
    return value


def _all_point_clouds():
    """Every PointCloud in the file.

    The item callback can run before the operator instance is usable —
    Blender does this while converting Python arguments to operator
    properties — and an empty list there makes a perfectly valid
    ``intensity_attribute='scalar_Intensity'`` fail with "enum not found".
    Falling back to the whole file keeps scripted exports working.
    """
    return [o for o in bpy.data.objects if o.type == 'POINTCLOUD']


def _role_enum_items(role_key):
    def items(self, context):
        role = ROLES[role_key]
        entries = [
            (AUTO, "Auto",
             f"Detect automatically: '{role.canonical}' first, then common "
             f"aliases from other tools",
             'NONE', _AUTO_VALUE),
            (NONE, "None", f"Do not write {role.label.lower()}",
             'NONE', _NONE_VALUE),
        ]
        objects = []
        try:
            objects = self._enum_source_objects(context)
        except Exception:
            # Item callbacks also run on every redraw, including in states
            # where the depsgraph is not reachable.
            objects = []
        if not objects:
            try:
                objects = _all_point_clouds()
            except Exception:
                objects = []
        taken = {_AUTO_VALUE, _NONE_VALUE}
        for name in candidate_names(objects, role_key):
            if name in (AUTO, NONE):
                continue
            entries.append(
                (name, name, f"Use the '{name}' attribute",
                 'NONE', _stable_value(name, taken))
            )
        _ENUM_ITEMS_CACHE[role_key] = entries
        return entries

    return items


def role_property(role_key):
    """An EnumProperty letting the user pick the source attribute for a role."""
    role = ROLES[role_key]
    return EnumProperty(
        name=role.label,
        description=role.description,
        items=_role_enum_items(role_key),
    )


def _summarize(names):
    if len(names) <= _MAX_LISTED:
        return ", ".join(names)
    listed = ", ".join(names[:_MAX_LISTED])
    return f"{listed} ...and {len(names) - _MAX_LISTED} more"


class PointCloudExportBase:
    """Selection handling, attribute-role overrides, and drop reporting.

    Subclasses declare the roles their format can carry:

        attribute_roles = ('color', 'intensity')

    and one `role_property(...)` annotation per role, named
    ``<role>_attribute``. Formats that write unrecognised attributes through
    by name (PLY) also set `passthrough_types`.
    """

    #: Role keys this format can write, in dialog order.
    attribute_roles = ()

    #: Data types the writer emits generically by name rather than dropping.
    passthrough_types = frozenset()

    #: Roles resolved only to keep their attribute out of the "not written"
    #: warning — for omissions the dialog already explains in place, such as
    #: E57 normals. Never drawn, never enabled.
    consumed_roles = ()

    # -- object resolution --------------------------------------------------

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

    def _enum_source_objects(self, context):
        """Objects whose attributes populate the role dropdowns.

        Uses the evaluated copies so attributes created by Geometry Nodes are
        selectable, falling back to the originals if the depsgraph cannot be
        reached from a draw callback.
        """
        try:
            return self._resolve_objects(context)
        except Exception:
            return [o for o in self._candidates(context) if o.type == 'POINTCLOUD']

    # -- attribute roles ----------------------------------------------------

    def enabled_roles(self):
        """Roles actually switched on. Overridden where a checkbox gates one."""
        return self.attribute_roles

    def attribute_overrides(self):
        return {
            role_key: getattr(self, f"{role_key}_attribute", AUTO)
            for role_key in self.attribute_roles
        }

    def export_plan(self, objects):
        return plan_export(
            objects,
            tuple(self.attribute_roles) + tuple(self.consumed_roles),
            enabled=self.enabled_roles(),
            overrides=self.attribute_overrides(),
            passthrough_types=self.passthrough_types,
        )

    # -- drawing ------------------------------------------------------------

    def draw_attribute_roles(self, layout, context):
        if not self.attribute_roles:
            return

        layout.label(text="Source Attributes")
        col = layout.column()
        for role_key in self.attribute_roles:
            col.prop(self, f"{role_key}_attribute", text=ROLES[role_key].label)

        objects = self._enum_source_objects(context)
        if not objects:
            return
        plan = self.export_plan(objects)
        enabled = set(self.enabled_roles())

        lines = []
        for role_key in self.attribute_roles:
            if role_key not in enabled:
                continue
            name = plan.mapping.get(role_key)
            # Only worth a line when auto-detection found a non-obvious name;
            # a match on the canonical name is what everyone already expects.
            if name is not None and name != ROLES[role_key].canonical:
                lines.append(('INFO', f"{ROLES[role_key].label} → \"{name}\""))

        if plan.broken:
            lines.append(('ERROR', "Missing source: " + ", ".join(plan.broken)))
        if plan.dropped:
            lines.append(('ERROR', "Not written: " + _summarize(plan.dropped)))

        if not lines:
            return

        box = layout.box()
        for icon, text in lines:
            box.label(text=text, icon=icon)
        if plan.broken or plan.dropped:
            box.label(text=naming_hint(self.attribute_roles))

    def draw_skipped_objects(self, layout, context):
        skipped = self._skipped_names(context)
        if not skipped:
            return
        box = layout.box()
        box.label(
            text=f"{len(skipped)} non-PointCloud object(s) will be skipped:",
            icon='ERROR',
        )
        for name in skipped[:5]:
            box.label(text=f"  • {name}")
        if len(skipped) > 5:
            box.label(text=f"  ...and {len(skipped) - 5} more")

    # -- reporting ----------------------------------------------------------

    def report_unwritten(self, plan, format_label):
        """Warn about attributes the finished file does not carry.

        Reported after the success message so it is the one left in the status
        bar — silently dropping data is the failure this is here to surface.
        """
        parts = []
        if plan.broken:
            parts.append("missing source attribute for " + ", ".join(plan.broken))
        if plan.dropped:
            parts.append(f"{format_label} did not write " + _summarize(plan.dropped))
        if not parts:
            return
        self.report(
            {'WARNING'},
            "Some attributes were left out: " + "; ".join(parts) + ". "
            + naming_hint(self.attribute_roles),
        )
