"""Corner detection, radius estimation, and radius scaling for
rounded-corner audits.

Pure Python — no Glyphs API. Nodes are duck-typed: an int ``.type``
(Glyphs node-type constants) and a ``.position`` with ``x``/``y``. So the
same code runs inside Glyphs.app, under glyphsLib, and in avar2-studio.

Model of a rounded corner ("round"):

    prev(LINE) ──── T1(CURVE) ⌒(handles)⌒ T2(LINE) ──── next

Extending the two straight segments gives the *virtual corner* C (their
intersection). Scaling every node of the round (T1, handles, any mid
on-curve nodes, T2) about C by a factor k scales the radius while
preserving node count/order/type — i.e. it is interpolation-safe for
variable fonts as long as the same k-factors are applied per master.
"""

from __future__ import division

import math

LINE = 1
CURVE = 35
OFFCURVE = 65
QCURVE = 67
QCURVE_SMOOTH = 99

# node.type is an INT in the Glyphs 3 runtime (1/35/65/67/99) but a STRING
# under glyphsLib ('line'/'curve'/'offcurve'/'qcurve') — normalize both.
_KIND = {
    LINE: "line",
    CURVE: "curve",
    OFFCURVE: "offcurve",
    QCURVE: "qcurve",
    QCURVE_SMOOTH: "qcurve",
    "line": "line",
    "curve": "curve",
    "offcurve": "offcurve",
    "qcurve": "qcurve",
}
_ONCURVE = {"line", "curve", "qcurve"}
_OFFCURVE = {"offcurve"}


def _kind(node):
    return _KIND.get(node.type, "unknown")

_KAPPA = 0.5522847498307936  # quarter-circle handle-length / radius ratio


# --------------------------------------------------------------------------
# small vector helpers
# --------------------------------------------------------------------------

def _pt(node):
    p = node.position
    return (float(p.x), float(p.y))


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def _mul(a, k):
    return (a[0] * k, a[1] * k)


def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _cubic_mid(p0, h1, h2, p1):
    """de Casteljau midpoint (t=0.5) of a cubic segment."""
    return (
        (p0[0] + 3.0 * h1[0] + 3.0 * h2[0] + p1[0]) / 8.0,
        (p0[1] + 3.0 * h1[1] + 3.0 * h2[1] + p1[1]) / 8.0,
    )


def _line_intersection(p1, p2, p3, p4):
    """Intersection of line p1p2 with p3p4; None when (near-)parallel."""
    d1 = _sub(p2, p1)
    d2 = _sub(p4, p3)
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t = ((p3[0] - p1[0]) * d2[1] - (p3[1] - p1[1]) * d2[0]) / den
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


# --------------------------------------------------------------------------
# circle fitting (Pratt / algebraic least squares)
# --------------------------------------------------------------------------

