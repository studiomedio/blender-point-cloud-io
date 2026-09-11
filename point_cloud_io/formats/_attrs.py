"""Attribute roles: naming conventions, auto-detection, and export overrides.

Every export writer needs to know which point attribute carries color, which
carries intensity, and so on. Clouds produced by this add-on's importers use
the canonical names ('color', 'normal', 'intensity', ...), but clouds built in
Geometry Nodes or written by other tools rarely do — CloudCompare exports
'scalar_Intensity', a fair number of PLY writers emit 'Col', LAS tooling
round-trips 'scalar_Classification'.

A *role* ('color', 'intensity', ...) resolves to a concrete attribute name in
three steps:

    1. an explicit override chosen in the export dialog, or
    2. the canonical name, if present with a usable data type, or
    3. the first alias that matches, compared with case and punctuation
       stripped, so 'scalar_Intensity' and 'Intensity' both land on the
       intensity role.

`plan_export` then reports which attributes no writer column claimed, so the
operator can warn about them instead of dropping them silently.
"""

from collections import namedtuple


# Enum sentinels for the export dialog. Prefixed so they can never collide
# with a real attribute name, which shares the same enum.
AUTO = '__AUTO__'
NONE = '__NONE__'

# Blender attribute data types usable for each kind of role. FLOAT_VECTOR is
# accepted for color so a 3-component vector attribute can drive RGB.
COLOR_TYPES = frozenset({'FLOAT_COLOR', 'BYTE_COLOR', 'FLOAT_VECTOR'})
VECTOR_TYPES = frozenset({'FLOAT_VECTOR'})
SCALAR_TYPES = frozenset({'FLOAT', 'INT', 'INT8', 'BOOLEAN'})

# Attributes that are geometry rather than payload, or Blender internals.
# Never offered as a role source and never reported as dropped.
RESERVED_NAMES = frozenset({'position', 'radius'})


_Role = namedtuple('_Role', 'key label canonical aliases types description')


def _normalize(name):
    """Fold a name to its comparison form: lowercase, alphanumerics only.

    Collapses the punctuation conventions different tools use, so
    'scalar_Intensity', 'Scalar Intensity' and 'scalarintensity' all match.
    """
    return ''.join(char for char in name.lower() if char.isalnum())


ROLES = {
    role.key: role
    for role in (
        _Role(
            key='color',
            label="Color",
            canonical='color',
            aliases=(
                'color', 'colors', 'col', 'cols', 'rgb', 'rgba',
                'vertexcolor', 'vertexcolors', 'diffusecolor', 'basecolor',
                'scalarcolor',
            ),
            types=COLOR_TYPES,
            description="Attribute written as the RGB color channels",
        ),
        _Role(
            key='normal',
            label="Normal",
            canonical='normal',
            aliases=('normal', 'normals', 'n', 'nrm', 'vertexnormal', 'vertexnormals'),
            types=VECTOR_TYPES,
            description="Attribute written as the per-point normal vector",
        ),
        _Role(
            key='intensity',
            label="Intensity",
            canonical='intensity',
            aliases=(
                'intensity', 'intensities', 'i', 'scalarintensity',
                'reflectance', 'scalarreflectance', 'amplitude',
                'scalaramplitude',
            ),
            types=SCALAR_TYPES,
            description="Scalar attribute written as the intensity channel",
        ),
        _Role(
            key='classification',
            label="Classification",
            canonical='classification',
            aliases=(
                'classification', 'classifications', 'class', 'classes',
                'scalarclassification', 'category', 'label', 'scalarlabel',
            ),
            types=SCALAR_TYPES,
            description="Scalar attribute written as the ASPRS classification code",
        ),
        _Role(
            key='return_number',
            label="Return Number",
            canonical='return_number',
            aliases=(
                'returnnumber', 'returnnum', 'retnum', 'returnindex',
                'scalarreturnnumber',
            ),
            types=SCALAR_TYPES,
            description="Scalar attribute written as the LiDAR return number",
        ),
        _Role(
            key='number_of_returns',
            label="Number of Returns",
            canonical='number_of_returns',
            aliases=(
                'numberofreturns', 'numreturns', 'nreturns', 'returncount',
                'scalarnumberofreturns',
            ),
            types=SCALAR_TYPES,
            description="Scalar attribute written as the LiDAR return count",
        ),
    )
}

# Alias -> role key, built once. Canonical names are included by construction
# because every role lists its canonical name first in `aliases`.
_ALIAS_TO_ROLE = {
    _normalize(alias): role.key
    for role in ROLES.values()
    for alias in role.aliases
}


def is_payload(attr):
    """True for a POINT attribute that carries exportable payload.

    Excludes Blender internals (names starting with '.', e.g. '.selection')
    and the geometry attributes every writer handles on its own.
    """
    return (
        attr.domain == 'POINT'
        and not attr.name.startswith('.')
        and attr.name not in RESERVED_NAMES
    )


