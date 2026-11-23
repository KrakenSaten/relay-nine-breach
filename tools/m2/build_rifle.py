# VK-9 carbine (M2). Origin = bore axis at the rear face of the upper receiver, +Y forward.
import math
from mathutils import Vector, Matrix
from m2lib import (MB, V, X, Y, Z, rrect, circle2, stadium, boolean, union_parts, finish, join, set_origin,
                   empty, set_parent, rot_about, xform, subsurf, sharp_by_angle, apply_mods, perp_basis)
from parts import picatinny, socket_screw, qd_cup, pic_profile, PIC_H
import specs as S

MUZZLE_Y = 0.655


def _upper():
    m = MB()
    prof = [(-0.0145, -0.0115), (0.0145, -0.0115), (0.0145, 0.0215), (0.0120, 0.0298), (0.0109, S.RAIL_Z0),
            (-0.0109, S.RAIL_Z0), (-0.0120, 0.0298), (-0.0145, 0.0215)]
    m.prism(prof, "Y", 0.0, 0.183)
    up = m.obj("upper_receiver", "anodized")
    u = MB()
    # brass deflector behind the ejection port
    u.prism([(0.072, -0.002), (0.0972, -0.002), (0.0972, 0.0212), (0.088, 0.0262), (0.079, 0.0262), (0.072, 0.014)], "X", 0.010, 0.0205)
    # forward assist housing (angled tube) and dust-cover hinge boss
    u.cyl_between((0.0168, 0.017, 0.0095), (0.0126, 0.077, 0.0095), 0.0071, n=20)
    u.cyl_between((0.0148, 0.095, -0.0085), (0.0148, 0.167, -0.0085), 0.0022, n=10)
    union_parts(up, u)
    c = MB()
    c.prism(rrect(0.066, 0.0205, 0.003, 2, cx=0.1305, cy=0.006), "X", -0.004, 0.03)       # ejection port
    c.box((0.0, 0.018, 0.0236), (0.0158, 0.062, 0.0126))                                   # charging handle channel
    c.prism(rrect(0.118, 0.020, 0.004, 2, cx=0.098, cy=0.0055), "X", -0.03, -0.0137)      # billet side panel
    c.prism(rrect(0.040, 0.012, 0.003, 2, cx=0.040, cy=-0.003), "X", 0.0137, 0.03)        # right side panel
    for i in range(3):                                                                    # deflector grooves
        c.box((0.0208, 0.0795 + i * 0.0055, 0.012), (0.003, 0.0018, 0.022))
    boolean(up, c)
    finish(up, 0.0007, 2)
    rail = picatinny("upper_rail", -0.004, 0.183, S.RAIL_Z0)
    # forward assist plunger
    m = MB()
    a = (V((0.0126, 0.077, 0.0095)) - V((0.0168, 0.017, 0.0095))).normalized()
    p0 = V((0.0168, 0.017, 0.0095))
    m.lathe([(0.0, -0.0115), (0.0040, -0.0115), (0.0054, -0.0104), (0.0054, -0.0062), (0.0046, -0.0058), (0.0054, -0.0054),
             (0.0054, -0.0030), (0.0046, -0.0026), (0.0054, -0.0022), (0.0058, 0.0005)], n=16, off=p0, axis_vec=a)
    fa = m.obj("fwd_assist", "gunmetal")
    finish(fa, 0.0003, 1)
    # dust cover, open and hanging against the receiver
    m = MB()
    m.box((0.0, 0.1315, 0.0105), (0.0016, 0.069, 0.021))
    m.box((0.0011, 0.1315, 0.0120), (0.0012, 0.060, 0.0030))
    m.cyl((0.0, 0.1315, 0.0), 0.0021, 0.07, "Y", n=10)
    dc = m.obj("dust_cover", "gunmetal")
    finish(dc, 0.0003, 1)
    xform(dc, Matrix.Translation(V((0.0148, 0.0, -0.0085))) @ Matrix.Rotation(math.radians(150), 4, "Y"))
    return [up, rail, fa, dc]


