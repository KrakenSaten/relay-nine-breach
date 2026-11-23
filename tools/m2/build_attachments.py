# Attachments: each top-level empty's origin is its mounting point; children are relative to it.
import math
from mathutils import Vector, Matrix
import m2lib as L
from m2lib import MB, V, X, Y, Z, rrect, circle2, stadium, boolean, union_parts, finish, join, set_origin, empty, set_parent, xform
from parts import socket_screw, knurl_band, PIC_H
import specs as S


def _clamp(name, y0, y1, depth=0.0095, material="anodized", inverted=False):
    """Picatinny clamp hugging a rail whose top face is at local z=0 (inverted: rail above, grip below)."""
    sg = -1.0 if inverted else 1.0
    prof = [(-0.0135, -0.0075), (-0.0109, -0.0075), (-0.0109, 0.0), (0.0109, 0.0), (0.0109, -0.0075), (0.0135, -0.0075),
            (0.0135, depth), (-0.0135, depth)]
    m = MB()
    m.prism([(x, z * sg) for x, z in prof], "Y", y0, y1)
    m.box((0.0, 0.0, -sg * 0.0014), (0.0170, 0.0048, 0.0030))  # recoil lug sits in the rail slot under the mount point
    o = m.obj(name, material)
    finish(o, 0.0005, 1)
    return o


def _place(objs, root, off):
    for o in objs:
        o.matrix_world = Matrix.Translation(V(off)) @ o.matrix_world
        set_parent(o, root)


