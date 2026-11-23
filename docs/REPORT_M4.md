# BREACH M4: tactical mission expansion (v0.4.0 development candidate, 2026-11-23)

Engine: Godot 4.7.2. Hardware: Arc B580, 1080p. Every image and clip comes from the running game (automated capture harness).
**Nothing in this report is a human playtest.** Results marked "automated" are scripted checks; v0.4.0 has not been played by a person yet.

## 1. New environments

The M1–M3 facility is unchanged except for six new openings. They are joined by five new spaces.

| Area | Size | Character | How it connects |
| --- | --- | --- | --- |
| **Pump Station 2** | 18 × 27 m, 9 m high, two levels | Three cooling pumps (a hard-cover block), a header pipe, a covered water channel, a north gallery with stair, and the **steam purge valve** | Security office (new door D8), service tunnel (D9b), crawlway |
| **Service tunnel S-2** | 12 m | Narrow, piped, a single crate | Corridor north end (D9) ↔ pump station |
| **Maintenance crawlway** | 16 m, 1.25 m clear | Crouch-only duct with caged lamps | Dock west wall ↔ pump station. **Units cannot path through it** (verified) |
| **Switchgear Hall 9-B** | 18 × 28 m, 10 m high | Two 132 kV transformers behind HV cages (landmark), facing switchgear line-ups forming an aisle, an east gallery with stair, **main breakers A (floor) and B (gallery)** | Turbine hall (D10), relay control (D11) |
| **Antechamber + Relay Core** | 20 × 20 m, 12 m high | Blast door B-9, the Relay Nine array on its dais, three caged capacitor stacks, a barrier ring, bus bars | Server room, through the blast door |

* **Existing rooms:**
  * A lockdown panel was added in the security office and a lift call panel in the dock.
  * The control-room breaker moved so that D11 fits.
* **Environmental storytelling:**
  * Log terminals in the pump station and switchgear hall explain the sealed office, the crawlway escape and the opened breakers.
  * The charge-bay units in the turbine hall look decommissioned until Relay Nine wakes them.
* **Art:**
  * Each new room has the same structural rhythm as the old ones: wall ribs, roof I-beams and pipe/cable runs.
  * The new 20-piece kit (`m4_kit.glb`, first-party) supplies the hero props.
  * The 26 new sounds are CC0 recordings layered with synthesis. Sources are in `docs/SOURCES_ENV_M4.md` and `docs/SOURCES_AUDIO_M4.md`.

## 2. Mission flow

1. **Insertion (dock).** Pick a route:
   * the service corridor;
   * the crouch-only shutter into the turbine hall;
   * the crawlway to the pump station.
2. **Infiltration (either order).**
   * **Release the control-wing lockdown** at the security-office panel. This unseals D5, D6 and D11. Relay Nine notices and sends the two nearest roaming units to the office.
   * **Restore main power** by closing breakers A and B. The switchgear hall is held by a posted squad and a gallery sentry. The first breaker draws two roaming units to investigate.
3. **Upload.** Connect the override and defend the console for 40 s. All units converge. Three reinforcements arrive through three different doors: the server room, D11 and D6.
4. **Complication.** Relay Nine rejects the override.
   * Sirens start and emergency lighting takes over: pulsing red beacons, normal lights at 30%.
   * **D3 slams sealed**, cutting the corridor off from the hall.
   * The two "decommissioned" units in charge bays 04/06 **wake and hunt**.
   * The **core blast door opens**, with three units holding posts inside.
5. **Relay core.** Shoot the three capacitor stacks. The staged final overload damages units within 9 m, so it can be used deliberately.
6. **Blackout extraction.**
   * Every room except the dock goes dark: unit sight drops to 9 m, or 18 m on infrared once alerted, and night vision matters.
   * Two search units and a dock guard deploy, and nearby roaming units sweep the player's area.
   * Three ways back:
     * servers → D7 → corridor;
     * servers → D4 → hall → shutter;
     * corridor → tunnel → pump station → crawlway, a stealth route where units cannot follow.
7. **Lift.** Calling the lift is loud. Hold the dock for 25 s while two units assault from the corridor, then board.

**Checkpoints:** after the two infiltration objectives, after the complication ("relay core") and at extraction. Death offers **Restart from checkpoint**, which rebuilds the level in the recorded state, or a full restart.

## 3. Tactical choices

* **Approach:** loud through the corridor, or quiet through the crawlway and pump station, an entrance no unit can follow.
* **Objective order:** lockdown first gives two exits from relay control earlier. Power first avoids alerting the office side.
* **Stealth tools:**
  * The steam purge blinds every unit in the pump hall for about 20 s. Measured: the same unit at 4.9 m spots the player in 2 s without steam and stays unaware with it.
  * Crouching, darkness and room breakers carry over from M3.
* **Positions:**
  * Galleries give overwatch over both new halls, and each has its own sentry.
  * The switchgear aisle and transformer cages form lanes.
  * The core's barrier ring and dais are the cover.
