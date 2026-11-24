# BREACH M4.3: visual and audio quality pass (v0.4.3)

* **Baseline:** v0.4.2 (`dist/BREACH_0.4.2`, kept unchanged). **Result:** v0.4.3 (`dist/BREACH_0.4.3`).
* **Scope:**
  * the weapon audio;
  * a construction and lighting audit of every area of the M4 mission (dock, corridor, office, turbine hall, passage, servers, relay control, pump station, tunnel, crawlway, switchgear hall, antechamber and relay core).
* **Not changed:**
  * enemy health, damage and aggression;
  * weapon damage, timing and handling;
  * ammunition supplies, objectives, encounters and checkpoints;
  * AI hearing distances (`Game.emit_noise` calls are untouched).
* **Verification:**
  * Everything below was measured or rendered in-engine; nothing is a mock-up.
  * "Automated" means a scripted test.
  * The pass has **not been human-playtested yet**: how the new gunfire *feels* still needs the owner's ears.

## 1. Weapon audio

### What was wrong (v0.4.2, measured from an in-engine recording)

| Weapon | Problem |
| --- | --- |
| Suppressed rifle | 33.7 dB RMS in the office, with low-mid body 6.7 dB **below** the mids. This was the "thin" sound. |
| Open rifle and pistol | Spiky transients with little body (body −9.6…−13 dB re mids). Samples about 0.1 s long. |
| Suppressed shots | No room response at all. |
| Room tails | Picked from the M1–M3 rooms only: the pump station, switchgear hall and core used a generic tail. |
| Reverb | The generic room-reverb buses doubled up with the gun tails. |

### What changed

**Layered shots.** Every shot is now built from authored layers on a dedicated `Weapons` bus, which bypasses the generic reverb zones:

1. **Close report.**
   * Rifle: 4 variants.
   * Suppressed rifle: 4 variants. Its own sound, not a filtered copy; a strong low-mid thump with the blast and crack reduced.
   * Pistol: 4 variants.
2. **Mechanical action.** Bolt and slide; more prominent when suppressed, as it is in reality.
3. **Room response**, chosen by room size: duct, small, medium, large or huge, in open and suppressed variants. During sustained fire each new tail is a little lower.
4. **Early reflections.** Rays to walls within 14 m (left, right, behind, ahead, ceiling). Each reflection is delayed by its real path length (2·d/343 s) and played *from the wall's position*, so walls are heard where they are.

**Sources.** All recordings are CC0; the rest is synthesized. Sources and processing are in `docs/SOURCES_AUDIO_M43.md`; rebuild with `tools/m2/audio_m43.py`.

**Code.**
* `scripts/player/weapon.gd` `_shot_audio`.
* `scripts/core/sfx.gd`: weapon and reflection pools, `Weapons` bus.
* The M3 layering is kept as a fallback.

### Measured: same scripted firing at the same spots, v0.4.2 → v0.4.3

From the recordings in `captures/m43_audio_compare/metrics_v042.json` and `metrics_v043.json`:
* RMS = the first 400 ms;
* body = 100–400 Hz relative to 400–2000 Hz.

| Segment | RMS (dB) | Body (dB re mids) | Decay to −30 dB |
| --- | --- | --- | --- |
| Office, rifle single | −26.6 → **−20.1** | −9.6 → **+0.1** | 0.02 → 0.40 s |
| Office, suppressed single | −33.7 → **−26.1** | −6.7 → **+1.0** | — |
| Corridor, rifle single | −27.1 → **−19.4** | −11.4 → **+2.9** | 0.02 → 1.16 s |
| Turbine hall, rifle single | −24.3 → **−19.1** | −10.1 → **+2.4** | 0.02 → >1.6 s |
| Relay core, suppressed burst | −26.0 → **−19.5** | −4.1 → **+1.1** | — |
| Crawlway, rifle single | −23.4 → **−20.1** | −11.5 → **+1.2** | 0.04 → 0.34 s (tight metal duct) |
| Office, pistol single | −29.1 → **−22.2** | −9.7 → **+2.4** | 0.02 → 0.42 s |

