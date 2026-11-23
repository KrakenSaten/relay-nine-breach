# BREACH M3: animation, immersion and visual quality (2026-11-23)

Engine: Godot 4.7.2. Hardware: Arc B580, 1080p. All images and clips come from the running game (automated capture harness).
**Nothing here is a human playtest.** v0.3.0 is a development candidate.

## 1. Milestones

| Milestone | Status | Commit |
| --- | --- | --- |
| M3.1 Animation foundation (skinned arm rig, robot rig v3, pose library) | done | e9b263a, 99480c0 |
| M3.2 First-person presentation | done | e9b263a, 9391161 |
| M3.3 Teslabot animation | done | a6ed16a, 99480c0 |
| M3.4 Environment art (dock, control room, decals) | done | 9184c20 |
| M3.5 Cinematic effects | done | c2e680b |
| M3.6 Performance and frame pacing | done | 95b1460 |
| M3.7 Polish, validation, v0.3.0 | done | this commit |
| AI refinement (overwatch, navigation) | done | adbc34c, a6ed16a |

## 2. Major improvements

**First person.** Skinned arms replace the rigid segments:
* 40 bones per pair, 24.5k triangles, with forearm twist bones.
* Two-bone IK per arm, with hands placed exactly on the M2 weapon sockets.
* 12 authored finger poses blended per hand: the trigger finger pulls while firing and comes off the trigger when sprinting or reloading; there are a cup, a vertical-grip fist, a magazine grip, a pistol support grip and a pointing hand.
* Elbows and wrists deform cleanly (no segment seams).
* Draw has an ease-out overshoot; the weapon leans into strafes, floats on jumps and dips on landing; recoil roll varies per shot.
* The support hand leaves the weapon to press consoles and doors.
* The reload is timed to 10 new mechanical sounds (release, drop or pouch, seat, charging handle pull and release).
* Aim, recoil values, reload timings and input path are unchanged.

**Teslabot animation (`scripts/ai/bot_anim.gd`).**
* A gait driven by distance travelled, using two-bone leg IK, so the feet plant with no sliding.
* Lateral stepping when strafing, stepping in place when turning, and a walk/run blend with a lower, heavier run.
* Pelvis bob, roll and twist; the torso counter-rotates and leans into acceleration.
* Spring-driven aiming: deliberate while tracking, snapping fast when a charge starts.
* Hit reactions per zone (a leg hit buckles the knee), stagger with knock-back, and a death that topples under gravity around the feet, bounces and settles.
* Footfall dust, scuff, servo and hydraulic sounds.
* **Knee-piston bug fixed:** the rig v3 rams have mount-eye pivots and are re-aimed every frame on their hinge axis. The build checks the full joint ranges.

**Environment.**
* **Dock:** freight-lift rig (the extraction point), 60-slat roll-up door with leveler, a 20 ft container (new cover), a forklift, pallets, a gantry crane, cable runs, hose cabinet and bollards.
* **Control room:** a three-station operator desk with seven live screens, a 6 m mimic board of the 132/33 kV single-line diagram, instrument racks, relay cabinets with visible relays, and a suspended ceiling grid with light tiles drawn as a single MultiMesh.
* **Wear decals across the facility:** 25 generated CC0 decals (oil, tyre marks, cracks with a normal map, grime streaks, puddles, stencils).

**Effects.**
* Capacitor overload: shockwave, smoke column, debris chips, and screen shake near the player.
* Concrete chips that bounce off a level heightfield.
* Procedural muzzle-flash variants.
* Dust motes in the large rooms.
* Gentle eye adaptation (auto exposure) between dark and bright areas.

**Audio.** 51 new CC0-based sounds:
* the reload timeline;
* each gunshot built from a dry shot, a per-room tail and the bolt mechanics;
* draw, holster, ADS rustle and selector;
* heavy robot steps, scuffs, short servos, stagger, armour tear, collapse and a capacitor-overload warning whine;
* dock and control-room ambience.

## 3. AI and navigation fixes (evidence-based)