def _lower():
    m = MB()
    side = [(-0.012, -0.0115), (0.193, -0.0115), (0.193, -0.024), (0.188, -0.031), (0.126, -0.034), (0.120, -0.0365),
            (0.020, -0.0365), (0.008, -0.031), (-0.006, -0.026), (-0.012, -0.020)]
    m.prism(side, "X", -0.0145, 0.0145)
    lo = m.obj("lower_receiver", "anodized")
    u = MB()
    u.prism(rrect(0.0335, 0.077, 0.004, 2, cy=0.1595), "Z", S.MAGWELL_BOTTOM + 0.005, -0.016)
    u.prism(rrect(0.0368, 0.0815, 0.0055, 2, cy=0.1595), "Z", S.MAGWELL_BOTTOM, S.MAGWELL_BOTTOM + 0.0075)
    u.lathe([(0.0168, -0.012), (0.0168, 0.003)], "Y", 24)
    # mag release fence (right) and bolt catch bosses (left)
    u.lathe([(0.0050, 0.0140), (0.0078, 0.0140), (0.0078, 0.0161), (0.0050, 0.0161)], "X", 20, off=(0, 0.111, -0.0285))
    u.box((-0.0150, 0.109, -0.022), (0.003, 0.016, 0.012))
    union_parts(lo, u)
    c = MB()
    c.prism(rrect(0.0245, 0.0625, 0.003, 2, cy=0.160), "Z", -0.11, -0.0102)                # magwell cavity
    for i in range(4):                                                                     # front grip grooves
        c.box((0.0, 0.1985, -0.046 - i * 0.0075), (0.05, 0.0028, 0.0026))
    for sx in (-1, 1):                                                                     # magwell side panels
        c.prism(rrect(0.054, 0.030, 0.004, 2, cx=0.1595, cy=-0.058), "X", sx * 0.0160, sx * 0.03)
    c.box((0.0, 0.0815, -0.035), (0.0086, 0.025, 0.010))                                    # trigger slot
    c.prism(circle2(0.0050, 16), "X", 0.0158, 0.03, off=(0, 0.111, -0.0285))                # mag release hole
    boolean(lo, c, self_inter=False)
    finish(lo, 0.0008, 2)
    # trigger guard with a real opening; rear edge follows the grip front strap
    m = MB()
    outer = [(0.0585, -0.0345), (0.1250, -0.0345), (0.1250, -0.0630), (0.1225, -0.0690), (0.1160, -0.0725),
             (0.0500, -0.0725), (0.0462, -0.0700)]
    m.prism(outer, "X", -0.0058, 0.0058)
    tg = m.obj("trigger_guard", "anodized")
    c = MB()
    inner = [(0.0640, -0.0368), (0.1180, -0.0368), (0.1180, -0.0610), (0.1150, -0.0652), (0.1100, -0.0665),
             (0.0565, -0.0665), (0.0535, -0.0640)]
    c.prism(inner, "X", -0.02, 0.02)
    boolean(tg, c)
    finish(tg, 0.0009, 2)
    # bolt catch paddle
    m = MB()
    m.prism([(0.101, -0.0300), (0.118, -0.0300), (0.1195, -0.0245), (0.1165, -0.0150), (0.1045, -0.0150), (0.101, -0.0205)],
            "X", -0.0178, -0.0160)
    for i in range(3):
        m.box((-0.0180, 0.1035 + i * 0.0045, -0.0255), (0.0012, 0.0016, 0.007))
    bc = m.obj("bolt_catch", "anodized")
    finish(bc, 0.0003, 1)
    # pins: front pivot, rear takedown, trigger, hammer, bolt catch roll pin
    m = MB()
    for (py, pz, r, head) in ((0.186, -0.0075, 0.0034, True), (0.004, -0.0075, 0.0034, True),
                              (0.0855, -0.0255, 0.0024, False), (0.064, -0.0205, 0.0024, False)):
        for sx in (-1, 1):
            hh = 0.0012 if (head and sx < 0) else 0.0005
            m.lathe([(r, 0.0), (r, hh - 0.0003), (r - 0.0004, hh), (0.0, hh)], n=10, off=(sx * 0.0144, py, pz), axis_vec=(sx, 0, 0))
    m.lathe([(0.0012, 0.0), (0.0012, 0.0004), (0.0, 0.0004)], n=8, off=(-0.0160, 0.112, -0.0170), axis_vec=(-1, 0, 0))
    pins = m.obj("lower_pins", "steel")
    finish(pins, 0.0, 1, 40)
    return [lo, tg, bc, pins]