def payload_names(attributes):
    """Names of the payload attributes in an attribute collection."""
    return [attr.name for attr in attributes if is_payload(attr)]


def _point_attributes(obj):
    """Yield the POINT-domain attributes a user could meaningfully export."""
    data = getattr(obj, 'data', None)
    if data is None:
        return
    for attr in getattr(data, 'attributes', ()):
        if is_payload(attr):
            yield attr


def is_compatible(attr, role_key):
    """True when `attr` can act as the source for `role_key`."""
    role = ROLES.get(role_key)
    return role is not None and attr.data_type in role.types


def candidate_names(objects, role_key):
    """Attribute names across `objects` that could serve `role_key`.

    Ordered by first appearance so the enum keeps a stable, predictable
    layout rather than reshuffling as the selection changes.
    """
    seen = []
    for obj in objects:
        for attr in _point_attributes(obj):
            if attr.name not in seen and is_compatible(attr, role_key):
                seen.append(attr.name)
    return seen


def suppressed_name(obj, role_key, override):
    """The attribute a NONE override is deliberately leaving out, if any.

    Callers need this to honour NONE properly: a writer with a generic
    by-name passthrough (PLY) would otherwise still emit the attribute under
    its own name, and the export report would count it as an accident rather
    than a choice.
    """
    if override != NONE:
        return None
    return resolve(obj, role_key, AUTO)


def resolve(obj, role_key, override=AUTO):
    """Resolve `role_key` to an attribute name on `obj`, or None.

    `override` is an attribute name, or the AUTO / NONE sentinels. An override
    naming an attribute that is missing or of an unusable type resolves to
    None — the export then reports it rather than falling back silently, since
    a silent fallback is exactly the failure mode this module exists to fix.
    """
    if override == NONE:
        return None

    role = ROLES.get(role_key)
    if role is None:
        return None

    attributes = {attr.name: attr for attr in _point_attributes(obj)}

    if override and override != AUTO:
        attr = attributes.get(override)
        return attr.name if attr is not None and is_compatible(attr, role_key) else None

    canonical = attributes.get(role.canonical)
    if canonical is not None and is_compatible(canonical, role_key):
        return canonical.name

    for attr in attributes.values():
        if not is_compatible(attr, role_key):
            continue
        if _ALIAS_TO_ROLE.get(_normalize(attr.name)) == role_key:
            return attr.name

    return None


ExportPlan = namedtuple('ExportPlan', 'mapping dropped broken')
"""What an export will and will not write.

mapping  -- {role key: attribute name}, for display in the dialog.
dropped  -- sorted attribute names no writer column claims, across all
            objects. These are the silent data losses worth warning about.
broken   -- sorted "Role 'name'" strings for explicitly chosen source
            attributes that are missing or of an unusable type. A role left
            on Auto that simply finds nothing is not an error: most clouds
            legitimately have no classification or return-number channel.
"""


def plan_export(objects, roles, enabled=None, overrides=None, passthrough_types=frozenset()):
    """Work out which attributes an export will write, and which it will drop.

    `roles`             role keys the target format can carry.
    `enabled`           subset actually switched on in the dialog; defaults to
                        all of `roles`. Roles that are off still consume their
                        attribute — turning a column off is a deliberate
                        choice, so its source should not resurface as an
                        unexpected drop.
    `overrides`         {role key: attribute name or sentinel} from the dialog.
    `passthrough_types` data types the writer emits generically by name, as
                        PLY does — those attributes are written, not dropped.

    Both this function and the writers call `resolve`, so the reported plan
    and the bytes on disk agree by construction.
    """
    overrides = overrides or {}
    enabled = set(roles if enabled is None else enabled)

    mapping = {}
    dropped = set()
    broken = set()

    for obj in objects:
        consumed = set()
        for role_key in roles:
            override = overrides.get(role_key, AUTO)
            name = resolve(obj, role_key, override)
            if name is not None:
                consumed.add(name)
                mapping.setdefault(role_key, name)
            elif override == NONE:
                # Chosen omission: keep it out of the file and out of the
                # warning both.
                omitted = suppressed_name(obj, role_key, override)
                if omitted is not None:
                    consumed.add(omitted)
            elif role_key in enabled and override != AUTO:
                broken.add(f"{ROLES[role_key].label} '{override}'")

        for attr in _point_attributes(obj):
            if attr.name in consumed or attr.data_type in passthrough_types:
                continue
            dropped.add(attr.name)

    return ExportPlan(mapping, sorted(dropped), sorted(broken))


def naming_hint(role_keys):
    """One-line reminder of the canonical names for `role_keys`."""
    names = ", ".join(f"'{ROLES[key].canonical}'" for key in role_keys if key in ROLES)
    return f"Recognised names: {names} — or pick a source above."
