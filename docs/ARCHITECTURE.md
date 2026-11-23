# BREACH — technical architecture (Vertical Slice 0.1)

## Engine decision

The brief preferred Unreal Engine 5. The machine has no Unreal install, no
Epic launcher and no Visual Studio C++ toolchain, and installing Unreal needs
an Epic account sign-in. With the owner's approval the slice is built on
**Godot 4.7.2** (MIT, Forward+ Vulkan renderer). Godot covers what this slice
needs: PBR, SDFGI, SSR/SSAO/SSIL, volumetric fog, clustered lights with soft
shadows, GPU particles, decals, runtime navmesh baking, Jolt-class physics
queries and a fixed-step physics loop.

Hardware during development: Intel Arc B580, Ryzen 7 9700X, 32 GB RAM, Windows 11.

## Project layout

```
project.godot            autoloads, physics tick (120 Hz), layer names
scenes/main.tscn         single root node -> scripts/main.gd
scripts/
  core/settings.gd       input map, graphics presets (Low..Ultra), persistence
  core/matlib.gd         triplanar PBR material library + glTF material remap
  core/sfx.gd            pooled 2D/3D audio, variant selection, loops
  core/game.gd           mission state machine, noise events, rooms/lighting, stats
  fx/fx.gd               pooled sparks/dust/smoke, decals, tracers, lightning, flashes
  player/player.gd       CharacterBody3D controller, lean/crouch/sprint, interaction
  player/weapon.gd       viewmodel, attachments, firing, recoil, reload choreography
  player/weapon_defs.gd  data: weapons, attachment slots and stat modifiers
  ai/teslabot.gd         robot agent: perception, state machine, attacks, damage, animation
  ai/director.gd         squad coordinator: alerts, attack tokens, roles, cover, flanks
  level/level_builder.gd builds "Substation 9-B": geometry, props, lights, signage, spawns
  level/door.gd          hinged doors: open/close, robot use, breach (kick)
  level/breaker.gd       breaker panels: cut a room's lights
  level/relay_console.gd objective: hold-to-connect, defend upload, jamming
  level/deploy_shield.gd deployable ballistic shield
  level/terminal.gd      readable logs; level/armory.gd loadout station
  ui/hud.gd              tactical HUD, vignette shader, damage direction, FPS
  ui/menus.gd            briefing, pause, settings, loadout, end screens
  test/autopilot.gd      automated tests, captures, video, benchmark (--autotest)
tools/
  build_models.py        Blender script: all meshes -> assets/models/*.glb
  synth_audio.py         DSP synthesis: all sounds -> assets/audio/*.wav
```

Autoload order: Settings, MatLib, Sfx, Fx, Game. Everything else is created
by `main.gd`. The level is authored in code (boxes + Blender props), which keeps
the slice diffable and lets the layout, navmesh and cover data be rebuilt from
one source.

## Frame flow

* **Physics (120 Hz):** player movement and weapon logic, robot perception
  (every 0.15 s, staggered), robot decisions (every 0.35 s), steering and
  procedural animation, doors.
* **Process:** HUD, FX timers, light flicker, extraction timer.
* Hit detection is hitscan via `PhysicsDirectSpaceState3D.intersect_ray`.

## Collision layers

| Layer | Use |
| --- | --- |
| 1 world | walls, props, doors, shields, breakers (rays and navmesh source) |
| 2 player | player capsule (robot arcs test it) |
| 3 enemy | robot capsules (movement only) |
| 4 hitbox | robot damage zones (`Area3D`, follow animated bones) |
| 5 interact | reserved |

## Player and weapons

* Movement uses acceleration toward a wish velocity (fast, but not
  instant), with sprint, a crouch toggle (capsule resized, ceiling check),
  jump and landing dip. Lean (Q/E) rolls a pivot at chest height and is
  ray-limited so the camera cannot pass through walls.
* The camera FOV is horizontal (`KEEP_WIDTH`), default 90°. ADS narrows the
  FOV per optic and scales sensitivity to match.
* **Recoil:** each shot adds real aim pitch and a yaw impulse. Recovery
  returns only recoil the player has not already pulled down against. A
  viewmodel kick spring and rotational kick are layered on top. Spread
  combines hip/ADS base, movement, airborne and sustained fire.
* **ADS alignment:** each optic carries an `eye` empty. The weapon is placed
  at `-eye_local`, so the reticle lies exactly on the camera axis (verified
  numerically: error < 0.5 mm).
* **Attachments** (`weapon_defs.gd`) are data. Each one multiplies or
  overrides stats: damage, recoil V/H, ADS time, ADS zoom/sensitivity,
  magazine size, reload time, movement speed, noise radius (used by robot
  hearing) and muzzle flash. The loadout screen and the in-world armory apply
  them live.