**Suppressed vs open rifle.**
* RMS is about **6 dB lower** in every room (5.9–6.6 dB) and the tail about 6.7 dB lower.
* There is less sub (−9 vs −3…−6 dB) and relatively more mechanical detail.
* It stays full-bodied: body +0.6…+2.3 dB.
* No low-pass is applied to it.

**Peaks and limiter.** Single shots peak at −2…−8 dBFS. Bursts reach the master limiter (−1.9 dBFS peak), the same as v0.4.2.

**Comparison clips.** `captures/m43_audio_compare/*.ogg` holds 9 clips. Each plays the v0.4.2 recording, 0.8 s of silence, then v0.4.3:
* office, open and suppressed rifle;
* corridor bursts, open and suppressed;
* turbine hall singles, open and suppressed;
* core rifle burst;
* core pistol;
* crawlway.

## 2. Visual audit: method

1. **Mesh-level geometry audit** (`--rv_geo`, `scripts/test/m43_tests.gd`). It checks five things:
   * vertices of every prop against every structural box (penetration);
   * unsupported items (floating);
   * escaping rays (holes);
   * unshadowed lights reaching another room through a wall (leaks);
   * coplanar faces with different materials (z-fighting).
2. **Wall-mount audit** (`--rv_wallgap`): wall-mounted items whose back does not touch the wall.
3. **Rendered tour** (`--rv_tour`): 42 room and route views, plus 9 close-ups of flagged spots.
   * Captured before and after with identical cameras.
   * Each view waits 2.5 s so auto-exposure settles.
4. **Targeted look-and-pick** (`--rv_look`): renders a spot and names the meshes under chosen pixels. Used to identify every visual finding before fixing it.
5. **Independent inspection.** A separate reviewer looked at all 51 "after" captures with no knowledge of the fixes; see §4.

| Audit counts | v0.4.2 | v0.4.3 |
| --- | --- | --- |
| Floating candidates | 23 | 9: recessed vent grilles and valve stations, verified mounted |
| Light-leak candidates | 47 (highest estimate 8.6) | 7, all low (highest 0.52) |
| Coplanar different-material faces | 371 | 87: hidden wall-to-ceiling edges and turbine-skid undersides |
| Wall-mounted items off their wall | 48 | 37: rib-mounted pipes and ducts, items flush with the wainscot, and the new bracketed lamps; each verified |

Logs are in `captures/m43_audit/`.

## 3. Issues found and fixed

| Area | Problem (v0.4.2) | Fix |
| --- | --- | --- |
| All framed openings | Steel jambs and headers coplanar with the concrete and wainscot ends: z-fighting on every jamb and lintel underside | Jambs 4 mm inside the opening, header 4 mm lower; wainscot ends 2 mm proud |
| All doorways | Hazard floor stripes coplanar with the floor overlays (33 overlapping floor faces; 0 after) | Stripes 1.5 mm higher |
| Door frames | Green wainscot covered the kit frame's hazard trim below 1.15 m | Wainscot stops at the trim |
| Corridor D3 and D7, servers D5 | Door emergency lights mounted on top of the TURBINE HALL, DATA CENTRE and RELAY CONTROL signs | The light moves beside a sign automatically |
| Relay control | Ceiling light tiles 0.45 m off the tile grid: overlapping tiles and bright slits | Fixtures (and their lights) snapped to the grid |
| Relay control | Server racks 16 cm into the wall; wall screen showed the ceiling lamp as a glowing orb | Racks moved; screen made matte |
| Control and office | Terminal screens were bare glowing slabs floating beside the desk monitors | Monitor bezel, neck and foot |
| Turbine hall | Cable trays ran through the T1 exhaust stack and hung 1.8 m below the roof with nothing holding them | Moved clear of the stack; drop rods to the roof |
| Turbine hall | Duct run ended in mid-air at both ends | Run reaches the east wall and turns up through the roof at the west end; drop rods |
| Turbine hall | Clerestory "windows" were flat over-bright slabs, one crossed by a wall rib | Framed wired glass (mullion and transom), dimmer; the south window moved clear of the rib |
| Servers | Trays 0.5 m below the 3.6 m soffit with no support, in segments with 1 m gaps | Raised so the kit rods reach the soffit; continuous runs |
| Switchgear | Trays hung 3 m below the roof with no support | Drop rods |
| Switchgear | Line-up backs read as blank blockout boxes | Rear cubicle doors, handles, plinth, IDs and DANGER plates |
| Switchgear | Emergency beacon floated in mid-air over the aisle | Mounted on top of the line-up |
| Pump station | Header pipe hangers ended in clamps attached to nothing | Wall cantilever channels with knee braces |
| Pump station | Header ends showed the ribbed texture as large slatted discs | Plain blind plates |
| Pump station | Four bulkhead lamps hovered 25–35 cm in front of the walls; one lit the security office through the party wall | Steel arms and wall plates; that lamp moved to z −16.8 |
| Pump station | "PUMP STATION 2" sign hidden behind the pipe rack | Raised above it |
| Everywhere | 15 red emergency beacons hovered 15–45 cm off their walls | Shelf brackets |
| Hall, control, office, cameras | Electrical boxes 11–20 cm off their walls; security cameras 9–33 cm out of their corners; SHIFT LOG and GRID LOG terminals 12 cm off the walls; hall breaker 5 cm off | Moved onto the walls |
| **Light leaks** | Hall high bay lit the corridor through the wall (est. 8.6). Pump high bay lit the crawlway. Corridor lamps lit the hall and office. Dock spot lit the corridor. Red control lamp lit the hall | Shadows enabled on those lights |
| **Light leaks** | Emergency beacons (omni, range 9, unshadowed) lit neighbouring rooms red through walls | Wall beacons are spots aimed into their own room; the corridor ceiling beacons and the antechamber beacon are shadowed |
| Pump and switchgear | Ceiling invisible in a milky haze: volumetric fog energy 1.4 on 9–10 m high bays, unlike the M1–M3 hall | Fog energy 0.45 on the M4 high bays; the light shafts remain |
| Crawlway | Duct walls clipped to near-white | Lamps dimmed (0.2 → 0.04) with flatter fall-off and lower specular; the mouth is lit by dock spill |

