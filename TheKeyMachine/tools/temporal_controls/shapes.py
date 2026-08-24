"""Control curve shape library for Temporal Controls.

Each entry in ``SHAPES`` builds one curve-control shape, centered on the
origin and sized by *size*, returned as an unparented transform named
*name*. The Aim system's aim-target ("pole") picks a shape explicitly (see
``api._add_aim_target``); every System's main control starts out built from
``DEFAULT_SHAPE`` in ``api._build_control_hierarchy``, and the Temp
Controls Panel (``api.set_control_shape``) can swap a control's own shape
for any entry here afterward.

``SHAPE_LIST`` is the ordered, human-labeled version of this dictionary --
what the panel's shape picker actually shows -- while ``SHAPES`` stays the
plain id-to-builder lookup every other caller (``build``) uses.
"""

import math

from maya import cmds


def no_shape(name, size):
    """An empty transform with no shape node at all -- "No Shape" in the
    panel's picker, for a control that should drive/nest without ever
    being visible itself."""
    return cmds.group(empty=True, name=name)


def circle(name, size):
    return cmds.circle(name=name, normal=(0, 1, 0), radius=size, constructionHistory=False)[0]


def square(name, size):
    """A flat, sharp-cornered square -- edges facing the cardinal
    directions (the counterpart to rounded_square's arced corners)."""
    half = size
    points = [(-half, 0, -half), (half, 0, -half), (half, 0, half), (-half, 0, half), (-half, 0, -half)]
    curve = cmds.curve(degree=1, point=points)
    return cmds.rename(curve, name)


def _rounded_square_points(half, radius, segments_per_corner=6):
    """(x, z) points for a square of half-width *half* with real
    arc-rounded corners of *radius* (not a straight chamfer) -- traced
    counter-clockwise starting at the +X/-Z corner's arc."""
    radius = max(0.0, min(radius, half))
    inset = half - radius
    # Each entry: the corner's arc center, and the start angle (degrees,
    # standard math convention) its 90-degree outward sweep begins at.
    corners = (
        ((inset, -inset), -90.0),
        ((inset, inset), 0.0),
        ((-inset, inset), 90.0),
        ((-inset, -inset), 180.0),
    )
    points = []
    for (cx, cz), start_deg in corners:
        for step in range(segments_per_corner + 1):
            angle = math.radians(start_deg + 90.0 * step / segments_per_corner)
            points.append((cx + radius * math.cos(angle), cz + radius * math.sin(angle)))
    points.append(points[0])
    return points


def rounded_square(name, size):
    """A flat square with real arc-rounded corners (not a straight
    chamfer) -- sits on the ground plane like the default circle control
    does, edges facing the cardinal directions. The panel's "Default"
    shape entry."""
    points = [(x, 0, z) for x, z in _rounded_square_points(size, size * 0.4)]
    curve = cmds.curve(degree=1, point=points)
    return cmds.rename(curve, name)


def cross(name, size):
    """3-axis jack -- a small pole/target marker, not meant to read as a
    filled volume. Also what "Locator" in the panel's picker reuses (the
    same silhouette a raw Maya locator draws), see ``SHAPES["locator"]``."""
    axes = (
        [(-size, 0, 0), (size, 0, 0)],
        [(0, -size, 0), (0, size, 0)],
        [(0, 0, -size), (0, 0, size)],
    )
    return _combine_curves(name, [cmds.curve(degree=1, point=points) for points in axes])


def diamond(name, size):
    """A flat, single-plane kite/diamond outline -- points on the X/Z
    axes rather than square/rounded_square's edges-on-axes, so it reads
    as a diamond rotated 45 degrees off them, sitting on the same ground
    plane. Unlike the volumetric ``rhombus``."""
    points = [(0, 0, -size), (size, 0, 0), (0, 0, size), (-size, 0, 0), (0, 0, -size)]
    curve = cmds.curve(degree=1, point=points)
    return cmds.rename(curve, name)