# ---------------------------------------------------------------- reflex sight
def optic_reflex(off):
    root = empty("optic_reflex", loc=off, size=0.03)
    axz = 0.031
    out = []
    base = _clamp("reflex_mount", -0.022, 0.022)
    u = MB()
    u.box((0.0, 0.0, 0.0125), (0.0230, 0.034, 0.013))                       # riser
    union_parts(base, u)
    c = MB()
    c.prism(rrect(0.024, 0.006, 0.002, 2, cx=0.0, cy=0.0115), "X", -0.02, 0.02)   # lightening window through the riser
    boolean(base, c)
    finish(base, 0.0006, 1)
    out.append(base)
    # QD lever (left) and thumb nut (right)
    m = MB()
    m.cyl((-0.0148, 0.006, -0.0035), 0.0042, 0.0030, "X", n=16)
    m.prism([(0.009, -0.0055), (-0.024, -0.0040), (-0.026, -0.0010), (-0.024, 0.0015), (0.009, -0.0005)], "X", -0.0172, -0.0150,
            off=(0, 0, 0))
    for i in range(3):
        m.box((-0.0175, -0.016 - i * 0.003, -0.0013), (0.0010, 0.0011, 0.0035))
    lev = m.obj("reflex_qd_lever", "gunmetal")
    finish(lev, 0.0003, 1)
    out.append(lev)
    m = MB()
    knurl_band(m, (0.0158, -0.006, -0.0035), (1, 0, 0), 0.0055, 0.0040, teeth=14, depth=0.0005, grooves=0)
    out.append(m.obj("reflex_nut", "gunmetal"))
    # tube body (hollow) with objective flare
    m = MB()
    prof = [(0.0118, -0.0215), (0.0143, -0.0215), (0.0148, -0.0200), (0.0148, 0.0170), (0.0156, 0.0182), (0.0156, 0.0245),
            (0.0149, 0.0258), (0.0123, 0.0258), (0.0118, 0.0245), (0.0118, -0.0215)]
    m.lathe(prof, "Y", 32, off=(0, 0, axz), cap0=False, cap1=False)
    tube = m.obj("reflex_body", "anodized")
    finish(tube, 0.0003, 1, 35)
    out.append(tube)
    # sunshade hood over the objective
    ro, ri = 0.0186, 0.0161
    arc_o = [(ro * math.cos(math.radians(a)), axz + ro * math.sin(math.radians(a))) for a in range(-12, 193, 12)]
    arc_i = [(ri * math.cos(math.radians(a)), axz + ri * math.sin(math.radians(a))) for a in range(192, -13, -12)]
    hood = [(arc_o[0][0], 0.008)] + arc_o + [(arc_o[-1][0], 0.008), (arc_i[0][0], 0.008)] + arc_i + [(arc_i[-1][0], 0.008)]
    m = MB()
    m.prism(hood, "Y", 0.002, 0.031)
    h = m.obj("reflex_hood", "anodized")
    c = MB()
    for sx in (-1, 1):
        c.prism(stadium(0.016, 0.0045, 3, cx=0.016, cy=0.022), "X", sx * 0.012, sx * 0.03)
    boolean(h, c)
    finish(h, 0.0005, 1)
    out.append(h)
    # turrets: elevation (top) and windage (right), knurled caps
    for axis, pos in (((0, 0, 1), (0.0, -0.009, axz + 0.0140)), ((1, 0, 0), (0.0140, -0.009, axz))):
        a = V(axis)
        m = MB()
        m.lathe([(0.0070, 0.0), (0.0070, 0.0035), (0.0058, 0.0042), (0.0058, 0.0060)], n=20, off=pos, axis_vec=a, cap0=True, cap1=False)
        knurl_band(m, V(pos) + a * 0.0080, a, 0.0064, 0.0040, teeth=18, depth=0.0005, grooves=0)
        t = m.obj("reflex_turret", "gunmetal")
        c = MB()
        cc = V(pos) + a * 0.0102
        c.box(cc, (0.0072, 0.0012, 0.0012) if axis[2] else (0.0012, 0.0072, 0.0012))
        boolean(t, c)
        finish(t, 0.0002, 1, 40)
        out.append(t)
    # battery cap (left) and brightness buttons (rubber) on a control housing
    m = MB()
    m.lathe([(0.0072, 0.0), (0.0072, 0.0035)], n=20, off=(-0.0138, -0.009, axz), axis_vec=(-1, 0, 0), cap0=True, cap1=False)
    knurl_band(m, (-0.0193, -0.009, axz), (-1, 0, 0), 0.0074, 0.0042, teeth=18, depth=0.0005, grooves=0)
    out.append(m.obj("reflex_battery", "gunmetal"))
    m = MB()
    m.prism(rrect(0.020, 0.010, 0.003, 2, cx=-0.006, cy=0.0175), "X", -0.0150, -0.0105)
    ctrl = m.obj("reflex_ctrl", "anodized")
    finish(ctrl, 0.0005, 1)
    out.append(ctrl)
    m = MB()
    for yy in (-0.0115, -0.0005):
        m.lathe([(0.0030, 0.0), (0.0030, 0.0011), (0.0022, 0.0018), (0.0, 0.0018)], n=12, off=(-0.0150, yy, 0.0175), axis_vec=(-1, 0, 0))
    out.append(m.obj("reflex_buttons", "rubber"))
    # lens (front), origin at its centre
    m = MB()
    m.lathe([(0.0, -0.0007), (0.0118, -0.0007), (0.0118, 0.0007), (0.0, 0.0007)], "Y", 32, off=(0, 0.0130, axz))
    lens = m.obj("lens", "glass_lens")
    set_origin(lens, (0, 0.0130, axz))
    out.append(lens)
    _place(out, root, off)
    empty("eye", loc=V(off) + V((0, 0.0130 - 0.30, axz)), parent=root, size=0.01)
    return root