def _solve3(a, b):
    """3x3 Gaussian elimination with partial pivot; None if singular."""
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(3):
        piv = max(range(col, 3), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            return None
        m[col], m[piv] = m[piv], m[col]
        for r in range(col + 1, 3):
            f = m[r][col] / m[col][col]
            for c in range(col, 4):
                m[r][c] -= f * m[col][c]
    x = [0.0] * 3
    for r in range(2, -1, -1):
        s = m[r][3] - sum(m[r][c] * x[c] for c in range(r + 1, 3))
        if abs(m[r][r]) < 1e-12:
            return None
        x[r] = s / m[r][r]
    return x


def _cubic_eval(p0, h1, h2, p1, t):
    """Point on a cubic Bezier at parameter t (de Casteljau)."""
    mt = 1.0 - t
    return (
        mt**3 * p0[0] + 3 * mt * mt * t * h1[0] + 3 * mt * t * t * h2[0] + t**3 * p1[0],
        mt**3 * p0[1] + 3 * mt * mt * t * h1[1] + 3 * mt * t * t * h2[1] + t**3 * p1[1],
    )


def circle_fit(points):
    """Least-squares circle through ``points`` [(x, y), ...].

    Returns ``(center, radius, rms_residual)`` or None when the points
    are degenerate (collinear / fewer than 3). The residual answers "how
    circular is this round, really" — large means hand-drawn or broken.
    """
    n = len(points)
    if n < 3:
        return None
    sx = sy = sxx = sxy = syy = sxz = syz = sz = 0.0
    for x, y in points:
        z = x * x + y * y
        sx += x
        sy += y
        sxx += x * x
        sxy += x * y
        syy += y * y
        sxz += x * z
        syz += y * z
        sz += z
    sol = _solve3(
        [[sxx, sxy, sx], [sxy, syy, sy], [sx, sy, float(n)]],
        [-sxz, -syz, -sz],
    )
    if sol is None:
        return None
    D, E, F = sol
    center = (-D / 2.0, -E / 2.0)
    r2 = (D * D + E * E) / 4.0 - F
    if r2 <= 0:
        return None
    radius = math.sqrt(r2)
    residual = math.sqrt(
        sum((_dist((x, y), center) - radius) ** 2 for x, y in points) / n
    )
    return center, radius, residual


# --------------------------------------------------------------------------
# path classification (exterior vs counter) via even-odd containment
# --------------------------------------------------------------------------

def _point_in_ring(pt, ring):
    """Even-odd ray cast against a ring of points (straight-segment
    approximation — adequate for contour classification)."""
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xin > x:
                inside = not inside
    return inside


def _path_depths(paths):
    """Depth of each path in the containment hierarchy: 0 = exterior
    contour, odd = counter. Uses each path's first on-curve node as the
    probe point against all other paths."""
    rings = [[_pt(nd) for nd in p.nodes if _kind(nd) in _ONCURVE] for p in paths]
    probes = []
    for i, ring in enumerate(rings):
        if not ring:
            probes.append(None)
            continue
        # nudge the probe slightly off the contour so it never lands on an edge
        px, py = ring[0]
        probes.append((px + 0.31, py + 0.17))
    depths = []
    for i, probe in enumerate(probes):
        if probe is None:
            depths.append(0)
            continue
        depth = 0
        for j, ring in enumerate(rings):
            if j != i and ring and _point_in_ring(probe, ring):
                depth += 1
        depths.append(depth)
    return depths


# --------------------------------------------------------------------------
# corner detection
# --------------------------------------------------------------------------

def find_corners(paths, baseline_y=0.0, baseline_tol=10.0):
    """Detect rounded corners across ``paths``.

    Returns a list of dicts, one per round:

      path_index   index into ``paths``
      node_indices indices of ALL round nodes (T1 .. T2 inclusive)
      t1, t2       tangent-point coordinates
      handles      off-curve coordinates between T1 and T2
      mids         on-curve coordinates between T1 and T2 (multi-curve rounds)
      corner       virtual corner C (line intersection; None when parallel)
      center/radius/residual   from the circle fit (None when degenerate)
      handle_radius            radius implied by handle length / kappa
      class        ``'outer'`` (exterior contour) or ``'counter'``
      convex       True when the round bulges away from the contour centroid
      baseline     True when |C.y - baseline_y| <= baseline_tol
      label_pos    where to draw the radius label
    """
    corners = []
    depths = _path_depths(paths)
    centroids = []
    for path in paths:
        pts = [_pt(nd) for nd in path.nodes if _kind(nd) in _ONCURVE]
        if pts:
            centroids.append(
                (
                    sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts),
                )
            )
        else:
            centroids.append((0.0, 0.0))

    for pi, path in enumerate(paths):
        nodes = list(path.nodes)
        n = len(nodes)
        if n < 5:
            continue
        closed = bool(getattr(path, "closed", True))
        seq = nodes + nodes if closed else nodes
        end = n if closed else n - 1

        i = 0
        while i < end:
            node_i = seq[i]
            # A round's T1 is a LINE node (straight segment INTO it);
            # node.type describes the segment ENDING at the node.
            if _kind(node_i) != 'line':
                i += 1
                continue
            # off-curve run of >= 2 (the handles of the round)
            run = 0
            while (
                i + 1 + run < len(seq)
                and _kind(seq[i + 1 + run]) in _OFFCURVE
            ):
                run += 1
            t2i = i + 1 + run
            if run < 2 or t2i >= len(seq):
                i += 1
                continue
            t2 = seq[t2i]
            # T2 ends the curve segment(s): a CURVE node
            if _kind(t2) != 'curve':
                i += 1
                continue
            # outgoing segment must be straight: next node is LINE
            nxt_i = (t2i + 1) % n if closed else t2i + 1
            if nxt_i < n and _kind(seq[t2i + 1]) != 'line':
                i += 1
                continue
            prev_i = (i - 1) % n if closed else i - 1
            if prev_i < 0:
                prev_i = i  # open path start — no prev; corner fit degrades gracefully
            # collect mid on-curve nodes inside the run (multi-curve rounds)
            mid_on = []
            h_end = t2i
            for k in range(i + 1, h_end):
                if _kind(seq[k]) in _ONCURVE:
                    mid_on.append(k)

            t1i = i % n
            t2i_mod = t2i % n
            prev_pt = _pt(nodes[prev_i])
            t1_pt = _pt(nodes[t1i])
            t2_pt = _pt(nodes[t2i_mod])
            nxt_pt = _pt(nodes[nxt_i]) if nxt_i < n else None

            handle_pts = [_pt(seq[k]) for k in range(i + 1, t2i) if _kind(seq[k]) in _OFFCURVE]
            mid_pts = [_pt(seq[k]) for k in mid_on]

            corner_c = None
            if nxt_pt is not None:
                corner_c = _line_intersection(prev_pt, t1_pt, t2_pt, nxt_pt)

            # Fit the circle through points ON the arc: tangent points,
            # mid on-curve nodes, and curve samples. Off-curve handles are
            # NOT on the circle — fitting through them drags the radius
            # down (a 100-radius round fit as ~79 before this fix).
            segments = []       # (p0_pt, [handle_pts], p1_pt) for fitting
            segments_idx = []   # {"p0": idx, "handles": [idx], "p1": idx} for drawing
            p0 = nodes[t1i]
            p0i = t1i
            pending = []
            pending_i = []
            for k in range(i + 1, t2i + 1):
                nd = seq[k]
                if _kind(nd) in _OFFCURVE:
                    pending.append(_pt(nd))
                    pending_i.append(k % n)
                elif _kind(nd) in _ONCURVE:
                    segments.append((_pt(p0), list(pending), _pt(nd)))
                    segments_idx.append({"p0": p0i, "handles": pending_i, "p1": k % n})
                    p0 = nd
                    p0i = k % n
                    pending = []
                    pending_i = []
            fit_pts = [t1_pt, t2_pt] + mid_pts
            for (a, hs, b) in segments:
                if len(hs) == 2:
                    for t in (0.25, 0.5, 0.75):
                        fit_pts.append(_cubic_eval(a, hs[0], hs[1], b, t))
                else:
                    fit_pts.extend(hs)  # non-cubic shape — sample what we have
            fit = circle_fit(fit_pts)
            center, radius, residual = (fit if fit else (None, None, None))

            handle_radius = None
            if handle_pts:
                handle_radius = _dist(t1_pt, handle_pts[0]) / _KAPPA

            arc_mid = _cubic_mid(
                t1_pt,
                handle_pts[0] if handle_pts else t1_pt,
                handle_pts[-1] if handle_pts else t2_pt,
                t2_pt,
            )

            # convexity: the virtual corner C of a convex round is the
            # OUTERMOST point — the arc sits inside it, closer to the
            # contour centroid. (Inverted once: arc-farther != convex.)
            ctr = centroids[pi]
            ref = corner_c or center or arc_mid
            convex = _dist(ref, ctr) > _dist(arc_mid, ctr)

            node_indices = sorted({t1i, t2i_mod} | {(k % n) for k in range(i + 1, t2i)})

            corners.append(
                {
                    "path_index": pi,
                    "node_indices": node_indices,
                    "t1": t1_pt,
                    "t2": t2_pt,
                    "handles": handle_pts,
                    "mids": mid_pts,
                    "segments": segments_idx,
                    "prev": prev_pt,
                    "next": nxt_pt,
                    "corner": corner_c,
                    "center": center,
                    "radius": radius,
                    "residual": residual,
                    "handle_radius": handle_radius,
                    "class": "counter" if depths[pi] % 2 == 1 else "outer",
                    "convex": convex,
                    "baseline": corner_c is not None and abs(corner_c[1] - baseline_y) <= baseline_tol,
                    "label_pos": arc_mid,
                }
            )
            i = t2i
    return corners