def box(name, size):
    """A 3D wireframe cube outline -- top/bottom face rectangles plus the
    four vertical edges connecting them, edges facing the cardinal
    directions like square/rounded_square."""
    half = size
    corners = ((-half, -half), (half, -half), (half, half), (-half, half), (-half, -half))
    bottom = cmds.curve(degree=1, point=[(x, -half, z) for x, z in corners])
    top = cmds.curve(degree=1, point=[(x, half, z) for x, z in corners])
    edges = [
        cmds.curve(degree=1, point=[(x, -half, z), (x, half, z)])
        for x, z in corners[:-1]
    ]
    return _combine_curves(name, [bottom, top] + edges)


def sphere(name, size):
    """Three orthogonal circles -- two of them at 90 degrees to each other
    (normals (1,0,0) and (0,0,1)), the third (0,1,0) crossing both. The
    classic wireframe-sphere control shape -- reads as a volume from any
    viewing angle, unlike a single flat circle -- which is why it's the
    current Aim aim-target ("pole") shape."""
    circles = [
        cmds.circle(normal=(1, 0, 0), radius=size, constructionHistory=False)[0],
        cmds.circle(normal=(0, 1, 0), radius=size, constructionHistory=False)[0],
        cmds.circle(normal=(0, 0, 1), radius=size, constructionHistory=False)[0],
    ]
    return _combine_curves(name, circles)


def rhombus(name, size):
    """A Sims-style double-pointed diamond / plumbob outline."""
    height = size * 1.35
    mid = size * 0.55
    top = (0, height, 0)
    bottom = (0, -height, 0)
    ring = (
        (mid, 0, 0),
        (0, 0, mid),
        (-mid, 0, 0),
        (0, 0, -mid),
    )

    ring_curve = cmds.curve(degree=1, point=list(ring) + [ring[0]])
    edges = []
    for point in ring:
        edges.append(cmds.curve(degree=1, point=[top, point]))
        edges.append(cmds.curve(degree=1, point=[bottom, point]))
    return _combine_curves(name, [ring_curve] + edges)


