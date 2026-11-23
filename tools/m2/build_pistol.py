# P-12 polymer-frame service pistol (M2). Origin = bore axis at the rear of the slide, +Y forward.
# The grip rake, cross-section and trigger position match the rifle's in grip-frame terms, so the
# single hand_R pose fits both weapons.
import math
from mathutils import Vector, Matrix
from m2lib import (MB, V, X, Y, Z, rrect, circle2, stadium, boolean, union_parts, finish, join, set_origin, empty,
                   set_parent, xform, tris)
from parts import picatinny, socket_screw
import specs as S

SLIDE_L = 0.188
MAG_LEN = 0.114
MAG_HW, MAG_HD = 0.0112, 0.0160


def _slide():
    m = MB()
    prof = [(-0.0128, -0.0105), (0.0128, -0.0105), (0.0128, 0.0132), (0.0100, 0.0195), (-0.0100, 0.0195), (-0.0128, 0.0132)]
    m.prism(prof, "Y", 0.0, SLIDE_L)
    sl = m.obj("slide", "gunmetal")
    c = MB()
    # ejection port (top-right)
    c.box_mm((-0.0040, 0.0860, 0.0010), (0.0200, 0.1310, 0.0300))
    # barrel bore through the front, recoil-spring channel under it
    c.cyl((0, SLIDE_L, 0.0), 0.0071, 0.010, "Y", n=20)
    c.cyl((0, SLIDE_L, -0.0084), 0.0034, 0.010, "Y", n=12)
    # front + rear cocking serrations (raked)
    for sx in (-1, 1):
        for i in range(7):
            c.box((sx * 0.0134, 0.0090 + i * 0.0050, 0.0030), (0.0020, 0.0018, 0.028), rot=Matrix.Rotation(math.radians(-14), 3, "X"))
        for i in range(5):
            c.box((sx * 0.0134, 0.1440 + i * 0.0050, 0.0030), (0.0020, 0.0018, 0.028), rot=Matrix.Rotation(math.radians(-14), 3, "X"))
        # nose taper
        c.box((sx * 0.0175, 0.1840, -0.0040), (0.010, 0.040, 0.050), rot=Matrix.Rotation(math.radians(sx * 9), 3, "Z"))
    # optic cover plate recess on top, slide cover plate at the rear
    c.prism(rrect(0.044, 0.0150, 0.003, 2, cx=0.0, cy=0.046), "Z", 0.0186, 0.03)
    c.prism(rrect(0.0140, 0.0170, 0.0020, 2, cx=0.0, cy=0.0015), "Y", -0.01, 0.0008)
    boolean(sl, c)
    finish(sl, 0.0007, 2)
    parts = [sl]
    # optic plate and screws
    m = MB()
    m.prism(rrect(0.0430, 0.0140, 0.0028, 2, cx=0.0, cy=0.046), "Z", 0.0170, 0.0193)
    plate = m.obj("optic_plate", "gunmetal")
    finish(plate, 0.0004, 1)
    parts.append(plate)
    for yy in (0.030, 0.062):
        parts.append(socket_screw("plate_screw", (0, yy, 0.0189), (0, 0, 1), r=0.0019, h=0.0006, hex_r=0.0008))
    # extractor
    m = MB()
    m.prism(rrect(0.020, 0.0055, 0.0015, 2, cx=0.132, cy=0.0072), "X", 0.0124, 0.0137)
    ex = m.obj("extractor", "steel")
    finish(ex, 0.0003, 1)
    parts.append(ex)
    # sights: rear with a U notch and two tritium dots, front post with one dot
    m = MB()
    m.prism([(-0.0105, 0.0185), (0.0105, 0.0185), (0.0105, 0.0245), (0.0085, 0.0275), (-0.0085, 0.0275), (-0.0105, 0.0245)], "Y", 0.0060, 0.0170)
    rs = m.obj("rear_sight_p", "gunmetal")
    c = MB()
    c.prism(rrect(0.0036, 0.008, 0.0012, 2, cx=0.0, cy=0.0285), "Y", 0.0, 0.02)
    c.box((0, 0.0050, 0.0270), (0.03, 0.003, 0.003), rot=Matrix.Rotation(math.radians(-30), 3, "X"))   # anti-glare bevel
    boolean(rs, c)
    finish(rs, 0.0003, 1)
    parts.append(rs)
    m = MB()
    m.prism([(-0.0018, 0.0185), (0.0018, 0.0185), (0.0018, 0.0268), (0.0012, 0.0275), (-0.0012, 0.0275), (-0.0018, 0.0268)], "Y", 0.1760, 0.1840)
    fs = m.obj("front_sight_p", "gunmetal")
    finish(fs, 0.0002, 1)
    parts.append(fs)
    for (cx, cy, yy) in ((-0.0055, 0.0232, 0.0058), (0.0055, 0.0232, 0.0058), (0.0, 0.0240, 0.1758)):
        m = MB()
        m.lathe([(0.0, -0.0004), (0.0013, -0.0004), (0.0013, 0.0004), (0.0, 0.0004)], "Y", 10, off=(cx, yy, cy))
        parts.append(m.obj("tritium_dot", "tritium"))
        m = MB()
        m.lathe([(0.0013, -0.0006), (0.0019, -0.0006), (0.0019, 0.0003), (0.0013, 0.0003), (0.0013, -0.0006)], "Y", 10,
                off=(cx, yy, cy), cap0=False, cap1=False)
        parts.append(m.obj("tritium_ring", "steel"))
    o = join(parts, "slide")
    return o