# --------------------------------------------------------------------------
# radius scaling (interpolation-safe: same node slots, new positions)
# --------------------------------------------------------------------------

def transformed_positions(path, corner, factor, pivot=None):
    """Scaled coordinates for the round's nodes.

    ``factor`` k scales every round node about the pivot: the virtual
    corner C when available, else the fitted circle center, else the arc
    midpoint. Returns ``{node_index: (x, y)}`` — applying these positions
    to the SAME node slots changes the radius without touching topology,
    so masters stay interpolation-compatible.
    """
    if pivot is None:
        pivot = corner.get("corner") or corner.get("center") or corner.get("label_pos")
    if pivot is None:
        return {}
    nodes = list(path.nodes)
    out = {}
    for idx in corner["node_indices"]:
        pos = _pt(nodes[idx])
        out[idx] = (
            pivot[0] + factor * (pos[0] - pivot[0]),
            pivot[1] + factor * (pos[1] - pivot[1]),
        )
    return out


def factor_to_absolute(corner, factor):
    """The radius a factor would produce, for the panel readout."""
    base = corner.get("radius") or corner.get("handle_radius")
    return None if base is None else base * factor


# --------------------------------------------------------------------------
# overlap detection (outer round vs counter round)
# --------------------------------------------------------------------------

def _arc_points(center, r, a_start, a_end, a_through, n=16):
    """Sample the arc from a_start to a_end that passes a_through (direction
    chosen so the sweep includes a_through)."""
    def norm(x):
        while x < 0.0:
            x += 2.0 * math.pi
        while x >= 2.0 * math.pi:
            x -= 2.0 * math.pi
        return x

    a_start = norm(a_start)
    a_end = norm(a_end)
    a_through = norm(a_through)

    def ccw(a, b):
        return norm(b - a)

    total = ccw(a_start, a_end)
    if ccw(a_start, a_through) > total:
        total -= 2.0 * math.pi  # go the other way
    return [
        (
            center[0] + r * math.cos(a_start + total * i / n),
            center[1] + r * math.sin(a_start + total * i / n),
        )
        for i in range(n + 1)
    ]


def circle_circle_lens(c1, r1, c2, r2):
    """Polygon approximating the overlap (lens) of two circles, or None.

    Used to flag an outer round colliding with a counter round after
    scaling: the two fitted circles intersect iff
    ``abs(r1 - r2) < d < r1 + r2``. The polygon is the two boundary arcs
    sampled at 16 segments each.
    """
    d = _dist(c1, c2)
    if d <= 1e-9 or d >= r1 + r2 or d <= abs(r1 - r2):
        return None
    a = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    h2 = r1 * r1 - a * a
    if h2 <= 0.0:
        return None
    h = math.sqrt(h2)
    ux, uy = (c2[0] - c1[0]) / d, (c2[1] - c1[1]) / d
    xm = (c1[0] + a * ux, c1[1] + a * uy)
    p1 = (xm[0] + h * uy, xm[1] - h * ux)
    p2 = (xm[0] - h * uy, xm[1] + h * ux)

    def ang(p, c):
        return math.atan2(p[1] - c[1], p[0] - c[0])

    pts = _arc_points(c1, r1, ang(p1, c1), ang(p2, c1), ang(c2, c1))
    pts += _arc_points(c2, r2, ang(p2, c2), ang(p1, c2), ang(c1, c2))
    return pts