def _flat_compass_directions():
    """The 4 ground-plane compass directions the flat arrows point along."""
    return [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _flat_arrow_outline(direction, size):
    """A closed, flat (XZ-plane) arrow silhouette *outline* pointing along
    *direction* -- traced as a real shape with width (shaft + head, both
    edges), not a bare center-line stroke, so it reads as a solid arrow
    ("double sided") instead of a stick figure."""
    dx, dz = direction
    px, pz = -dz, dx  # in-plane perpendicular

    shaft_len = size * 0.55
    shaft_half_w = size * 0.10
    head_half_w = size * 0.24

    def pt(d, p):
        return (dx * d + px * p, 0, dz * d + pz * p)

    points = [
        pt(0, -shaft_half_w),
        pt(shaft_len, -shaft_half_w),
        pt(shaft_len, -head_half_w),
        pt(size, 0),
        pt(shaft_len, head_half_w),
        pt(shaft_len, shaft_half_w),
        pt(0, shaft_half_w),
        pt(0, -shaft_half_w),
    ]
    return cmds.curve(degree=1, point=points)


def arrow_cross(name, size):
    """Four flat arrow outlines as one continuous curve shape."""
    shaft_len = size * 0.55
    shaft_half_w = size * 0.10
    head_half_w = size * 0.24
    join_half_w = shaft_half_w

    def pt(x, z):
        return (x, 0, z)

    points = [
        pt(join_half_w, -join_half_w),
        pt(shaft_len, -shaft_half_w),
        pt(shaft_len, -head_half_w),
        pt(size, 0),
        pt(shaft_len, head_half_w),
        pt(shaft_len, shaft_half_w),
        pt(join_half_w, join_half_w),
        pt(shaft_half_w, shaft_len),
        pt(head_half_w, shaft_len),
        pt(0, size),
        pt(-head_half_w, shaft_len),
        pt(-shaft_half_w, shaft_len),
        pt(-join_half_w, join_half_w),
        pt(-shaft_len, shaft_half_w),
        pt(-shaft_len, head_half_w),
        pt(-size, 0),
        pt(-shaft_len, -head_half_w),
        pt(-shaft_len, -shaft_half_w),
        pt(-join_half_w, -join_half_w),
        pt(-shaft_half_w, -shaft_len),
        pt(-head_half_w, -shaft_len),
        pt(0, -size),
        pt(head_half_w, -shaft_len),
        pt(shaft_half_w, -shaft_len),
        pt(join_half_w, -join_half_w),
    ]
    curve = cmds.curve(degree=1, point=points)
    return cmds.rename(curve, name)


def arrow_circle(name, size):
    """Four arrow outlines fused into one smaller central ring."""
    ring_radius = size * 0.38
    shaft_len = size * 0.55
    shaft_half_w = size * 0.10
    head_half_w = size * 0.24
    arc_steps = 7

    def arrow_points(direction):
        dx, dz = direction
        px, pz = -dz, dx

        def pt(d, p):
            return (dx * d + px * p, 0, dz * d + pz * p)

        return [
            pt(ring_radius, -shaft_half_w),
            pt(shaft_len, -shaft_half_w),
            pt(shaft_len, -head_half_w),
            pt(size, 0),
            pt(shaft_len, head_half_w),
            pt(shaft_len, shaft_half_w),
            pt(ring_radius, shaft_half_w),
        ]

    def arc_points(start, end):
        start_angle = math.atan2(start[2], start[0])
        end_angle = math.atan2(end[2], end[0])
        while end_angle <= start_angle:
            end_angle += math.tau
        return [
            (
                ring_radius * math.cos(start_angle + (end_angle - start_angle) * step / arc_steps),
                0,
                ring_radius * math.sin(start_angle + (end_angle - start_angle) * step / arc_steps),
            )
            for step in range(1, arc_steps + 1)
        ]

    directions = ((1, 0), (0, 1), (-1, 0), (0, -1))
    outlines = [arrow_points(direction) for direction in directions]
    points = []
    for index, outline in enumerate(outlines):
        points.extend(outline if index == 0 else outline[1:])
        next_outline = outlines[(index + 1) % len(outlines)]
        points.extend(arc_points(outline[-1], next_outline[0]))

    curve = cmds.curve(degree=1, point=points)
    return cmds.rename(curve, name)


def cog(name, size, teeth=8):
    """A flat gear/cog silhouette -- a circle whose radius alternates
    between an outer and inner value around *teeth* teeth."""
    outer = size
    inner = size * 0.72
    steps_per_tooth = 4
    steps = teeth * steps_per_tooth
    points = []
    for i in range(steps + 1):
        angle = 2.0 * math.pi * i / steps
        radius = outer if (i // (steps_per_tooth // 2)) % 2 == 0 else inner
        points.append((radius * math.cos(angle), 0, radius * math.sin(angle)))
    curve = cmds.curve(degree=1, point=points)
    return cmds.rename(curve, name)


def _combine_curves(name, curves):
    """Merge every curve in *curves* into one transform's shape nodes,
    named *name* -- the standard "multiple curve shapes, one transform"
    control-curve pattern, so the result still behaves like a single
    control rather than a little hierarchy of separate curves."""
    transform = cmds.rename(curves[0], name)
    for curve in curves[1:]:
        shape = cmds.listRelatives(curve, shapes=True, fullPath=True)[0]
        cmds.parent(shape, transform, shape=True, relative=True)
        cmds.delete(curve)
    return transform


SHAPES = {
    "none": no_shape,
    "circle": circle,
    "square": square,
    "rounded_square": rounded_square,
    "locator": cross,
    "diamond": diamond,
    "box": box,
    "sphere": sphere,
    "rhombus": rhombus,
    "arrow_cross": arrow_cross,
    "arrow_circle": arrow_circle,
    "cog": cog,
}

# Ordered, human-labeled shape list shown by the Temp Controls Panel.
SHAPE_LIST = (
    {"id": "none", "label": "No Shape"},
    {"id": "rounded_square", "label": "Rounded Square"},
    {"id": "square", "label": "Square"},
    {"id": "circle", "label": "Circle"},
    {"id": "locator", "label": "Locator"},
    {"id": "diamond", "label": "Diamond"},
    {"id": "box", "label": "Box"},
    {"id": "sphere", "label": "Sphere"},
    {"id": "rhombus", "label": "Rhombus"},
    {"id": "arrow_cross", "label": "Arrow Cross"},
    {"id": "arrow_circle", "label": "Arrow Circle"},
    {"id": "cog", "label": "Cog"},
)

DEFAULT_SHAPE = "rounded_square"


def build(shape_id, name, size):
    return SHAPES[shape_id](name, size)