* **Pre-emption:** the dormant units can be destroyed in their bays before the override. Damage wakes them, which is the trade-off.
* **The overload** can be triggered with defenders standing near the core.
* **Extraction:** three routes of different length and risk. D3 is now sealed, so the map has changed since the way in.

## 4. Encounters (no extra HP; unit stats unchanged)

| Group | Units | Behaviour |
| --- | --- | --- |
| M1–M3 garrison | 10 | Patrols, posts (unchanged positions) |
| Pump station | 2 | Gallery sentry (leash 3.5 m), floor patrol |
| Switchgear hall | 3 | Defensive squad: two posted at the breakers/aisle (leash 5–6 m), one gallery sentry |
| Charge bays | 2 | Dormant; woken by Relay Nine (or by damage) |
| Upload | 3 | Reinforcements through three different doors |
| Relay core | 3 | Defensive posts around the capacitors |
| Extraction | 3 | Two search units, one dock guard |
| Lift | 2 | Corridor assault on the dock |

* 15 units are active at the start, plus 2 dormant. At most 28 spawn over the whole mission (M3: 16 over a mission about a third as long).
* **New behaviours:**
  * Guard posts with a leash: alerted units fight and search only inside their area.
  * Gallery sentries.
  * Dormant/wake.
  * Steam blinding.
  * Coordinated dispatch: objectives draw the nearest roaming units.
* **Pathing:**
  * Path-based door opening.
  * Units push a door that is open toward them over to the far side.
* **Doors:** a navmesh blocker layer with runtime rebake keeps sealed and locked doors out of unit paths.

## 5. Verification (automated)

All runs: 0 script errors.

| Test | Result |
| --- | --- |
| `--m4nav`: test units physically drive every new route (doors, stairs, galleries, channel, blast door, core) | **12/12 routes traversed**, longest stall 0 s. Crawlway: no unit path. 0 spawn/patrol points off the navmesh |
| `--m4mission`: the full objective chain with real interactions (hold F at the panel, both breakers, the console and the lift; shoot all three capacitor stacks) | **PASS** through COMPLETE. Three logged time skips: upload progress, lift countdown and teleports between objectives |
| `--m4cp`: reach the relay-core checkpoint, die, *Restart from checkpoint* | **PASS**: stage, sealed D3, open blast door, emergency lighting, destroyed capacitor, the exact surviving-unit set (killed units stay dead), kill count, respawn and navmesh restored |
| `--m4ai`: steam / leash / sentry / dormant | **PASS**: steam blinds; leashed unit max 6.0 m from post (leash 6); sentry stays at 4.2 m; dormant unit ignores gunfire noise, then wakes into combat |
| M3 regression (`--autotest`, `--aitest`, `--aitest2`) | **PASS**: weapons, ADS, night vision, settings, 66 windups, roles, 11 room entries, suppression, reload push, overwatch/pusher |
| `--audit` (prop/wall intersections, floating/sunk props, nav routes) | No new intersections apart from deliberate kit tiling. Sealed routes correctly report "blocked" before the lockdown is released |

**Defects found and fixed during M4:**
* **Doors swung toward the user (a sign error since M1).** Players never noticed because the leaf pushed them back, but robots were pinned behind leaves. The breach slam also now hits the far side as designed.
* **Robots stalled at doors and stair feet:** the door probe ray missed at angled approaches, and units stepped onto stairs from the side.
* **Robot frame cost:** animation ran at the 120 Hz physics rate for every unit. It now runs per frame with distance and frustum LOD, and distant non-combat AI ticks at 40 Hz.
* **Stale reflections after lighting changes:** probes now re-capture.
* **A delayed checkpoint could record the wrong stage:** it is now guarded.

## 6. Screenshots and video

* **Curated set:** `captures/m4_report/` (`overview.png` is a contact sheet).
* **Video:** `captures/m4_report/m4_mission_sequence.mp4`, 55 s at 1280×720/60. A scripted sequence: crawlway → steam purge → breaker → upload → complication and blast door → core overload → blackout → lift. Cuts are teleports; three time skips are logged in `captures/m4_video/stdout.txt`.

## 7. Estimated playtime

* **Scripted (measured):** 62 s through the whole chain with teleports and three time skips. This is not a playtime.
* **Movement only (computed):** the shortest objective route is about 240 m; at a cautious 1.5 m/s average that is about 3 min of travel.
* **Estimated first careful playthrough: 15–25 minutes.**
  * About 25 units, 40 s upload, 25 s lift hold, searching, objective order and route choices.
  * The estimate is not measured; it needs a human playtest to confirm.

## 8. Performance (1080p, Arc B580, idle machine)

**Comparable conditions.** Same 24 s fly-through with live AI as the M3 bench, same machine. CPU idle was checked first: no process used more than 0.1 CPU-seconds over 3 s. M4 has 17 units on the map versus 10 in M3, and they all react to the god-mode player passing through. Data: `captures/m4_final_bench/bench.json`.