# ---------------------------------------------------------------- 2x prism
def optic_prism(off):
    root = empty("optic_prism", loc=off, size=0.03)
    axz = 0.040
    out = []
    base = _clamp("prism_mount", -0.026, 0.026, depth=0.0105)
    u = MB()
    u.box((0.0, 0.0, 0.0150), (0.0240, 0.040, 0.012))
    union_parts(base, u)
    finish(base, 0.0006, 1)
    out.append(base)
    for yy in (-0.014, 0.014):   # cross bolts with thumb nuts (right)
        out.append(socket_screw("prism_bolt", (-0.0135, yy, -0.0035), (-1, 0, 0), r=0.0030))
        m = MB()
        knurl_band(m, (0.0160, yy, -0.0035), (1, 0, 0), 0.0050, 0.0045, teeth=12, depth=0.0005, grooves=0)
        out.append(m.obj("prism_nut", "gunmetal"))
    # housing
    m = MB()
    m.prism([(-0.022, 0.020), (0.020, 0.020), (0.0245, 0.028), (0.0245, 0.054), (0.018, 0.0595), (-0.016, 0.0595), (-0.022, 0.053)],
            "X", -0.0172, 0.0172)
    hs = m.obj("prism_housing", "anodized")
    c = MB()
    for sx in (-1, 1):
        c.prism(rrect(0.026, 0.016, 0.004, 2, cx=-0.002, cy=0.036), "X", sx * 0.0162, sx * 0.03)
    boolean(hs, c)
    finish(hs, 0.0022, 2, 30)
    out.append(hs)
    # objective bell + glass
    m = MB()
    m.lathe([(0.0150, 0.018), (0.0160, 0.022), (0.0188, 0.034), (0.0197, 0.039), (0.0197, 0.0475), (0.0190, 0.0490), (0.0172, 0.0490),
             (0.0166, 0.0478), (0.0166, 0.0442), (0.0, 0.0442)], "Y", 32, off=(0, 0, axz))
    ob = m.obj("prism_objective", "anodized")
    finish(ob, 0.0003, 1, 35)
    out.append(ob)
    m = MB()
    m.lathe([(0.0, -0.0006), (0.0166, -0.0006), (0.0166, 0.0006), (0.0, 0.0006)], "Y", 32, off=(0, 0.0450, axz))
    og = m.obj("obj_glass", "glass_lens")
    set_origin(og, (0, 0.0450, axz))
    out.append(og)
    # ocular bell, diopter ring, glass, rubber guard
    m = MB()
    m.lathe([(0.0, -0.0468), (0.0145, -0.0468), (0.0150, -0.0490), (0.0186, -0.0490), (0.0186, -0.0400), (0.0170, -0.0330),
             (0.0152, -0.0210), (0.0150, -0.0180)], "Y", 32, off=(0, 0, axz), cap1=True)
    oc = m.obj("prism_ocular", "anodized")
    finish(oc, 0.0003, 1, 35)
    out.append(oc)
    m = MB()
    knurl_band(m, (0, -0.0445, axz), (0, 1, 0), 0.0192, 0.0070, teeth=30, depth=0.0005, grooves=0)
    out.append(m.obj("prism_diopter", "gunmetal"))
    m = MB()
    m.lathe([(0.0, -0.0004), (0.0145, -0.0004), (0.0145, 0.0004), (0.0, 0.0004)], "Y", 24, off=(0, -0.0472, axz))
    out.append(m.obj("ocu_glass", "glass_lens"))
    m = MB()
    m.lathe([(0.0178, -0.0480), (0.0192, -0.0480), (0.0205, -0.0540), (0.0200, -0.0575), (0.0186, -0.0580), (0.0172, -0.0560),
             (0.0168, -0.0500), (0.0178, -0.0480)], "Y", 32, off=(0, 0, axz), cap0=False, cap1=False)
    out.append(m.obj("ocular_guard", "rubber"))
    # turrets with caps
    for axis, pos in (((0, 0, 1), (0.0, 0.0, 0.0590)), ((1, 0, 0), (0.0168, 0.0, axz))):
        a = V(axis)
        m = MB()
        m.lathe([(0.0088, 0.0), (0.0088, 0.0030), (0.0080, 0.0036)], n=20, off=pos, axis_vec=a, cap0=True, cap1=True)
        knurl_band(m, V(pos) + a * 0.0068, a, 0.0084, 0.0064, teeth=20, depth=0.0006, grooves=1)
        out.append(m.obj("prism_turret", "gunmetal"))
    m = MB()   # illumination dial (left)
    m.lathe([(0.0080, 0.0), (0.0080, 0.0025)], n=20, off=(-0.0168, -0.004, axz), axis_vec=(-1, 0, 0), cap0=True, cap1=False)
    knurl_band(m, (-0.0218, -0.004, axz), (-1, 0, 0), 0.0086, 0.0050, teeth=20, depth=0.0006, grooves=0)
    out.append(m.obj("prism_dial", "gunmetal"))
    _place(out, root, off)
    empty("eye", loc=V(off) + V((0, -0.0580 - 0.16, axz)), parent=root, size=0.01)
    return root