def _barrel():
    m = MB()
    m.lathe([(0.0, 0.080), (0.0068, 0.080), (0.0068, 0.1855), (0.0058, 0.1865), (0.0032, 0.1865), (0.0026, 0.1858),
             (0.0026, 0.170), (0.0, 0.170)], "Y", 20)
    b = m.obj("barrel", "gunmetal")
    u = MB()
    u.box_mm((-0.0086, 0.0860, -0.0040), (0.0086, 0.1300, 0.0098))      # chamber hood
    union_parts(b, u)
    c = MB()
    c.box((0.0, 0.1060, 0.0098), (0.004, 0.006, 0.0016))             # loaded-chamber notch
    boolean(b, c)
    finish(b, 0.0004, 1)
    return b


def _frame():
    parts = []
    m = MB()
    prof = [(-0.0010, -0.0105), (0.1760, -0.0105), (0.1760, -0.0245), (0.1700, -0.0255), (0.0505, -0.0255), (0.0200, -0.0270),
            (0.0040, -0.0220), (-0.0010, -0.0160)]
    m.prism(prof, "X", -0.0122, 0.0122)
    fr = m.obj("frame", "polymer")
    u = MB()
    outer = [(0.0500, -0.0250), (0.1190, -0.0250), (0.1190, -0.0470), (0.1130, -0.0560), (0.1050, -0.0585), (0.0430, -0.0585),
             (0.0398, -0.0560)]
    u.prism(outer, "X", -0.0072, 0.0072)
    union_parts(fr, u)
    c = MB()
    inner = [(0.0535, -0.0262), (0.1120, -0.0262), (0.1120, -0.0460), (0.1080, -0.0515), (0.1020, -0.0527), (0.0458, -0.0527),
             (0.0446, -0.0500)]
    c.prism(inner, "X", -0.02, 0.02)
    c.box((0.0, 0.0825, -0.020), (0.0070, 0.024, 0.0140))        # trigger slot
    boolean(fr, c)
    finish(fr, 0.0008, 2)
    parts.append(fr)
    # grip (lofted like the rifle grip; shares the hand-pose cross-section)
    f, g = S.PG_FWD, S.PG_AXIS
    rings = []
    for s, hw, fwd, bk in S.PG_STATIONS:
        cc = S.PG_TOP + g * s
        rings.append([cc + X * x + f * ff for x, ff in S.grip_ring2d(hw, fwd, bk, 24)])
    m = MB()
    m.loft(rings)
    gr = m.obj("pistol_grip", "polymer")
    c = MB()
    for sx in (-1, 1):
        cc = S.PG_TOP + g * 0.066 + X * sx * 0.0168
        c.prism(rrect(0.028, 0.050, 0.006, 3), a0=-0.0019, a1=0.004, off=cc, basis=(f, g, X * sx))
    # magwell opening at the base
    sb = S.PG_STATIONS[-1][0]
    cb = S.PG_TOP + g * (sb + 0.002)
    c.prism(rrect(2 * MAG_HW + 0.0016, 2 * MAG_HD + 0.0016, 0.003, 2), a0=-0.02, a1=0.01, off=cb + f * 0.0005, basis=(X, f, g))
    boolean(gr, c)
    finish(gr, 0.0007, 2, 35)
    parts.append(gr)
    parts.append(picatinny("p_rail", 0.128, 0.172, -0.0255, sign=-1.0, material="polymer"))
    # controls: slide stop (left), takedown tabs, mag release
    m = MB()
    m.prism([(0.060, -0.0150), (0.0800, -0.0150), (0.0840, -0.0128), (0.0820, -0.0118), (0.060, -0.0125)], "X", -0.0134, -0.0120)
    for sx in (-1, 1):
        m.box((sx * 0.0127, 0.0915, -0.0172), (0.0012, 0.0060, 0.0036))
    m.prism(rrect(0.0095, 0.0080, 0.0025, 2, cx=0.0475, cy=-0.0335), "X", -0.0160, -0.0118)
    ctl = m.obj("controls", "gunmetal")
    finish(ctl, 0.0003, 1)
    parts.append(ctl)
    # recoil spring guide rod tip (visible through the slide nose)
    m = MB()
    m.lathe([(0.0, 0.170), (0.0028, 0.170), (0.0028, 0.1865), (0.0022, 0.1872), (0.0, 0.1872)], "Y", 12, off=(0, 0, -0.0084))
    parts.append(m.obj("guide_rod", "steel"))
    return join(parts, "frame")