| Preset | M3 avg FPS | **M4 avg FPS** | M4 p95 | M4 p99 | M4 1% low |
| --- | --- | --- | --- | --- | --- |
| Low | 216 | **153** | 11.5 ms | 15.2 ms | 46 |
| Medium | 200 | **145** | 10.4 ms | 14.3 ms | 53 |
| High | 152 | **125** | 11.1 ms | 14.1 ms | 52 |
| Ultra | 118 | **103** | 12.7 ms | 17.0 ms | 49 |

**New M4 route.** A 45 s fly-through: corridor → tunnel → pump → office → hall → switchgear → control → servers → core. Data: `captures/m4_final_bench_route/bench.json`.

| Preset | avg FPS | p95 | p99 | 1% low |
| --- | --- | --- | --- | --- |
| Low | 196 | 9.4 ms | 12.5 ms | 65 |
| Medium | 169 | 9.9 ms | 13.8 ms | 57 |
| High | **136** | 10.4 ms | 12.7 ms | 61 |
| Ultra | 111 | 11.8 ms | 16.9 ms | 44 |

**Attribution** (same path, attribution flags on the bench):

| Configuration | Low FPS | High FPS |
| --- | --- | --- |
| No units | 345 | 155 |
| Units frozen (drawn, not processed) | 330 | 150 |
| Only the 10 M3 units | **222** (M3: 216) | 137 |
| All 17 units, before optimisation | 117 | 123 |
| All 17 units, final | 153 | 125 |

* **Rendering the robots is cheap. Processing them is not.** Per unit, the cost equals M3: the M3 unit set reproduces M3's Low result.
* **The M4 drop has two causes:**
  * seven more active units;
  * a larger level, about 0.7 ms on High.
* **Optimisations:**
  * Robot animation runs per rendered frame, with distance and frustum LOD and a 120 Hz cap.
  * Idle units skip the collision sweep.
  * Separation and door probes are throttled.
  * Distant patrols tick at 40 Hz.
* **Worst case:** 15 units converging within 25 m of the player. It was 72–83 FPS on High and is now 90–102.
* **Lighting states:** emergency lighting and the blackout cost nothing measurable (within ±10 FPS of normal in fixed views).

**FPS discrepancy from M3.1.** It was 80 vs 151 FPS, attributed at the time to machine load.
* **Not reproduced.** Under comparable conditions (idle machine, same path), the M3 unit set gives the M3 numbers.
* The remaining M4 difference is explained and measured above.

**Target:** at least 100 FPS average on High. **Met:** 125 on the M3 path and 136 on the M4 route.

## 9. Remaining limitations

* **Not human-playtested.** Encounter pressure, the 40 s upload, the 25 s lift hold, capacitor HP (420) and unit counts are design values, untested by a player.
* **Open door leaves** are not part of the navmesh. Units push them aside, but can brush a leaf.
* **Checkpoint restore** keeps which units are alive and where they were, but not their alert state: restored units start on patrol or post, while hunters resume hunting.
* **The relay dais is an obstacle** (insulator stacks and the maintenance ring), not a walkable platform.
* **Auto exposure** partly compensates the blackout. Night vision is helpful there, not mandatory.
* **Audio:** the siren and the transformer hum are synthesized because no suitable CC0 recordings were found. All new audio was judged by measurement, not by ear.
* **Frame rate under load:** heavy convergence (15+ units within 25 m) runs at about 90–100 FPS on High.
* **Not code-signed; one test machine.**

## 10. Build

| Item | Value |
| --- | --- |
| Executable | `C:\AAA\Breach\dist\BREACH_0.4.0\Breach.exe` (Windows x64, release template, data embedded) |
| Size | 582,351,280 bytes (555.4 MiB); folder adds README, CREDITS (v0.3.1 credits + M4 sources) and the Godot licence files |
| SHA-256 | `cea9e836c198df8113353cf7a783a61196f43f8ec2f18493fc24e016c03a2c30` |
| Version info | 0.4.0.0, "tactical FPS (M4 tactical mission expansion, development candidate)" |
| Earlier builds | `dist/BREACH` (0.2.0), `dist/BREACH_0.3.0` and `dist/BREACH_0.3.1` untouched (0.3.1 hash unchanged: `a6cc06bc...`) |

**Validation of the exported binaries** (copies run from a folder outside the project):

| Check | Result |
| --- | --- |
| Release exe, no arguments | **PASS.** Responding, title "Relay Nine: BREACH", about 1.58 GB working set at the briefing, graceful close with exit code 0, log 0 errors / 0 warnings |
| Validation exe `--m4mission` | **PASS**, full chain to COMPLETE |
| Validation exe `--m4cp` | **PASS**: death, restart from checkpoint, restored state matches |
| Package content | **PASS.** The release has no test harness, captures or staging; the mission script, M4 kit and M4 audio are present |

**Rebuild:**

```powershell
& C:\AAA	ools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path C:\AAA\Breach --export-release "Windows Release" dist/BREACH_0.4.0/Breach.exe
```