# ---------------------------------------------------------------- suppressor
def suppressor(off):
    root = empty("suppressor", loc=off, size=0.03)
    out = []
    m = MB()   # QD mount collar (covers the muzzle threads)
    m.lathe([(0.0090, -0.0210), (0.0150, -0.0210), (0.0168, -0.0195), (0.0168, -0.0045), (0.0182, -0.0035), (0.0182, 0.0010),
             (0.0090, 0.0010)], "Y", 32)
    col = m.obj("supp_mount", "gunmetal")
    c = MB()
    for k in range(8):   # ratchet teeth / wrench notches
        a = 2 * math.pi * k / 8
        c.box((math.cos(a) * 0.0172, -0.0165, math.sin(a) * 0.0172), (0.0040, 0.0060, 0.0040), rot=Matrix.Rotation(-a, 3, "Y"))
    boolean(col, c)
    finish(col, 0.0004, 1)
    out.append(col)
    m = MB()
    knurl_band(m, (0, -0.0110, 0), (0, 1, 0), 0.0171, 0.0080, teeth=32, depth=0.0005, grooves=1)
    out.append(m.obj("supp_knurl_rear", "gunmetal"))
    m = MB()   # can body with two engraved rings
    prof = [(0.0150, 0.0005), (0.0196, 0.0005), (0.0205, 0.0020), (0.0205, 0.0300), (0.0199, 0.0306), (0.0205, 0.0312),
            (0.0205, 0.0950), (0.0199, 0.0956), (0.0205, 0.0962), (0.0205, 0.1220), (0.0150, 0.1220)]
    m.lathe(prof, "Y", 36)
    can = m.obj("supp_can", "anodized")
    finish(can, 0.0004, 1, 35)
    out.append(can)
    m = MB()
    knurl_band(m, (0, 0.1290, 0), (0, 1, 0), 0.0207, 0.0140, teeth=36, depth=0.0006, grooves=2)
    out.append(m.obj("supp_knurl_front", "gunmetal"))
    m = MB()   # end cap with recessed face and bore
    m.lathe([(0.0150, 0.1360), (0.0205, 0.1360), (0.0205, 0.1460), (0.0196, 0.1500), (0.0120, 0.1500), (0.0112, 0.1488),
             (0.0060, 0.1488), (0.0045, 0.1478), (0.0045, 0.1300), (0.0, 0.1300)], "Y", 36)
    cap = m.obj("supp_cap", "gunmetal")
    c = MB()
    for k in range(3):
        a = math.radians(90 + 120 * k)
        c.cyl((math.cos(a) * 0.0158, 0.1500, math.sin(a) * 0.0158), 0.0016, 0.006, "Y", n=10)
    boolean(cap, c)
    finish(cap, 0.0003, 1, 35)
    out.append(cap)
    _place(out, root, off)
    return root


# ---------------------------------------------------------------- foregrips
def grip_vertical(off):
    import poses
    root = empty("grip_vertical", loc=off, size=0.03)
    out = [_clamp("vg_clamp", -0.020, 0.020, depth=0.0110, inverted=True)]
    out.append(socket_screw("vg_bolt", (-0.0135, 0.0, 0.0035), (-1, 0, 0), r=0.0030))
    m = MB()
    knurl_band(m, (0.0160, 0.0, 0.0035), (1, 0, 0), 0.0052, 0.0045, teeth=12, depth=0.0005, grooves=0)
    out.append(m.obj("vg_nut", "gunmetal"))
    top = S.VG_TOP
    r = S.VG_R
    prof = [(0.0, top + 0.001), (0.0128, top + 0.001), (0.0152, top - 0.001), (0.0152, top - 0.0045), (0.0139, top - 0.0060)]
    z = top - 0.0080
    for i in range(6):   # grip rings
        prof += [(r, z), (r, z - 0.0085), (r - 0.0007, z - 0.0093), (r - 0.0007, z - 0.0107), (r, z - 0.0115)]
        z -= 0.0123
    zb = top - S.VG_LEN
    prof += [(r, zb + 0.0080), (0.0150, zb + 0.0045), (0.0150, zb + 0.0012), (0.0138, zb), (0.0, zb)]
    m = MB()
    m.lathe(prof, "Z", 28)
    h = m.obj("vg_handle", "polymer")
    finish(h, 0.0004, 1, 35)
    out.append(h)
    m = MB()
    m.lathe([(0.0, zb + 0.0002), (0.0110, zb + 0.0002), (0.0110, zb - 0.0012), (0.0095, zb - 0.0020), (0.0, zb - 0.0020)], "Z", 24)
    out.append(m.obj("vg_cap", "rubber"))
    _place(out, root, off)
    M = poses.vgrip_hand_matrix()
    empty("hand_L", M=Matrix.Translation(V(off)) @ M, parent=root, size=0.02)
    return root