* Reload is choreographed: the magazine node detaches, drops and returns.
  Ammo loads at magazine insertion, a tactical reload keeps one in the
  chamber, an empty reload adds a bolt pull, and sprinting early cancels it.

## Teslabot AI

Each `Teslabot` is a `CharacterBody3D` with a `NavigationAgent3D` and a
procedurally animated hierarchy imported from Blender (pelvis, torso, head,
shoulders, elbows, hips, knees, ankles, core, muzzle).

* **Perception:** a 116° vision cone plus a 2.2 m proximity sense, with
  ray line-of-sight to the player's head and chest. Sight range is 26 m in lit
  rooms and 9 m in dark rooms, ×0.35 if the optic is destroyed. Awareness
  builds with distance, stance and peripheral angle, and builds faster once
  the squad is alert. **Hearing** uses `Game.noise`: gunshots (42 m, or
  10.5 m suppressed), breaches (28 m), sprint steps (12 m), walking steps
  (5 m), crouching (1.5 m), doors and arcs.
* **States:** PATROL → SUSPICIOUS → INVESTIGATE → COMBAT → SEARCH, plus
  STAGGER and DEAD.
* **Director:** shares the last-known position, alerts squadmates within
  22 m (with an audible chirp) and assigns roles (one *flanker*, then a mix
  of *cover* and *assault*). It also hands out **attack tokens**: at most
  two robots can charge or fire at once, so fights stay lethal but readable.
* **Cover:** the level generates cover points around cover props, with a
  peek position past each edge. The director picks points that face the
  threat and actually block line of sight at body height. Robots crouch
  while hiding (hitboxes follow the bones), step out to peek and shoot, then
  return.
* **Attack:** a 0.6 s telegraphed charge (emitter glow, light, crackle,
  charge sound). During the charge, the aim tracks the target with lag, so
  strafing dodges shots. The hitscan arc's error grows with distance, target
  speed, arm damage and blindness. Arcs are blocked by world geometry,
  shields and other robots.
* **Doors:** robots open closed doors along their path. Locked doors stop them.

## Damage model (readable and functional)

| Zone | Multiplier | Consequence |
| --- | --- | --- |
| Head optic | 2.0× | At 70 zone HP it is **blinded**: optic goes dark and sparks, sight ×0.35, aim error up |
| Rear capacitor (core) | 2.7× | Staggers. A kill here **overloads**: area burst damages nearby robots (and the player within 3.5 m) |
| Torso | 1.0× | — |
| Emitter arm | 0.7× | At 85 zone HP: 35% slower charge, worse accuracy |
| Legs | 0.65× | At 90 zone HP: limp, about 45% slower |

Below 50% HP robots spark and smoke from damaged zones, and the eye flickers
when blinded. Heavy hit bursts or door breaches stagger them and cancel charges.

## Level: Substation 9-B

Seven rooms: dock (start and extraction), service corridor, security office,
crouch-only shutter passage (robots cannot path through it, so it is a
player-only flank), turbine hall (9 m high, machinery hard cover), data
centre (rack aisles) and relay control. There are seven doors; D6 stays
sealed until the upload completes. Four breaker panels black out their room,
and three terminals plus signage carry the story. The mission runs:
infiltrate → hold F to connect → defend a 40 s upload against 4
reinforcement waves (any robot within 3 m jams it) → D6 unseals → two units
ambush the dock → extract on the lift (4 s).

The navmesh is baked at load from static colliders (agent radius 0.5 m,
height 2 m). Doors sit outside the nav region, so paths run through doorways.

## Rendering and scalability

`Settings.apply()` maps the presets to concrete features:

| | Low | Medium | High | Ultra |
| --- | --- | --- | --- | --- |
| GI | — | — | SDFGI 16 rays | SDFGI 32 rays + SSIL |
| SSR / SSAO | — / — | — / on | on / on | on (48 steps) / high |
| Fog | depth fog | volumetric | volumetric, filtered | volumetric 64³ |
| AA / scale | FXAA, 77% FSR2 | FXAA | TAA | TAA |
| Shadow atlas | 2048 hard | 4096 | 4096 soft | 8192 soft |

Render scale (50–100%, FSR2), FOV, sensitivity, volume, VSync and the FPS
counter are user settings, saved to `user://settings.cfg`. Lights use
distance fade, and only about a dozen cast shadows.

## Verification tooling

`scripts/test/autopilot.gd` drives the real build through the normal player
controller (scripted inputs and look direction, god mode):

* `--autotest`: captures every area and runs AI combat exposure with
  metrics, scripted engagement and kills, a core overload, then the full
  objective chain (connect, upload, unlock, extract, COMPLETE) and menus.
  Teleports and the one upload time skip are written to the log.
* `--showcase`: robot and weapon close-ups, damage states.
* `--video` with `--write-movie`: a 15 s scripted combat clip.
* `--bench`: a 24 s fly-through with live AI per preset; reports average FPS,
  p95/p99 frame time and 1% lows.