def _trigger():
    piv = V((0.0, 0.0800, -0.0160))
    m = MB()
    front = [(0.0858 - 0.0072 * t ** 1.5, -0.0220 - 0.0240 * t) for t in [i / 7 for i in range(8)]]
    back = [(0.0818 - 0.0072 * t ** 1.5 - 0.0006 * t, -0.0220 - 0.0232 * t) for t in [i / 7 for i in range(8)]]
    poly = [(0.0770, -0.0140), (0.0860, -0.0140), (0.0862, -0.0200)] + front + back[::-1] + [(0.0770, -0.0200)]
    m.prism(poly, "X", -0.0030, 0.0030)
    # safety blade in the middle of the face
    blade = [(0.0868 - 0.0072 * t ** 1.5, -0.0250 - 0.0170 * t) for t in [i / 5 for i in range(6)]]
    bpoly = blade + [(b[0] - 0.0030, b[1]) for b in blade[::-1]]
    m.prism(bpoly, "X", -0.0009, 0.0009)
    o = m.obj("trigger", "polymer")
    finish(o, 0.0004, 1)
    set_origin(o, piv)
    return o


def _mag():
    """Pistol magazine in its own frame: origin at the top of the magwell, hangs along local -Z."""
    m = MB()
    rings = []
    stations = [(-0.0010, 0.82, 0.92), (-0.0080, 0.82, 0.92), (-0.0120, 1.0, 1.0), (-MAG_LEN + 0.010, 1.0, 1.0)]
    for z, sxw, syd in stations:
        rings.append([V((x, y, z)) for x, y in rrect(2 * MAG_HW * sxw, 2 * MAG_HD * syd, 0.0040, 3)])
    m.loft(rings)
    body = m.obj("mag_body", "polymer")
    c = MB()
    for i in range(5):   # witness holes on the back face
        c.cyl((0, -MAG_HD, -0.030 - i * 0.012), 0.0018, 0.005, "Y", n=10)
    boolean(body, c)
    finish(body, 0.0004, 1)
    parts = [body]
    m = MB()
    rings = []
    for z, grow in ((-MAG_LEN + 0.012, 0.0), (-MAG_LEN + 0.0050, 0.0), (-MAG_LEN, 0.0)):
        rings.append([V((x, y + 0.0020, z)) for x, y in rrect(2 * MAG_HW + 0.0040, 2 * MAG_HD + 0.0060, 0.0040, 3)])
    m.loft(rings)
    fp = m.obj("mag_floor", "polymer")
    finish(fp, 0.0010, 2)
    parts.append(fp)
    m = MB()
    m.lathe([(0.0, -0.0115), (0.0049, -0.0115), (0.0049, 0.0040), (0.0045, 0.0050), (0.0045, 0.0060), (0.0, 0.0060)], "Y", 12, off=(0, 0, -0.0045))
    m.lathe([(0.0045, 0.0060), (0.0045, 0.0080), (0.0035, 0.0118), (0.0, 0.0128)], "Y", 12, off=(0, 0, -0.0045), cap0=True)
    parts.append(m.obj("mag_round", "copper"))
    return join(parts, "mag")


def mag_matrix():
    top = S.PG_TOP + S.PG_AXIS * S.P_SOCK_MAG_S + S.PG_FWD * 0.0035
    return Matrix.Translation(top) @ Matrix.Rotation(-S.P_GRIP_ANGLE, 4, "X")


def build():
    import poses
    root = empty("Pistol", loc=(0, 0, 0), size=0.04)
    sl = _slide()
    fr = _frame()
    br = _barrel()
    tr = _trigger()
    mg = _mag()
    Mm = mag_matrix()
    mg.matrix_world = Mm @ mg.matrix_world
    for o in (sl, fr, br, tr, mg):
        print(f"  part {o.name:20s} {tris(o)}")
        set_parent(o, root)
    empty("sock_muzzle", loc=(0, 0.190, 0.0), parent=root)
    empty("sock_iron", loc=(0, 0.0, 0.0275), parent=root)
    empty("sock_eject", loc=(0.020, 0.110, 0.010), parent=root)
    empty("sock_mag", M=Mm, parent=root)
    for n, M in poses.pistol_hand_sockets(Mm).items():
        empty(n, M=M, parent=root, size=0.03)
    return root