def grip_angled(off):
    import poses
    root = empty("grip_angled", loc=off, size=0.03)
    out = [_clamp("ag_clamp", -0.030, 0.030, depth=0.0110, inverted=True)]
    for yy in (-0.016, 0.016):
        out.append(socket_screw("ag_bolt", (-0.0135, yy, 0.0035), (-1, 0, 0), r=0.0030))
    m = MB()
    prof = [(0.030, -0.0100), (0.026, -0.0155), (-0.016, -0.0350), (-0.028, -0.0425), (-0.037, -0.0432), (-0.042, -0.0395),
            (-0.039, -0.0260), (-0.033, -0.0100)]
    m.prism(prof, "X", -0.0118, 0.0118)
    w = m.obj("ag_body", "polymer")
    c = MB()
    for sx in (-1, 1):
        for i in range(3):
            c.prism(stadium(0.026, 0.0030, 2, cx=0.004 - i * 0.0085, cy=-0.0175 - i * 0.0045), "X", sx * 0.0108, sx * 0.02,
                    basis=None)
    boolean(w, c)
    finish(w, 0.0022, 2, 30)
    out.append(w)
    _place(out, root, off)
    M = poses.agrip_hand_matrix()
    empty("hand_L", M=Matrix.Translation(V(off)) @ M, parent=root, size=0.02)
    return root


# ---------------------------------------------------------------- magazines
MAGS = {
    # name: (length from feed lips to floorplate, body material, extra)
    "mag_std": (0.170, "polymer"),
    "mag_ext": (0.240, "polymer"),
    "mag_quick": (0.150, "polymer_tan"),
}
MAG_STRAIGHT = 0.072
MAG_BEND = math.radians(10.0)


def mag_path(Lm, s):
    """Centre, down-tangent and forward normal of the magazine spine at arc length s (mag space)."""
    if s <= MAG_STRAIGHT:
        return V((0, 0, -s)), V((0, 0, -1)), V((0, 1, 0))
    k = MAG_BEND / max(1e-6, Lm - MAG_STRAIGHT)
    th = (s - MAG_STRAIGHT) * k
    R = 1.0 / k
    c = V((0, R * (1 - math.cos(th)), -MAG_STRAIGHT - R * math.sin(th)))
    t = V((0, math.sin(th), -math.cos(th)))
    n = V((0, math.cos(th), math.sin(th)))
    return c, t, n


def mag_section(hw, hd, ribs=True, bump=0.0):
    """Cross-section (x, forward) with vertical spine ribs; hd = half depth (front-back)."""
    base = rrect(2 * hw, 2 * hd, 0.0042, 3)
    pts = []
    for x, y in base:
        pts.append((x * (1 + bump / hw), y + (bump if y > 0 else -bump)))
    if not ribs:
        return pts
    # add two raised spine ribs per side by bumping the points nearest |y| = 0.012
    out = []
    for x, y in pts:
        out.append((x, y))
    return out