def _grip():
    """Pistol grip lofted from the shared stations (matches the hand pose solver)."""
    f, g = S.RG_FWD, S.RG_AXIS
    rings = []
    for s, hw, fr, bk in S.RG_STATIONS:
        c = S.RG_TOP + g * s
        rings.append([c + X * x + f * ff for x, ff in S.grip_ring2d(hw, fr, bk, 24)])
    # rounded bottom: shrink toward the base
    s_end = S.RG_STATIONS[-1][0]
    hw, fr, bk = S.RG_STATIONS[-1][1:]
    for k, (ds, sc) in enumerate(((0.0025, 0.86), (0.0038, 0.55))):
        c = S.RG_TOP + g * (s_end + ds)
        rings.append([c + X * x * sc + f * ff * sc for x, ff in S.grip_ring2d(hw, fr, bk, 24)])
    m = MB()
    m.loft(rings, cap0=True, cap1=True)
    o = m.obj("pistol_grip", "polymer")
    # texture panels and a storage-cap seam
    c = MB()
    for sx in (-1, 1):
        cc = S.RG_TOP + g * 0.070 + X * sx * 0.0168
        c.prism(rrect(0.028, 0.046, 0.006, 3), a0=-0.0019, a1=0.004, off=cc, basis=(f, g, X * sx))
    boolean(o, c)
    finish(o, 0.0006, 2, 35)
    return [o]


def _trigger():
    m = MB()
    front = [(0.0890 - 0.0080 * t ** 1.5, -0.034 - 0.028 * t) for t in [i / 7 for i in range(8)]]
    back = [(0.0848 - 0.0080 * t ** 1.5 - 0.0005 * t, -0.034 - 0.0272 * t) for t in [i / 7 for i in range(8)]]
    poly = [(0.0800, -0.0215), (0.0915, -0.0215), (0.0915, -0.0300)] + front + back[::-1] + [(0.0800, -0.0300)]
    m.prism(poly, "X", -0.0028, 0.0028)
    o = m.obj("trigger", "gunmetal")
    c = MB()
    for i in range(4):   # serrated face
        t = 0.25 + i * 0.15
        c.box((0.0, 0.0892 - 0.0080 * t ** 1.5, -0.034 - 0.028 * t), (0.01, 0.0012, 0.0012))
    boolean(o, c)
    finish(o, 0.0004, 1)
    set_origin(o, S.R_TRIGGER_PIVOT)
    return o


def _selector():
    piv = V((0.0, 0.030, -0.021))
    m = MB()
    m.lathe([(0.0, -0.0172), (0.0046, -0.0172), (0.0050, -0.0160), (0.0050, 0.0160), (0.0044, 0.0168), (0.0, 0.0168)], "X", 18, off=piv)
    lever = [(-0.0030, 0.0045), (0.0170, 0.0030), (0.0195, 0.0010), (0.0195, -0.0020), (0.0170, -0.0035), (-0.0030, -0.0045)]
    m.prism([(piv.y + a, piv.z + b) for a, b in lever], "X", -0.0192, -0.0168)
    m.box((-0.0196, piv.y + 0.0172, piv.z), (0.0012, 0.0026, 0.0052))
    short = [(-0.0025, 0.0040), (0.0100, 0.0026), (0.0115, 0.0), (0.0100, -0.0026), (-0.0025, -0.0040)]
    m.prism([(piv.y - a, piv.z + b) for a, b in short], "X", 0.0166, 0.0186)
    o = m.obj("selector", "gunmetal")
    finish(o, 0.0003, 1)
    set_origin(o, piv)
    return o


