# BREACH M4.5 - Mission briefing (v0.4.4 -> v0.4.5)

Owner playtest of v0.4.4: graphics, gameplay and weapon audio good; ambience still slightly synthetic (not a priority; untouched here).
This pass adds a pre-mission tactical briefing. Mission objectives, triggers, encounters, checkpoints and saves are unchanged.

Status: **automated checks only.** The briefing has not been human-playtested.

## What the briefing shows

Operation DEADBAND, built from the running mission rather than authored separately:

| Section | Content | Source |
|---|---|---|
| Header | Operation name, classification, live mission clock, status chips (Relay Nine sync, main breakers, control wing, comms) | Mission flags; the existing 02:40 local time |
| Situation | Relay Nine lost sync 41 h ago; units sealed the control wing; breakers open; relay control on battery; night shift left through the crawlway; two technicians missing | The in-world terminal logs (SHIFT LOG, GRID LOG, RELAY 9, PUMP LOG) |
| Primary objective | Upload the override at relay control | Mission flow |
| Tasking | 01 release the lockdown; 02 restore main power (breakers A and B); 03 upload the override (40 s); 04 extract on Freight Lift 2. Grid references are computed from the real object positions | `Mission`, `Expansion` objects |
| Secondary | The 3 ammunition caches; the pump-station steam purge | Existing optional systems |
| Threat assessment | 15 active and 2 dormant units, per area. Telegraphed discharges, weak points, hearing through walls, breaker blackouts. Relay Nine reacts to load changes and the uplink | `Mission.START_SET`; existing mechanics |
| Facility intel | Routes A (corridor), B (shutter, crouch only), C (crawlway, units cannot follow); turbine-hall charge bays; sealed core; armory case | Level layout |
| Tactical map | Plan view of the whole facility (see below) | Level collision geometry |
| Mission progression | Insertion -> 01 + 02 (either order) -> 03 -> 04 | Mission flow |

The core twist (Relay Nine rejecting the override) is not revealed in advance. After it happens, the review adds a "DESTROY RELAY NINE" field-update task.

## Tactical map

`BriefingIntel.plan()` reads the facility from the built level.

**Plan geometry**
- Source: every static `BoxShape3D` collider (109 walls, 80 machinery blocks, 57 low-cover blocks, 3 gallery slabs).
- Added layers:
  - `Game.rooms` for the room areas and names;
  - the live doors (sealed doors in red);
  - the core blast door.
- Display: drawn once per resize. A survey grid (A-H / 1-8, 10 m squares) gives every location a grid reference.

**Overlay** (redrawn every frame)
- Objective markers at the mission objects' positions, insertion, extraction, ammo caches and the steam valve.
- Last-known unit positions from the encounter roster; dormant units drawn hollow.
- Route A from the navmesh, shown with marching dashes; routes B and C are short hand-placed lines through the shutter and the crawlway, which robots cannot path.
- A scan sweep.
- In review mode only: the live operator position and the current objective.

**Interaction**
- Hovering or focusing a task row lights its markers with callouts.
- Hovering a marker lights its row.
- While idle, a spotlight cycles through 01-04.

## Flow and controls

**New mission**
- The briefing replaces the old text panel. The mission stays in BRIEFING with the tree paused.
- DEPLOY (click, or Enter / Space) runs, in order:
  1. button charge (0.7 s);
  2. cut to black;
  3. title card (skippable with any key or click);
  4. the mission begins (`Game.begin_mission()` + `Mission.begin()`, unchanged) and the game fades in;
  5. the HUD returns.
- LOADOUT, SETTINGS and QUIT are reachable from the briefing.

**Checkpoint respawn:** straight back into play, never through the briefing (the `mission.restoring` path is unchanged).

**Restart mission:** this is a new mission, so the briefing shows again. The full reveal plays only once per session; later views fade in quickly.

**Review:** pause -> MISSION BRIEFING.
- Same screen with live task status (COMPLETE / ACTIVE / n/2 / PENDING), updated status chips, unsealed doors and crossed-out completed markers.
- RETURN or Esc goes back to the pause menu.

**Keyboard and mouse**
- Up/Down walk the task and secondary rows to DEPLOY; Left/Right move along the bottom buttons; Tab also cycles (Godot default, not covered by the test).
- Mouse hover and click work everywhere.
- The screen scales from 1280x720 up to 21:9.

## PASS / FAIL