**Before/after comparisons.** `captures/m43_compare/`, with every tour view side by side. The close-ups (`detail_*`) show the fixed spots.

## 4. Independent visual inspection

* A separate reviewer was given only the 51 "after" captures and a defect checklist. It returned 25 findings.
* Each finding was checked against the render (crops, pick tests) before acting.
* **Fixed after the inspection:** switchgear line-up backs; pump sign behind pipes; orb on the control wall screen; floating terminal screens; hall duct ends; crawlway over-exposure; slatted pipe-end discs; gapped server trays; door-frame trim under the wainscot.
* **Not defects:**
  * The "conduit" through the dock RELAY NINE sign is a crack in the concrete texture.
  * The "translucent" dock pipes are the pipe couplings at that crack.
  * D5 and D6 are shut because they are lockdown-sealed at mission start.
  * The robot in the turbine hall is a charge-bay display unit.
  * The control light tiles were already fixed: the serrated edge is aliasing.
* **Left** (low impact, listed in §5): rifle silhouette in strongly back-lit spots; a few low-confidence specks.

## 5. Remaining known visual problems

| Item | Notes |
| --- | --- |
| Light spill | Pump east-wall lamp at z −24.5 reaches the service tunnel through a corner (est. 0.52). Passage lamp and antechamber lamp reach the hall and servers a little (est. ≤0.45). |
| Large halls (pump, switchgear) | Still hazier than the M1–M3 hall when looking straight up. Global fog density is unchanged so that combat visibility stays the same. |
| Crawlway | Warm and bright next to the dock mouth: auto-exposure in a small, dark space. |
| Kit textures | Some stretched UVs on a few kit faces: control relay cabinet side, D5 header trim. |
| Pump header blind flanges | Large close up: correct for a 0.5 m header, but they dominate the view from the south-west corner. |
| Ceiling details | Switchgear drop rods are thin and hard to see in the dark roof. |
| Floor decal | One hard-edged decal outline in relay control. |
| First-person rifle | Renders as a dark silhouette when the player stands in shadow facing a bright area. This is weapon lighting, not part of this environment pass. |
| Cable bundles | Some end flat in the open above the dock side of D1 (M2 dressing). |
| Remaining audit counts | The 87 coplanar faces are hidden corners and undersides; none was visible in the tour. |

## 6. Validation