def _mag_release():
    c = V((0.0158, 0.111, -0.0285))
    m = MB()
    m.lathe([(0.0042, -0.0030), (0.0042, 0.0010), (0.0038, 0.0016), (0.0030, 0.0016), (0.0030, 0.0012), (0.0022, 0.0012),
             (0.0022, 0.0016), (0.0012, 0.0016), (0.0012, 0.0012), (0.0, 0.0012)], "X", 14, off=c)
    o = m.obj("mag_release", "gunmetal")
    finish(o, 0.0002, 1, 40)
    set_origin(o, c)
    return o


def _charging_handle():
    m = MB()
    poly = [(-0.0074, 0.050), (0.0074, 0.050), (0.0074, -0.0025), (0.0215, -0.0060), (0.0228, -0.0095), (0.0215, -0.0135),
            (-0.0215, -0.0135), (-0.0228, -0.0095), (-0.0215, -0.0060), (-0.0074, -0.0025)]
    m.prism(poly, "Z", 0.0185, 0.0292)
    for sx in (-1, 1):
        m.box((sx * 0.0170, -0.0098, 0.0302), (0.0100, 0.0060, 0.0024))
        for i in range(2):
            m.box((sx * (0.0145 + i * 0.0040), -0.0098, 0.0317), (0.0012, 0.0060, 0.0012))
    o = m.obj("charging_handle", "anodized")
    c = MB()
    c.box((0.0, -0.0150, 0.024), (0.0110, 0.006, 0.020))   # finger notch in the rear face
    boolean(o, c)
    finish(o, 0.0005, 1)
    set_origin(o, (0.0, -0.0085, 0.024))
    return o


def _bolt():
    m = MB()
    m.lathe([(0.0, 0.058), (0.0092, 0.058), (0.0099, 0.0595), (0.0099, 0.1765), (0.0092, 0.178), (0.0068, 0.178),
             (0.0068, 0.1915), (0.0060, 0.1935), (0.0, 0.1935)], "Y", 16)
    for k in range(7):   # bolt lugs
        a = 2 * math.pi * k / 7 + 0.2
        m.box((math.cos(a) * 0.0074, 0.1885, math.sin(a) * 0.0074), (0.0030, 0.0050, 0.0030),
              rot=Matrix.Rotation(-a, 3, "Y"))
    m.box((0.0, 0.130, 0.0105), (0.0062, 0.060, 0.0030))     # gas key
    o = m.obj("bolt", "gunmetal")
    c = MB()
    for i in range(7):   # forward-assist notches on the carrier
        c.box((0.0101, 0.108 + i * 0.0045, 0.0), (0.0030, 0.0018, 0.0140))
    c.box((0.0101, 0.150, 0.0), (0.0030, 0.010, 0.0022))      # extractor relief
    boolean(o, c)
    finish(o, 0.0004, 1)
    set_origin(o, (0.0, 0.130, 0.0))
    return o


