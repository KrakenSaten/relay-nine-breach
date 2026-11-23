class_name WeaponDefs
## Data for weapons and attachments. Attachments multiply/override base stats;
## see Weapon.compute_stats(). Every attachment changes at least one gameplay stat.

const WEAPONS := {
	"rifle": {
		"name": "VK-9 CARBINE",
		"model": "res://assets/models/rifle.glb",
		"damage": 30.0,
		"rpm": 760.0,
		"auto": true,
		"mag": 30,
		"reserve": 150,
		"reload": 2.1,
		"reload_empty": 2.7,
		"recoil_v": 1.15,        # degrees of camera pitch per shot
		"recoil_h": 0.45,        # max random yaw per shot
		"recoil_recover": 9.0,   # deg/s returned towards rest
		"spread_hip": 2.6,       # degrees
		"spread_ads": 0.12,
		"spread_move": 2.2,
		"ads_time": 0.2,
		"move_mult": 0.97,
		"noise": 42.0,           # metres a shot alerts robots
		"falloff_start": 25.0,
		"falloff_min": 0.75,
		"hip_pos": Vector3(0.2, -0.21, -0.43),
		"sprint_rot": Vector3(-0.25, 0.75, 0.25),
		"slots": ["optic", "muzzle", "grip", "mag"],
		"shot_sound": "rifle_shot",
		"shot_sound_supp": "rifle_shot_suppressed",
		"kick_back": 0.045,
	},
	"pistol": {
		"name": "P-12 SIDEARM",
		"model": "res://assets/models/pistol.glb",
		"damage": 34.0,
		"rpm": 400.0,
		"auto": false,
		"mag": 15,
		"reserve": 60,
		"reload": 1.45,
		"reload_empty": 1.75,
		"recoil_v": 1.6,
		"recoil_h": 0.5,
		"recoil_recover": 12.0,
		"spread_hip": 2.0,
		"spread_ads": 0.25,
		"spread_move": 1.6,
		"ads_time": 0.13,
		"move_mult": 1.04,
		"noise": 32.0,
		"falloff_start": 15.0,
		"falloff_min": 0.6,
		"hip_pos": Vector3(0.16, -0.16, -0.38),
		"sprint_rot": Vector3(-0.6, 0.2, 0.1),
		"slots": [],
		"shot_sound": "pistol_shot",
		"shot_sound_supp": "pistol_shot_suppressed",
		"kick_back": 0.03,
	},
}

const SLOTS := {
	"optic": ["iron", "optic_reflex", "optic_prism"],
	"muzzle": ["flash_hider", "suppressor"],
	"grip": ["none", "grip_vertical", "grip_angled"],
	"mag": ["mag_std", "mag_ext", "mag_quick"],
}

## Modifiers: *_mult multiply, plain keys override.
const ATTACHMENTS := {
	"iron": {"label": "IRON SIGHTS", "desc": "Fastest aim, widest view.", "ads_fov": 0.86, "ads_time_mult": 0.9},
	"optic_reflex": {"label": "RD-1 REFLEX", "desc": "Clear dot, slightly slower aim.", "ads_fov": 0.8, "ads_time_mult": 1.0, "spread_ads_mult": 0.8},
	"optic_prism": {"label": "PX-2 PRISM 2.0x", "desc": "2x magnification. Slow to aim, poor in CQB.", "ads_fov": 0.48, "ads_time_mult": 1.3, "spread_ads_mult": 0.6, "ads_sens": 0.62, "ads_move_mult": 0.85},
	"flash_hider": {"label": "FLASH HIDER", "desc": "Standard. Loud.", "flash_mult": 1.0},
	"suppressor": {"label": "SR-5 SUPPRESSOR", "desc": "Shots alert robots at 1/4 range. -8% damage.", "noise_mult": 0.25, "damage_mult": 0.92, "recoil_v_mult": 0.9, "ads_time_mult": 1.08, "suppressed": true, "flash_mult": 0.15},
	"none": {"label": "NO GRIP", "desc": "Standard handling."},
	"grip_vertical": {"label": "VG VERTICAL GRIP", "desc": "-35% horizontal, -10% vertical recoil.", "recoil_h_mult": 0.65, "recoil_v_mult": 0.9, "ads_time_mult": 1.05},
	"grip_angled": {"label": "AG ANGLED GRIP", "desc": "-15% aim time, -8% vertical recoil.", "ads_time_mult": 0.85, "recoil_v_mult": 0.92},
	"mag_std": {"label": "30 RND MAG", "desc": "Standard."},
	"mag_ext": {"label": "45 RND EXTENDED", "desc": "+15 rounds. Slower reload and aim.", "mag": 45, "reload_mult": 1.25, "ads_time_mult": 1.1, "move_mult_mult": 0.97},
	"mag_quick": {"label": "25 RND COUPLED", "desc": "-5 rounds. 35% faster reload.", "mag": 25, "reload_mult": 0.65},
}

const DEFAULT_LOADOUT := {"optic": "optic_reflex", "muzzle": "flash_hider", "grip": "grip_vertical", "mag": "mag_std"}
