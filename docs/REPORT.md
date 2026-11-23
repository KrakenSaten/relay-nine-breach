# BREACH Vertical Slice 0.1: status report (2026-11-23)

## Blocker and decision

**Unreal Engine was not available.** There was no UE install, no Epic
launcher and no Visual Studio C++ toolchain, and installing UE needs an Epic
account sign-in. With the owner's approval the slice was built on Godot 4.7.2
instead. The K230/DOORS repository was only read, for Relay Nine lore, and was
not modified.

## What works (verified in the running build)

Verification uses the real game through the normal player controller with
scripted inputs (`scripts/test/autopilot.gd`). Results come from the final
regression run (`captures/final/autotest_log.txt`) at 1920×1080, High preset:

| Area | Result |
| --- | --- |
| Boot, level build, navmesh bake | 10 robots spawned, 144 cover points, dock→control path found; 0 script errors |
| Robot perception and squad AI | Player exposed in the hall for 14 s: 8 robots entered COMBAT, 13 SEARCH entries, 28 telegraphed attack windups, cover/flanker/assault roles all used, 924 peek frames. Arcs dealt 599 damage over the whole run (god mode absorbed it) |
| Shooting and damage | Scripted ADS fire: 4 kills, 36/36 hits overall. A capacitor (core) kill triggered the overload |
| Objective chain | Hold-to-connect (2 s) → upload state HACK → reinforcements arrive → upload complete → D6 unseals → EXTRACT → lift → **COMPLETE** |
| ADS alignment | Reflex eye point on the camera axis, error < 0.5 mm |
| Menus | Loadout (attachments applied live), settings, end screen captured |

The test log lists every teleport and the one time skip: the 40 s upload is
forced to 98% to keep the test short. Captures, the clip and the benchmark use
god mode. **No human playtest has been done.** Feel and tuning are untested by
a person.

Systems implemented:

* **Player:** acceleration-based movement, sprint, crouch toggle with ceiling
  check, jump, collision-limited lean, ADS with per-optic zoom and sensitivity,
  recoil you pull against (partial auto-recovery), movement/burst spread,
  footstep noise by stance, interaction, door breach kick, deployable
  ballistic shield, regen after 6 s out of damage.
* **Weapons:** VK-9 carbine (auto/semi) and P-12 sidearm. Procedural viewmodel
  sway, bob, kick spring, sprint pose, wall pull-back, equip/switch, and a
  reload with the magazine physically dropping out (+1 in the chamber on a
  tactical reload, bolt pull when empty). Muzzle flash and light, ejected
  shells, tracers, impact sparks/dust/decals and ricochets.
* **Attachments, all of which change stats:** iron / RD-1 reflex / PX-2 2×
  prism (zoom, aim time, sensitivity, ADS spread); flash hider / SR-5
  suppressor (robots hear shots at ¼ range, −8% damage, less flash and
  recoil); vertical / angled grip (recoil vs aim time); 30 / 45 / 25-round
  coupled mags (capacity vs reload speed and aim).
* **Teslabots:** vision cone with light-dependent range, hearing, alert
  chirps and propagation, investigate/search, attack tokens (max two
  shooters), cover with crouch-and-peek, flanking, door use, a 0.6 s
  telegraphed arc you can dodge by strafing, stagger. Zone damage: blind
  (head), arm (slower and less accurate), limp (legs), capacitor overload
  (chain damage). Sparks and smoke as damage builds, procedural gait, a
  death collapse and a sparking wreck.
* **World:** seven rooms, seven doors (one sealed), crouch-only flank
  passage, four breaker panels that black out rooms (robot sight drops to
  9 m), readable terminals, signage, a slumped deactivated unit, an armory
  case.
* **HUD:** ammo/mode/attachments, health, objective marker with distance,
  prompt and hold progress, upload/jam bar, dynamic crosshair, hit/kill/weak-
  point markers, damage direction, a damage/low-HP vignette shader, FPS.

## Measured performance

The benchmark is a 24 s fly-through of all rooms per preset with live AI
shooting at the player (`captures/final_bench/bench.json`). Machine: Intel Arc
B580, Ryzen 7 9700X, 1920×1080, VSync off.

| Preset | Avg FPS | Avg ms | p95 ms | p99 ms | 1% low FPS |
| --- | --- | --- | --- | --- | --- |
| Low | 274 | 3.65 | 6.3 | 10.4 | 61 |
| Medium | 291 | 3.44 | 5.0 | 8.3 | 57 |
| High | 193 | 5.18 | 6.5 | 8.8 | 69 |
| Ultra | 147 | 6.82 | 8.3 | 10.7 | 58 |

All presets average far above 60 FPS. The 1% lows (57–69 FPS) come from
**first-use shader compilation hitches**, which is also why ADS lags in the
first seconds of a fresh launch. Low is not faster than Medium here because
the GPU is not the bottleneck at this scene size. Earlier runs gave
the same picture (High 197 / Ultra 146 avg).

## Incomplete or known weaknesses

* **Visual fidelity is prototype-grade.** Hard-surface meshes are scripted
  blockouts with bevels. There are no first-person arms or hands, no
  skeletal animation, and the Teslabot is a rigid-part model with
  procedural motion. The lighting mood works, but it is well short of the
  AAA target in the brief.
* Shader compilation stutter on first use (no warm-up pass yet).
* Audio is synthesized. It is functional, but the gunshots lack real
  recorded character. There are no music, VO or reverb zones.
* The AI has not been tuned against a human player. Difficulty, flank
  frequency and the 40 s defense timing are first-pass values. Robots never
  use the crouch passage (by design) and cannot climb.
* No standalone `.exe` export (Godot export templates are not installed). The
  game runs through `Play_BREACH.cmd` with the Godot runtime.
* Cover generation is axis-aligned only, and the deployable shield has no
  placement preview.
* Not run: gamepad, other GPUs/resolutions, long-session memory checks.

## Recommended next steps

1. **Human playtest pass** on feel (recoil, ADS time, robot damage, charge
   time) and the defend phase.
2. Shader warm-up during the briefing screen to remove first-use hitches.
3. Art pass: first-person arms and animated reloads, a sculpted and
   textured Teslabot with baked normal maps, modular kit pieces to replace
   box walls, decals for grime, and recorded or licensed CC0 weapon audio.
4. Install the Godot export templates and produce a standalone Windows build.
5. If Unreal 5 becomes available: the systems above are data- and
   script-driven and map cleanly to UE (Character/Component, BT/EQS for the
   director and cover, Niagara for the FX).

## Evidence

* `captures/final/`: final regression run screenshots plus `autotest_log.txt`
* `captures/showcase/`: robot and weapon close-ups, damage states
* `captures/video2/combat.mp4`: 15 s scripted combat clip from the running
  build (god mode, scripted aim)
* `captures/final_bench/bench.json`: benchmark data