def _stock():
    out = []
    # receiver extension (buffer tube) with an indexed bottom rail
    m = MB()
    m.lathe([(0.0148, -0.006), (0.0148, -0.236), (0.0140, -0.2395), (0.0100, -0.2410)], "Y", 24)
    tube = m.obj("buffer_tube", "anodized")
    u = MB()
    u.box((0.0, -0.128, -0.0148), (0.0084, 0.216, 0.0056))
    union_parts(tube, u)
    c = MB()
    for i in range(7):
        c.cyl((0.0, -0.050 - i * 0.025, -0.017), 0.0019, 0.012, "Z", n=10)
    boolean(tube, c)
    finish(tube, 0.0006, 2)
    out.append(tube)
    # end plate + castle nut
    m = MB()
    m.lathe([(0.0150, -0.0120), (0.0196, -0.0120), (0.0196, -0.0136), (0.0150, -0.0136)], "Y", 24)
    m.lathe([(0.0149, -0.0136), (0.0190, -0.0136), (0.0190, -0.0214), (0.0149, -0.0214)], "Y", 24)
    nut = m.obj("castle_nut", "gunmetal")
    c = MB()
    for k in range(6):
        a = math.radians(30 + 60 * k)
        c.box((math.cos(a) * 0.0195, -0.0205, math.sin(a) * 0.0195), (0.0045, 0.006, 0.0045), rot=Matrix.Rotation(-a, 3, "Y"))
    boolean(nut, c)
    finish(nut, 0.0003, 1)
    out.append(nut)
    # QD adapter on the tube
    m = MB()
    m.lathe([(0.0149, -0.046), (0.0176, -0.046), (0.0176, -0.030), (0.0149, -0.030)], "Y", 20)
    qa = m.obj("qd_adapter", "anodized")
    u = MB()
    u.box((-0.0185, -0.038, -0.001), (0.0130, 0.016, 0.017))
    union_parts(qa, u)
    c = MB()
    c.cyl((-0.025, -0.038, -0.001), 0.0058, 0.008, "X", n=16)
    c.box((0.0, -0.038, 0.017), (0.006, 0.020, 0.006))          # clamp split
    boolean(qa, c)
    finish(qa, 0.0006, 1)
    out.append(qa)
    out.append(qd_cup("qd_tube", (-0.0248, -0.038, -0.001), (-1, 0, 0)))
    out.append(socket_screw("qd_adapter_screw", (0.0035, -0.038, 0.0195), (0, 0, 1), r=0.0022))
    # stock body
    m = MB()
    stk = [(-0.1470, 0.0200), (-0.1520, 0.0228), (-0.2600, 0.0255), (-0.2705, 0.0240), (-0.2720, 0.0180), (-0.2720, -0.0760),
           (-0.2680, -0.0820), (-0.2600, -0.0830), (-0.2420, -0.0700), (-0.2050, -0.0420), (-0.1760, -0.0250), (-0.1560, -0.0215),
           (-0.1480, -0.0180), (-0.1440, -0.0120), (-0.1440, 0.0120)]
    m.prism(stk, "X", -0.0195, 0.0195)
    st = m.obj("stock", "polymer")
    c = MB()
    win = [(-0.2140, -0.0275), (-0.2540, -0.0275), (-0.2555, -0.0300), (-0.2555, -0.0615), (-0.2525, -0.0625), (-0.2165, -0.0300)]
    c.prism(win, "X", -0.03, 0.03)
    for sx in (-1, 1):
        c.prism(rrect(0.074, 0.021, 0.005, 2, cx=-0.205, cy=0.0045), "X", sx * 0.0185, sx * 0.03)
        c.prism(circle2(0.0050, 20), "X", sx * 0.012, sx * 0.03, off=(0, -0.2635, -0.0710))
    c.box((0.0, -0.162, -0.024), (0.013, 0.036, 0.010))              # lever channel
    boolean(st, c)
    finish(st, 0.0030, 3, 30)
    out.append(st)
    for sx in (-1, 1):
        out.append(qd_cup("qd_stock", (sx * 0.0193, -0.2635, -0.0710), (sx, 0, 0)))
    # adjustment lever
    m = MB()
    m.prism([(-0.1500, -0.0185), (-0.1860, -0.0262), (-0.1885, -0.0298), (-0.1845, -0.0318), (-0.1500, -0.0248)], "X", -0.0055, 0.0055)
    for i in range(3):
        m.box((0.0, -0.1770 + i * 0.0040, -0.0300 + i * 0.0009), (0.0100, 0.0014, 0.0018),
              rot=Matrix.Rotation(math.radians(-12), 3, "X"))
    m.cyl((0.0, -0.1530, -0.0205), 0.0019, 0.0170, "X", n=12)
    lever = m.obj("stock_lever", "anodized")
    finish(lever, 0.0004, 1)
    out.append(lever)
    # buttpad with ribs
    m = MB()
    m.prism(rrect(0.0165, 0.1110, 0.0055, 3, cx=-0.2795, cy=-0.0300), "X", -0.0205, 0.0205)
    bp = m.obj("buttpad", "rubber")
    c = MB()
    for i in range(6):
        c.box((0.0, -0.2885, -0.0700 + i * 0.0150), (0.05, 0.0035, 0.0034))
    boolean(bp, c)
    finish(bp, 0.0022, 1, 30)
    out.append(bp)
    return out


