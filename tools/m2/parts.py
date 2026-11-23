# Reusable hardware: Picatinny rail, socket screws, QD sling cups, knurled bands.
import math
from mathutils import Vector, Matrix
from m2lib import MB, V, X, Y, Z, rrect, circle2, boolean, finish, perp_basis

PIC_H = 0.0094      # MIL-STD-1913 rail height
PIC_PITCH = 0.01    # slot pitch
PIC_SLOT = 0.00523  # slot width


def pic_profile(z0=0.0, sign=1.0, base_w=0.0108):
    # Dovetail profile (x, z): 21.2 mm top, 45 deg flanks, ~15.6 mm waist.
    p = [(-base_w, 0.0), (base_w, 0.0), (base_w, 0.0018), (0.0079, 0.0047), (0.0106, 0.0074),
         (0.0106, 0.0083), (0.0097, PIC_H), (-0.0097, PIC_H), (-0.0106, 0.0083), (-0.0106, 0.0074),
         (-0.0079, 0.0047), (-base_w, 0.0018)]
    return [(x, z0 + sign * z) for x, z in p]


def picatinny(name, y0, y1, z0, sign=1.0, material="anodized", x0=0.0, phase=0.0):
    """Rail from y0 to y1 sitting on z0 (sign=-1 hangs below z0). Slots cut by one comb boolean."""
    m = MB()
    m.prism([(x + x0, z) for x, z in pic_profile(z0, sign)], "Y", y0, y1)
    rail = m.obj(name, material)
    c = MB()
    top = z0 + sign * PIC_H
    # slot centres on a global 10 mm grid so separate rail sections line up
    k0 = math.ceil((y0 + 0.004 - phase) / PIC_PITCH)
    k1 = math.floor((y1 - 0.004 - phase) / PIC_PITCH)
    for k in range(k0, k1 + 1):
        yc = phase + k * PIC_PITCH
        zc = top - sign * 0.0016
        c.box((x0, yc, zc + sign * 0.002), (0.026, PIC_SLOT, 0.0072))
    boolean(rail, c)
    finish(rail, 0.0, 1, 40)
    return rail


def socket_screw(m_name, center, axis, r=0.0028, h=0.0016, material="gunmetal", hex_r=0.0012):
    """Low-profile socket head screw: chamfered head with a hex socket."""
    a = V(axis).normalized()
    m = MB()
    m.lathe([(r * 0.82, -0.0012), (r, -0.0012), (r, h - 0.0005), (r - 0.0005, h), (0.0, h)], n=12, off=center, axis_vec=a)
    o = m.obj(m_name, material)
    c = MB()
    U, W = perp_basis(a)
    hexp = circle2(hex_r, 6)
    c.prism(hexp, a0=h - 0.0011, a1=h + 0.002, off=center, basis=(U, W, a))
    boolean(o, c)
    finish(o, 0.0, 1, 40)
    return o


def qd_cup(name, center, axis, material="gunmetal", flange_r=0.0074, body_r=0.0064, hole_r=0.0047, depth=0.007):
    """Quick-detach sling socket: flange + body with a deep bore and a ring groove."""
    a = V(axis).normalized()
    m = MB()
    prof = [(body_r, -depth), (body_r, -0.0010), (flange_r, -0.0006), (flange_r - 0.0004, 0.0012),
            (hole_r + 0.0005, 0.0012), (hole_r, 0.0006), (hole_r, -depth + 0.0012), (0.0, -depth + 0.0012)]
    m.lathe(prof, n=16, off=center, axis_vec=a, cap1=False)
    o = m.obj(name, material)
    finish(o, 0.0, 1, 40)
    return o


def knurl_band(m, center, axis, r, length, teeth=32, depth=0.0006, grooves=2):
    """Straight-knurl band (star cross-section) with circumferential grooves, added to MB m."""
    a = V(axis).normalized()
    U, W = perp_basis(a)
    c = V(center)
    n = teeth * 2
    zs = [-length / 2, length / 2]
    if grooves:
        zs = []
        cuts = [(-length / 2) + (i + 1) * length / (grooves + 1) for i in range(grooves)]
        edges = [-length / 2]
        for cz in cuts:
            edges += [cz - 0.0007, cz - 0.00035, cz + 0.00035, cz + 0.0007]
        edges.append(length / 2)
        zs = edges
    rings = []
    for zi, zz in enumerate(zs):
        ring = []
        is_groove = False
        if grooves and zi not in (0, len(zs) - 1):
            k = (zi - 1) % 4
            is_groove = k in (1, 2)
        for i in range(n):
            t = 2 * math.pi * i / n
            rr = r - (depth if i % 2 else 0.0)
            if is_groove:
                rr = r - depth * 1.6
            ring.append(c + a * zz + (U * math.cos(t) + W * math.sin(t)) * rr)
        rings.append(ring)
    m.loft(rings, cap0=True, cap1=True)
    return m
