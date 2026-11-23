# BREACH M2 "Visual Revolution": report (2026-11-23)

Engine: Godot 4.7.2 (Forward+). Hardware: Intel Arc B580, Ryzen 7 9700X, 1080p.
All images below come from the running game, captured by `scripts/test/autopilot.gd`.
Nothing here is a mock-up. In every comparison, **M1 is on the left and M2 on the right**,
from identical camera poses (`captures/m1_vs_m2/`).

## What changed visually

| Area | M1 | M2 |
| --- | --- | --- |
| Weapons | Bevelled boxes | Detailed VK-9 carbine (27.7k tris): M-LOK handguard, rail sections, flip-up BUIS, real bolt, charging handle, trigger and magazine parts. P-12 pistol (10.6k) with a separate slide that locks back on empty, and a tritium-dot sight. All attachments remodelled. |
| First person | Floating gun | Gloved hands and softshell sleeves (hand poses closed onto the real grip cross-sections) placed by two-bone IK on per-weapon hand sockets. Reload with the support hand: magazine out, to the pouch, new magazine seated, charging handle pulled when empty. Bolt and slide cycle on every shot. |
| Teslabot | Orange box humanoid | "WARDEN-pattern" unit (65k tris): layered worn-ochre armour over a dark frame, a forward-set three-lens sensor head, a caged back capacitor with copper coils and ceramic insulators, a finned arc projector, a claw arm, knee rams. Worn-paint shader. **26 armour plates break off** as physics debris when their zone is damaged, exposing modelled internals. The face plate drops when the optic is destroyed. Plates shed on death and overload. |
| Environment | Textured boxes | Modular kit (wall ribs, I-beams, cable trays, pipe bundles, ducts, vents, drains, handrails, door frames with keypads and emergency lights, high-bay and troffer fixtures). Replacement props. 18 CC0 Poly Haven models. 11 new CC0 texture sets (formwork concrete, painted block, rubber tile, epoxy, fabric, leather...). The turbines are rebuilt as horizontal generator sets. Per-room reflection probes. Scorch decals and story props. |
| Audio | Fully synthesized | 80 sounds: 71 built from CC0 recordings (real AR-15, AK and PPQ shots; footsteps, doors, tesla generator, workshop machinery), 9 synthesized. Gunshot variants. Per-room reverb zones (small, hall, servers, dock), room ambience beds, a fluorescent buzz, a master limiter. |

Key comparisons: `captures/m1_vs_m2/c02_corridor.png`, `c03_hall.png`, `c08_robot_front.png`,
`c09_robot_back.png`, `c10_weapon_hip.png`, `c12_reload.png` (overview: `overview.png`).
Gameplay clip: `captures/m2_video/combat.mp4`. It is 15 s of scripted combat (god mode, scripted aim).

## Combat AI improvements (without raising HP or damage)

* **Suppression:** rounds passing within 1.8 m (or hitting) pin a unit. It breaks for cover, cancels an early charge, aims worse, and learns roughly where the fire came from, even through the suppressor. A pinned unit triggers a squadmate flank (fire and maneuver).
* **Coordinated pressure:** windup starts are staggered at least 0.32 s apart, with up to 3 shooters, so the telegraphs stay readable. Reloading is audible (8 m), and units that hear it push. When the player breaks line of sight, the squad plan assigns overwatch plus pushers from different bearings.
* **Cover:** the score now includes protection at crouched head height, spacing from squadmates, and whether the spot is outside the player's current view. Units peek from the side that actually has line of sight.
* **Flanking:** the chosen route is the one least visible from the player's eye (sampled nav path), with a bonus for opening a crossfire.
* **Search and pursuit:** units predict the player's position from the velocity at the last sighting, and each claims a distinct search point (cover spots in the target room first), pausing to scan.
* **Room entry:** units stack on both sides of a doorway, open the door, and enter on crossing lines, with timeouts so they never deadlock.
* **Root-cause fix:** M1's 1.2 m doorways did not connect the navmesh, so **units could not pursue between rooms**. This was a hidden reason M1 felt easy. Doorways are now 1.5 m, and the navmesh uses cell 0.2 with agent radius 0.4.

## Performance (measured, 1080p, 24 s fly-through with live AI shooting)

| Preset | M1 avg FPS | M2 avg FPS | M2 p95 | M2 1% low |
| --- | --- | --- | --- | --- |
| Low | 274 | 180 | 9.3 ms | 58 |
| Medium | 291 | 181 | 8.9 ms | 43 |
| **High** | 193 | **142** | 9.8 ms | 45 |
| Ultra | 147 | 128 | 9.0 ms | 68 |

The target was ≥ 60 FPS on High: High averages 142 and p95 is about 102 FPS. The M2 cost is mainly CPU draw-call volume from the much denser scene. One optimisation pass was done: socket caching, a robot shadow budget, and distance culling of small props, moving High from 120 to about 140 FPS. The 1% lows (43–68) are short spikes from first-use pipeline compiles and debris spawns. A briefing-screen shader warm-up was added, but it does not cover everything.
Raw data: `captures/m2_bench/bench.json`.

## Gameplay regression (automated; not a human playtest)

The final run is `captures/m2_final/autotest_log.txt`, plus `captures/m2_core/` and `captures/m2_ai/`.
Every run had 0 script errors.

| Check | Result |
| --- | --- |
| Mission chain | Connect → upload (HACK) → D6 unseals → EXTRACT → lift → **COMPLETE** |
| Weapon handling | ADS eye alignment exact. Scripted engagement: 5 kills, 61/61 hits, 10 optic hits |
| Attachments | All loadouts mount on the new sockets (showcase captures). Stats are unchanged, data-driven as in M1 |
| Capacitor weak point | A rifle shot from behind kills and overloads the unit (deterministic test) |
| Teslabots | Exposure test: 9 units entered combat, 42 telegraphed windups, cover/flank/assault roles, peeking. Hunt test (player hidden in the office): stack-and-enter, door opened, the hidden player found and hit, reload push triggered. Near-miss fire suppressed a unit to 0.67 |
| Night vision | Works (blacked-out corridor capture) |

## Remaining limitations (honest)

* **Human playtest (owner, 2026-11-23): "All tested OK".** That covers the suggested checks: reloads and hands, shoot-off armour, robots hunting and entering rooms, suppression, the reload push, and night vision. No issues were reported. No detailed difficulty or audio-mix tuning notes have been given yet.
* The overwatch/pusher squad plan is implemented but was not observed in the automated tests. It needs ≥ 2 engaged units with the player hidden for 1.5 s.
* Arms are rigid segments (no skinned elbow), and the gloves are somewhat soft. A small overlap shows on the magazine grab.
* The robot is rigid-part animated: knee rams drift at large bends, and hip armour can clip on extreme strides.
* The dock and control room are less densely dressed than the corridor and hall. Volumetric fog makes the control room murky.
* 1% lows: there are still occasional compile/debris hitches.
* There is still no standalone `.exe` (Godot export templates are not installed).

## Recommended next steps

1. A human playtest of M2: AI pressure, the new audio mix, reload timing.
2. Skinned first-person arms (Blender armature + Godot Skeleton3D) and hand-keyed reload/draw animations.
3. Merge static robot sub-meshes per bone at load to cut draw calls, then raise the robot and prop shadow budget.
4. A dressing pass for the dock and control room, a light-fog tune per room, decals for grime and fluids.
5. Install the export templates and build a standalone Windows `.exe`.