Focused flow test `--autotest --ui_flow --rv_briefing`. It drives the real menus with real mouse and keyboard events on the **exported v0.4.5 validation build** at 1920x1080: **27 checks, 27 PASS, 0 FAIL** (`captures/m45_briefing/briefing_results.txt`).

The two objective completions in phase A are scripted: the panels' own `done` signals are emitted and nobody walks there. This is logged.

| Check | Result |
|---|---|
| Briefing opens on a new mission; mission waits in BRIEFING (paused) | PASS |
| Map built from level geometry (109 walls); markers placed from mission objects; threat estimate = start roster (17) | PASS |
| Hover task 02 highlights the breakers; arrow keys move focus through the tasking (map follows) | PASS |
| LOADOUT opens from the briefing and BACK returns to it | PASS |
| DEPLOY does not start the mission before the cut or during the title card | PASS |
| Gameplay starts after the transition: state INFILTRATE, stage infiltrate, first objective set by the mission, mouse captured | PASS |
| Esc -> pause -> MISSION BRIEFING opens the review; Esc backs out; review shows live progress (lockdown, 1/2 breakers, D5 unsealed); RETURN -> pause | PASS |
| Checkpoint saved -> RESTART FROM CHECKPOINT: no briefing, straight into play, state restored | PASS |
| RESTART MISSION: briefing shown again, checkpoint cleared; Enter deploys | PASS |
| Quick capture at 1280x720 and 2560x1080 (exported build): 5/5 checks each | PASS |

Regression on the existing suites:

| Suite | Result |
|---|---|
| `--m4mission` (project) | Full objective chain to COMPLETE (boarded, checkpoint cleared), 0 script errors: **PASS** |
| `--m4cp` (project) | CHECKPOINT RESTORE PASS, 0 script errors: **PASS** |
| `--m4load` (exported validation build) | Mission load, 0 script errors: **PASS** |

**Not tested**
- A human run through the briefing.
- The briefing's look on other GPUs. It uses Bahnschrift and Consolas from Windows, with Segoe UI / Courier fallbacks.
- No benchmark. The briefing is only shown while the game is paused, and the static map layer is drawn once.

## Screenshots (exported build, in-engine captures)

`captures/m45_briefing/`:

| File | Shows |
|---|---|
| `b01` | Reveal in progress |
| `b02` | Full briefing |
| `b03` | Hover highlight |
| `b04` | Keyboard focus |
| `b05` | Loadout opened from the briefing |
| `b06` | Deploy authorising |
| `b07` | Title card |
| `b08` | In game after deploy |
| `b09` | Review at the start |
| `b10` | Review with progress |
| `b11` | Checkpoint respawn, no briefing |
| `b12` | Restart-mission briefing |
| `b13` | Keyboard deploy |
| `b14` | The briefing at 1280x720 and 2560x1080 |

Logs: `stdout_flow.txt` and `briefing_log_A/B.txt`.

## Files

**New**
- `scripts/ui/briefing.gd`: screen, typography, reveal, deploy transition, review.
- `scripts/ui/tactical_map.gd`: map drawing and interaction.
- `scripts/ui/briefing_intel.gd`: plan and intel from the level and mission.
- `scripts/test/m45_tests.gd`: flow test.

**Changed**
- `scripts/ui/menus.gd`: hosts the briefing; pause button; Esc in review; the old text briefing removed.
- `scripts/main.gd`: `--ui_flow` test start on the normal path. The release path is unchanged apart from a comment.
- `scripts/test/autopilot.gd`: `--rv_briefing` dispatch; no auto-begin under `--ui_flow`.

## Remaining / notes

- The map is a single ground-level plan; galleries are hatched. Breaker B's gallery height (+4.2 m) is given in its callout.
- At 21:9 the extra width goes to the map panel's margins; the plan itself is height-limited.
- Room labels in a few tight spots sit close to markers or walls: the corridor label near the service tunnel, and the pump-station label near a sentry marker. They stay legible.

## Build

- `dist/BREACH_0.4.5/Breach.exe` SHA-256 `b276e8c90d318a754ef913e01d32b1a4defecd6e959d869ed55bdcd9d661497b`, with README.txt, CREDITS.txt (unchanged: no new assets), GODOT_COPYRIGHT.txt and GODOT_LICENSE.txt.
- Unchanged:
  - 0.4.4 `17334e04…`
  - 0.4.3 `9d57c3dc…`
  - 0.4.2 `6f96107e…`
  - all earlier dist folders
- Branch `m43-quality-pass`; master not merged.