def _handguard():
    out = []
    m = MB()
    m.tube(S.HG_OUT, S.HG_IN, "Y", S.HG_Y0, S.HG_Y1)
    hg = m.obj("handguard", "anodized")
    c = MB()
    side_ys = [0.225 + 0.040 * i for i in range(6)]
    for sx in (-1, 1):
        for yc in side_ys:      # M-LOK slots, 3 and 9 o'clock
            c.prism(stadium(0.032, 0.0075, 3, cx=yc, cy=0.009), "X", sx * 0.018, sx * 0.03)
        for yc in [0.245 + 0.040 * i for i in range(5)]:   # lower 45-degree lightening slots
            n = V((sx * 0.827, 0.0, -0.562))
            cen = V((sx * 0.0187, yc, -0.0180))
            U = Y
            W = n.cross(U).normalized()
            c.prism(stadium(0.020, 0.0055, 3), a0=-0.006, a1=0.006, off=cen, basis=(U, W, n))
        for yc in [0.262 + 0.040 * i for i in range(4)]:   # upper 45-degree round ports
            n = V((sx * 0.675, 0.0, 0.738)).normalized()
            cen = V((sx * 0.0183, yc, 0.0338))
            c.prism(circle2(0.0030, 8, a0=math.pi / 8), a0=-0.006, a1=0.006, off=cen, basis=(Y, n.cross(Y).normalized(), n))
    for yc in (0.225, 0.265, 0.305, 0.440):      # 6 o'clock M-LOK slots
        c.prism([(v, u) for u, v in stadium(0.032, 0.0075, 3, cx=yc)], "Z", -0.03, -0.018)
    boolean(hg, c)
    finish(hg, 0.0007, 1)
    out.append(hg)
    out.append(picatinny("handguard_rail", S.HG_Y0, S.HG_Y1, S.RAIL_Z0))
    out.append(picatinny("grip_rail", S.GRIP_RAIL_Y[0], S.GRIP_RAIL_Y[1], S.HG_BOTTOM, sign=-1.0))
    for zz in (-0.0040, 0.0200):
        out.append(socket_screw("hg_clamp_screw", (-0.0235, 0.1975, zz), (-1, 0, 0), r=0.0027))
        m = MB()
        m.lathe([(0.0024, 0.0), (0.0024, 0.0006), (0.0, 0.0006)], n=12, off=(0.0235, 0.1975, zz), axis_vec=(1, 0, 0))
        out.append(m.obj("hg_nut", "steel"))
    out.append(qd_cup("qd_handguard", (-0.0233, 0.455, 0.009), (-1, 0, 0)))
    # barrel nut visible in the gap to the receiver
    m = MB()
    m.lathe([(0.0130, 0.1800), (0.0178, 0.1800), (0.0182, 0.1810), (0.0182, 0.1885), (0.0130, 0.1885)], "Y", 24)
    bn = m.obj("barrel_nut", "gunmetal")
    finish(bn, 0.0003, 1)
    out.append(bn)
    return out