All results are automated (scripted) unless marked otherwise.

| Check | Result |
| --- | --- |
| `--m4nav`: units physically drive every route, including past the changed frames, trays, ducts and beacons | **12/12 routes**; longest stall 0.5 s; 0 spawn or patrol points off the navmesh; crawlway still impassable for units |
| `--rv_doors`: every door at its swing limits vs colliders and props | **No collider contacts.** One visual-AABB touch: D1 against the forklift at 85°. Not related to this pass: neither D1 nor the forklift changed |
| `--rv_crawl` (new): the crouched player drives the crawlway both ways on real collisions | **PASS.** Dock → corner 4.9 s, corner → pump 2.7 s, and back 2.6 s and 4.7 s; no stalls |
| `--m4mission`: full objective chain with real interactions | **PASS** to COMPLETE, in the editor and on the exported validation build (5 exported runs). The hitch pattern (capture and teleport) matches M4. One exported run printed "2 resources still in use at exit" at process exit; it did not reproduce in 4 reruns, including `--verbose` |
| `--m4cp` on the exported build: death, then restart from checkpoint | **PASS** |
| Performance: exported validation builds, same machine, same session | See below |
| Exported release exe, from a folder outside the project, no arguments | **PASS.** Title "Relay Nine: BREACH", responding, 1.56 GB working set at the briefing; clean close with exit code 0; log 0 errors, 0 warnings |
| Geometry audit after the fixes | See §2 |

### Performance

* **Method.** The fly-through benchmark from the M4 report (`--bench`, four presets), on exported validation builds, on the same machine and in the same session.
  * The v0.4.2 numbers come from the original v0.4.2 validation exe, plus two rebuilds from the v0.4.2 commit.
  * Run-to-run spread is large because live units drive the scene: v0.4.3 alone ranged 109–130 FPS on High.
  * Means are shown. Raw data: `captures/m43_bench/`.

| Path | Preset | v0.4.2 avg FPS | v0.4.3 avg FPS | Change |
| --- | --- | --- | --- | --- |
| Default fly-through (1 run each) | Low | 159 | 154 | within noise |
| | Medium | 118 | 117 | within noise |
| | High | 108 | 120 | within noise |
| | Ultra | 96 | 103 | within noise |
| M4 route (3 runs vs 2 runs) | Low | 199 | 187 | **−6 %** |
| | Medium | 166 | 162 | −3 % |
| | High | 130 | 127 | −2 % |
| | Ultra | 107 | 109 | +2 % |

* **Frame times on the M4 route.**
  * p99: v0.4.2 11.1–22.1 ms; v0.4.3 13.1–17.7 ms.
  * 1 % lows: v0.4.2 45–73 FPS; v0.4.3 43–62 FPS.
* **What it costs.** The cost is the shadows that now stop light leaks.
  * The first v0.4.3 build lost 7–10 % on the route.
  * The five newly shadowed omni lights then moved to dual-paraboloid shadows (2 passes instead of 6).
  * The two pump wall lamps were moved instead of shadowed.
* **Not significant:** the new detail meshes, which are not shadow-casting.
* **Build used:** the benchmark build differs from the shipped one only in one lamp's position.

## 7. Builds and files

* **v0.4.3** is in `dist/BREACH_0.4.3/`: Breach.exe, README.txt, CREDITS.txt (with the M4.3 audio sources), and the Godot licence files.
* **v0.4.2** is unchanged: SHA-256 `6f96107e71a3cab78b53caa1a6b4415e37ae20243f73d4cc340b550caa6d87bd`, the same as at release.
* **v0.4.3** `Breach.exe` SHA-256: `9d57c3dc6f7eb84a2f2c568397b41fdc031551124268ec16d8cfd470d6c37107`.
* **Commits** on branch `m43-quality-pass`, on top of v0.4.2:
  * `50c7d62` weapon audio;
  * `f30b4cd` environment construction fixes;
  * `61da8bb` lighting;
  * `0da1ea1` test harness;
  * plus this report, version metadata and the curated captures.
* **Test modes** (validation builds only): `--rv_gunaudio`, `--rv_tour [--tag=]`, `--rv_geo`, `--rv_wallgap`, `--rv_look --views=... [--emergency]` and `--rv_crawl`.