def _mag(name, off):
    import poses
    Lm, mt = MAGS[name]
    root = empty(name, loc=off, size=0.03)
    hw = S.MAG_W / 2
    hd = S.MAG_D / 2
    out = []
    # stations along the spine (s, scale_x, scale_y extra, bump)
    stations = [(0.0005, 0.86, -0.004, 0.0), (0.006, 0.86, -0.004, 0.0), (0.008, 1.0, 0.0, 0.0)]
    s = 0.020
    while s < Lm - 0.050:
        stations.append((s, 1.0, 0.0, 0.0))
        s += 0.022
    # texture bands near the base
    for sb in (Lm - 0.046, Lm - 0.034, Lm - 0.022):
        stations += [(sb - 0.0040, 1.0, 0.0, 0.0), (sb - 0.0032, 1.0, 0.0, 0.0007), (sb + 0.0032, 1.0, 0.0, 0.0007), (sb + 0.0040, 1.0, 0.0, 0.0)]
    stations.append((Lm - 0.010, 1.0, 0.0, 0.0))
    stations.sort(key=lambda t: t[0])
    rings = []
    for s, sx, dy, bump in stations:
        c, t, n = mag_path(Lm, s)
        grow = 0.0018 * (s / Lm)     # slightly deeper toward the base, like a real 5.56 mag
        sec = mag_section(hw * sx, hd + dy + grow, bump=bump)
        rings.append([c + X * x + n * (y + grow * 0.6) for x, y in sec])
    m = MB()
    m.loft(rings, cap0=True, cap1=True)
    body = m.obj(name + "_body", mt)
    c = MB()
    # witness holes (rear, both sides) and side spine grooves
    for k in range(3):
        sc = 0.040 + k * 0.030
        if sc > Lm - 0.06:
            break
        cc, t, n = mag_path(Lm, sc)
        for sxs in (-1, 1):
            c.cyl(cc + n * (-hd + 0.008) + X * sxs * (hw + 0.0005), 0.0022, 0.0050, "X", n=12)
    for sxs in (-1, 1):
        for yo in (-0.0105, 0.0105):
            pts = []
            c0, t0, n0 = mag_path(Lm, 0.020)
            c1, t1, n1 = mag_path(Lm, min(Lm - 0.055, 0.020 + 0.11))
            a = c0 + n0 * yo + X * sxs * hw
            b = c1 + n1 * yo + X * sxs * hw
            d = (b - a)
            nn = X * sxs
            U = d.normalized()
            W = nn.cross(U).normalized()
            c.prism(stadium(d.length, 0.0030, 2), a0=-0.0007, a1=0.003, off=(a + b) / 2, basis=(U, W, nn))
    boolean(body, c)
    finish(body, 0.0006, 1, 30)
    out.append(body)
    # floorplate with front lip
    cb, tb, nb = mag_path(Lm, Lm - 0.008)
    m = MB()
    sec = rrect(2 * hw + 0.0038, 2 * hd + 0.0060, 0.0040, 3, cy=0.0015)
    rings = []
    for ds in (-0.0040, 0.0060, 0.0080):
        cc = cb - tb * (-ds)
        rings.append([cc + X * x + nb * y for x, y in sec])
    m.loft(rings)
    fp = m.obj(name + "_floor", "polymer" if name != "mag_quick" else "polymer_tan")
    finish(fp, 0.0012, 2, 30)
    out.append(fp)
    # top round in the feed lips
    m = MB()
    m.lathe([(0.0, -0.0262), (0.0047, -0.0262), (0.0048, 0.0140), (0.0040, 0.0160), (0.0039, 0.0170)], "Y", 14, off=(0.0, -0.0010, -0.0035),
            cap1=True)
    out.append(m.obj(name + "_case", "copper"))
    m = MB()
    m.lathe([(0.0028, 0.0165), (0.0028, 0.0200), (0.0022, 0.0250), (0.0010, 0.0285), (0.0, 0.0295)], "Y", 14, off=(0.0, -0.0010, -0.0035),
            cap0=True)
    out.append(m.obj(name + "_bullet", "copper"))
    if name == "mag_quick":
        # rubber pull loop under the floorplate
        cl, tl, nl = mag_path(Lm, Lm + 0.002)
        pts = []
        for i in range(11):
            a = math.pi * i / 10
            pts.append(cl + nl * (0.019 * math.cos(a)) - tl * (-0.026 * math.sin(a)))
        rings = []
        for i, p in enumerate(pts):
            if i == 0:
                tg = pts[1] - pts[0]
            elif i == len(pts) - 1:
                tg = pts[-1] - pts[-2]
            else:
                tg = pts[i + 1] - pts[i - 1]
            tg.normalize()
            side = X
            up = tg.cross(side).normalized()
            rings.append([p + side * x + up * y for x, y in rrect(0.012, 0.0045, 0.0018, 2)])
        m = MB()
        m.loft(rings)
        loop = m.obj("mag_quick_loop", "rubber")
        L.subsurf(loop, 1)
        out.append(loop)
    _place(out, root, off)
    empty("hand_L", M=Matrix.Translation(V(off)) @ mag_hand_local(name), parent=root, size=0.02)
    return root


MAG_HAND_S = 0.090   # arc length below the feed lips where the reload hand grabs (just under the magwell)


def mag_hand_local(name):
    import poses
    Lm, mt = MAGS[name]
    s = min(MAG_HAND_S, Lm - 0.035)
    c, t, n = mag_path(Lm, s)
    grow = 0.0018 * (s / Lm)
    front_y = c.y + n.y * (S.MAG_D / 2 + grow * 1.6)
    return poses.mag_hand_matrix(front_y, c.z, S.MAG_W / 2)


def build():
    optic_reflex((0.0, 0, 0))
    optic_prism((0.15, 0, 0))
    suppressor((0.30, 0, 0))
    grip_vertical((0.45, 0, 0))
    grip_angled((0.60, 0, 0))
    _mag("mag_std", (0.75, 0, 0))
    _mag("mag_ext", (0.90, 0, 0))
    _mag("mag_quick", (1.05, 0, 0))