def _barrel():
    m = MB()
    prof = [(0.0098, 0.185), (0.0098, 0.468), (0.0092, 0.4705), (0.0092, 0.590), (0.0088, 0.5935), (0.0088, 0.6355),
            (0.0083, 0.637), (0.0070, 0.637), (0.0070, 0.6538), (0.0062, MUZZLE_Y), (0.0036, MUZZLE_Y), (0.0029, 0.6542),
            (0.0029, 0.640), (0.0, 0.640)]
    m.lathe(prof, "Y", 24)
    o = m.obj("barrel", "gunmetal")
    finish(o, 0.0003, 1, 35)
    return o


def _flash_hider():
    m = MB()
    prof = [(0.0, 0.634), (0.0098, 0.634), (0.0106, 0.6348), (0.0106, 0.6455), (0.0112, 0.6465), (0.0116, 0.6475),
            (0.0116, 0.6860), (0.0110, 0.6880), (0.0081, 0.6880), (0.0076, 0.6870), (0.0076, 0.6600), (0.0, 0.6600)]
    m.lathe(prof, "Y", 20)
    o = m.obj("flash_hider", "gunmetal")
    c = MB()
    for k in range(3):   # three prongs
        a = math.radians(90 + 120 * k)
        d = V((math.cos(a), 0.0, math.sin(a)))
        c.box(V((0.0, 0.6795, 0.0)) + d * 0.010, (0.0036, 0.019, 0.0036), rot=Matrix.Rotation(-a, 3, "Y"))
        c.box(V((0.0, 0.6795, 0.0)) + d * 0.010 + V((0, -0.0095, 0)), (0.0036, 0.0036, 0.0036), rot=Matrix.Rotation(-a, 3, "Y"))
    for sx in (-1, 1):   # wrench flats
        c.box((sx * 0.0125, 0.640, 0.0), (0.006, 0.0095, 0.03))
    boolean(o, c)
    finish(o, 0.0004, 1)
    set_origin(o, (0.0, MUZZLE_Y, 0.0))
    return o


def _sight_base(name, y0, y1, screw_y, pocket):
    m = MB()
    u_prof = [(-0.0128, 0.0405), (-0.0109, 0.0405), (-0.0109, S.RAIL_TOP), (0.0109, S.RAIL_TOP), (0.0109, 0.0405),
              (0.0128, 0.0405), (0.0128, 0.0545), (-0.0128, 0.0545)]
    m.prism(u_prof, "Y", y0, y1)
    o = m.obj(name, "anodized")
    c = MB()
    c.box_mm((-0.0091, pocket[0], 0.0526), (0.0091, pocket[1], 0.060))
    boolean(o, c)
    finish(o, 0.0005, 2)
    scr = socket_screw(name + "_screw", (-0.0128, screw_y, 0.0445), (-1, 0, 0), r=0.0030)
    m = MB()
    m.lathe([(0.0030, 0.0), (0.0030, 0.0012), (0.0024, 0.0016), (0.0, 0.0016)], n=6, off=(0.0128, screw_y, 0.0445), axis_vec=(1, 0, 0))
    nut = m.obj(name + "_nut", "gunmetal")
    finish(nut, 0.0002, 1, 25)
    return [o, scr, nut]


def _rear_sight():
    hinge = V((0.0, 0.0, 0.0548))
    m = MB()
    leaf = [(-0.0085, 0.0535), (0.0085, 0.0535), (0.0085, 0.0640), (0.0060, 0.0695), (0.0020, 0.0712), (-0.0020, 0.0712),
            (-0.0060, 0.0695), (-0.0085, 0.0640)]
    m.prism(leaf, "Y", -0.0020, 0.0020)
    m.lathe([(0.0042, -0.0032), (0.0042, 0.0), (0.0016, 0.0), (0.0016, -0.0032), (0.0042, -0.0032)], "Y", 12,
            off=(0, 0, 0.062), cap0=False, cap1=False)
    m.cyl((0.0, 0.0, 0.0548), 0.0022, 0.0150, "X", n=12)
    o = m.obj("rear_sight", "anodized")
    c = MB()
    c.cyl((0.0, 0.0, 0.062), 0.0013, 0.02, "Y", n=12)
    for sx in (-1, 1):   # grip serrations on the leaf edges
        for i in range(3):
            c.box((sx * 0.0088, 0.0, 0.0565 + i * 0.0022), (0.0014, 0.006, 0.0009))
    boolean(o, c, self_inter=True)
    finish(o, 0.0003, 1)
    set_origin(o, hinge)
    return o


