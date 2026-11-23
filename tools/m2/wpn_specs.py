# Shared dimensions used by both weapon geometry and the hand-pose solver, so the virtual
# grips the hands are posed around match the real meshes exactly.
import math
from mathutils import Vector

V = Vector

# ---------------------------------------------------------------- rifle pistol grip
RG_ANGLE = math.radians(18.4)                       # grip rake (from vertical)
RG_TOP = V((0.0, 0.036, -0.030))                    # grip axis point inside the lower
RG_AXIS = V((0.0, -math.sin(RG_ANGLE), -math.cos(RG_ANGLE)))   # down the grip
RG_FWD = V((0.0, math.cos(RG_ANGLE), -math.sin(RG_ANGLE)))     # toward the front strap
# stations: (s along axis, half width X, front extent, back extent)
RG_STATIONS = [
    (0.000, 0.0130, 0.0222, 0.0250),
    (0.010, 0.0140, 0.0222, 0.0285),
    (0.022, 0.0148, 0.0222, 0.0278),
    (0.036, 0.0153, 0.0222, 0.0242),
    (0.052, 0.0156, 0.0224, 0.0228),
    (0.068, 0.0158, 0.0230, 0.0224),
    (0.084, 0.0158, 0.0226, 0.0224),
    (0.098, 0.0156, 0.0228, 0.0228),
    (0.108, 0.0160, 0.0240, 0.0240),
    (0.115, 0.0152, 0.0232, 0.0232),
]
GRIP_PW = 2.7   # superellipse exponent of the grip cross-section


def grip_ring2d(hw, fr, bk, n=20, pw=GRIP_PW):
    """Cross-section (x, f) of a pistol grip: superellipse, different front/back extents."""
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        x = hw * math.copysign(abs(c) ** (2 / pw), c)
        f = (fr if s > 0 else bk) * math.copysign(abs(s) ** (2 / pw), s)
        pts.append((x, f))
    return pts


def rg_station(s):
    """Interpolated (hw, fr, bk) at s."""
    st = RG_STATIONS
    if s <= st[0][0]:
        return st[0][1:]
    for a, b in zip(st, st[1:]):
        if a[0] <= s <= b[0]:
            t = (s - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
    return st[-1][1:]


# rifle trigger: pivot and the point on the blade face the index pad presses
R_TRIGGER_PIVOT = V((0.0, 0.0855, -0.0255))
R_TRIGGER_PAD = V((0.0, 0.0862, -0.0490))         # point on the front face of the blade

# ---------------------------------------------------------------- rifle handguard
HG_Y0, HG_Y1 = 0.186, 0.470
HG_OUT = [(-0.0130, 0.0386), (0.0130, 0.0386), (0.0235, 0.0290), (0.0235, -0.0110),
          (0.0140, -0.0250), (-0.0140, -0.0250), (-0.0235, -0.0110), (-0.0235, 0.0290)]
HG_IN = [(-0.0110, 0.0358), (0.0110, 0.0358), (0.0207, 0.0278), (0.0207, -0.0100),
         (0.0128, -0.0222), (-0.0128, -0.0222), (-0.0207, -0.0100), (-0.0207, 0.0278)]
RAIL_Z0 = 0.0386          # rail base (top of receiver / handguard)
RAIL_TOP = 0.0480
HG_BOTTOM = -0.0250
GRIP_RAIL_Y = (0.352, 0.408)   # short rail section under the handguard
SOCK_GRIP = V((0.0, 0.380, HG_BOTTOM - 0.0094))
HAND_L_Y = 0.300               # support hand position along the handguard

# ---------------------------------------------------------------- magazines / magwell
MAG_TOP = V((0.0, 0.160, -0.0135))   # feed lips when seated (sock_mag)
MAG_W = 0.0226                        # body thickness (X)
MAG_D = 0.0600                        # body depth front-back at the top
MAGWELL_BOTTOM = -0.0875

# ---------------------------------------------------------------- vertical grip
VG_R = 0.0135             # handle radius (27 mm)
VG_TOP = -0.012           # handle starts below the clamp (grip space)
VG_LEN = 0.088
VG_HAND_Z = -0.050        # grip-space height of the middle finger

# ---------------------------------------------------------------- pistol
P_GRIP_ANGLE = RG_ANGLE
PG_TOP = V((0.0, 0.030, -0.020))
PG_AXIS = RG_AXIS.copy()
PG_FWD = RG_FWD.copy()
PG_STATIONS = [
    (0.000, 0.0118, 0.0215, 0.0240),
    (0.008, 0.0126, 0.0215, 0.0290),
    (0.020, 0.0140, 0.0215, 0.0272),
    (0.034, 0.0150, 0.0218, 0.0238),
    (0.050, 0.0155, 0.0222, 0.0228),
    (0.066, 0.0157, 0.0226, 0.0226),
    (0.082, 0.0156, 0.0226, 0.0226),
    (0.096, 0.0157, 0.0230, 0.0232),
    (0.104, 0.0158, 0.0232, 0.0234),
]
PG_HAND_S = 0.050           # middle-finger station on the pistol grip
P_SOCK_MAG_S = -0.0074      # magazine origin station (top of the magwell under the slide)


def pg_station(s):
    st = PG_STATIONS
    if s <= st[0][0]:
        return st[0][1:]
    for a, b in zip(st, st[1:]):
        if a[0] <= s <= b[0]:
            t = (s - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in (1, 2, 3))
    return st[-1][1:]


def rifle_to_pistol_grip(p):
    """Map a rifle point into pistol space through the matching grip frames (same hand pose fits both)."""
    pr = RG_TOP + RG_AXIS * 0.056
    pp = PG_TOP + PG_AXIS * PG_HAND_S
    d = V(p) - pr
    return pp + d