* **Stuck detector bug, present since M1.** It compared movement per physics frame (1.4 cm at walk speed against a 2 cm threshold), so every walking unit was re-pathed randomly every 1.2 s. It now checks progress over a 0.6 s window.
* **Capsule radius** was 0.42 against a navmesh agent radius of 0.4, so units snagged on rails and props. It is now 0.36. Two story props were moved out of the patrol lane.
* **Overwatch tactic.** It needs every engaged unit to lose sight of the player, which the M2 tests never produced. `--aitest2` isolates a squad and genuinely breaks line of sight: overwatch and pusher roles are assigned within 2.5 s. The trigger is now 1.0 s, and overwatch/pushers hold combat for 8 s.

## 4. Captures

* Fixed-pose M2 vs M3 comparisons: `captures/m2_vs_m3/` (13 pairs, M2 left; `overview.png`).
* First-person combat clip: `captures/m3_video/combat.mp4`.
* Teslabot animation clip: `captures/m3_botvideo/teslabot_animation.mp4` (walk, run, turn, hits, stagger, death).

## 5. Performance (1080p, 24 s fly-through with live AI; `captures/m3_bench/bench.json`)

| Preset | M2 avg FPS | **M3 avg FPS** | M3 p95 | M3 p99 | M3 1% low |
| --- | --- | --- | --- | --- | --- |
| Low | 180 | 216 | 7.9 ms | 12.9 ms | 59 |
| Medium | 181 | 200 | 6.9 ms | 8.5 ms | 75 |
| **High** | 142 | **152** | 7.9 ms | 9.5 ms | 66 |
| Ultra | 128 | 118 | 9.8 ms | 13.0 ms | 47 |

The target was ≥ 100 FPS on High; it averages 152. How the spikes were investigated and fixed:
* Frame-spike attribution showed AI decision cost at the microsecond level, and disabling SDFGI made no difference.
* The cause was armour debris piling up in long fights.
* A shared budget of 36 pieces (no shadows, faster sleep) raised a littered level's 1% low from 30 to 47 FPS.
* The robot model went from 165 to 87 objects.
* All effects are warmed up behind the briefing screen.

## 6. Gameplay regression (automated)

0 script errors in every run (`captures/m3_final`, `m3_ai`, and the exported-build validation run).
* **Mission:** connect → HACK → EXTRACT (D6 unsealed) → lift → COMPLETE.
* **Weapons:** ADS exact; 5–6 kills in scripted engagement; capacitor shot kills and overloads.
* **Teslabots:** 9 units into combat, 64 telegraphed windups, cover/flank/assault roles, peeking.
* **Hunt test:** 7 room entries, units reach the hidden player, suppression reaches 1.0, reload push and overwatch/pusher observed.
* **Night vision:** on, with the battery draining.
* **Settings:** the preset switch reaches the renderer.
* **Startup and exit:** clean (exit code 0) in both exported builds.

## 7. Standalone build

`C:\AAA\Breach\dist\BREACH_0.3.0\Breach.exe`: 575,984,400 bytes. The folder totals 549.5 MiB.
SHA-256 `40d58d583cac8fe805861ea35f8dff9a644061bdeadf54fb3d8bb2a99deb1f85`.

* **Version info:** v0.3.0.0, labelled "development candidate".
* **Release build:** starts, stays responsive (about 1.48 GB RAM) and exits with code 0; 0 log errors.
* **Validation build:** the full automated pass succeeds; 0 log errors.
* **v0.2.0:** untouched in `dist/BREACH/`.
* **Not manually playtested.**

## 8. Remaining limitations

* Finger poses switch by state; there are no hand-keyed reload or draw clips. The reload choreography is IK-driven.
* At the rifle's hip offset the support arm is longer than its reach. The shoulder slides along the clavicle line (off-screen) to compensate.
* Robot locomotion is procedural: no hand-authored clips, and no IK against uneven ground (the floors are flat).
* The robot is 87 objects; the target of ≤ 70 needs merges across joints.
* Ultra 1% lows (47) are still short spikes in heavy combat.
* The new CC0 sounds have only been judged by measurement, not by ear.
* The exe is not code-signed.

## 9. Recommended next milestone

**M4: Human playtest and content.** A playtest-driven tuning pass (AI pressure, the reload feel, audio mix). Hand-keyed first-person clips (inspect, melee, door-kick), blended over the IK. A second, shorter mission area, reusing the kits, to test pacing beyond one level.