def _front_sight():
    hy = 0.459
    hinge = V((0.0, hy, 0.0548))
    m = MB()
    hood = [(-0.0090, 0.0535), (0.0090, 0.0535), (0.0090, 0.0665), (0.0065, 0.0710), (0.0, 0.0724), (-0.0065, 0.0710), (-0.0090, 0.0665)]
    m.prism(hood, "Y", hy - 0.0021, hy + 0.0021)
    m.cyl((0.0, hy, 0.0548), 0.0022, 0.0150, "X", n=12)
    o = m.obj("front_sight", "anodized")
    c = MB()
    c.prism(circle2(0.0058, 20, cy=0.0636), "Y", hy - 0.01, hy + 0.01)
    boolean(o, c)
    u = MB()
    u.prism([(-0.0011, 0.0560), (0.0011, 0.0560), (0.0011, 0.0614), (0.0006, 0.0620), (-0.0006, 0.0620), (-0.0011, 0.0614)],
            "Y", hy - 0.0015, hy + 0.0015)
    union_parts(o, u)
    finish(o, 0.0003, 1)
    set_origin(o, hinge)
    return o


def build(hand_sockets=None):
    root = empty("Rifle", loc=(0, 0, 0), size=0.05)
    static = []
    static += _upper()
    static += _lower()
    static += _grip()
    static += _stock()
    static += _handguard()
    static.append(_barrel())
    static += _sight_base("rear_sight_base", -0.012, 0.016, 0.0095, (0.0010, 0.0180))
    static += _sight_base("front_sight_base", 0.437, 0.465, 0.443, (0.4415, 0.4590))
    moving = [_charging_handle(), _bolt(), _trigger(), _selector(), _mag_release(), _flash_hider(), _front_sight(), _rear_sight()]
    from m2lib import tris
    for o in static + moving:
        print(f"  part {o.name:26s} {tris(o)}")
    # merge static hardware into a few logical meshes (fewer draw calls)
    groups = {}
    for o in static:
        key = o.name.split(".")[0]
        if key.startswith(("upper", "fwd_assist", "dust_cover")):
            g = "upper_receiver"
        elif key.startswith(("lower", "trigger_guard", "bolt_catch")):
            g = "lower_receiver"
        elif key.startswith(("buffer", "castle", "qd_adapter", "qd_tube", "stock", "qd_stock", "buttpad")):
            g = "stock"
        elif key.startswith(("handguard", "grip_rail", "hg_", "qd_handguard", "barrel_nut")):
            g = "handguard"
        elif key.startswith(("rear_sight_base", "front_sight_base")):
            g = "sight_bases"
        else:
            g = key
        groups.setdefault(g, []).append(o)
    meshes = []
    for g, objs in groups.items():
        meshes.append(join(objs, g))
    for o in meshes + moving:
        set_parent(o, root)
    socks = {
        "sock_optic": (0.0, 0.090, S.RAIL_TOP),
        "sock_muzzle": (0.0, MUZZLE_Y, 0.0),
        "sock_grip": tuple(S.SOCK_GRIP),
        "sock_mag": tuple(S.MAG_TOP),
        "sock_eject": (0.028, 0.130, 0.008),
        "sock_iron": (0.0, 0.0, 0.062),
    }
    for n, p in socks.items():
        empty(n, loc=p, parent=root)
    for n, M in (hand_sockets or {}).items():
        empty(n, M=M, parent=root, size=0.03)
    return root, meshes + moving
