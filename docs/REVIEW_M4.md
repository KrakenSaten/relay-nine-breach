# BREACH M4: pre-playtest quality review (2026-11-23)

* **Scope:** the M4 v0.4.0 build.
* **Method:**
  * An independent read-only code review of progression, checkpoints and doors.
  * Focused in-engine tests (`scripts/test/m4_review.gd`).
  * Capture inspection.
  * Exported-build stability runs.
* **Constraints:** only confirmed bugs were fixed, with balance and mission design unchanged. Tests that had already passed were repeated only where a fix touched them.
* **Builds:** v0.4.0 is kept intact (`dist/BREACH_0.4.0`, SHA-256 unchanged). The fixes are a separate commit and a separate build, **v0.4.1** (`dist/BREACH_0.4.1`).

**Verdict: v0.4.1 is ready for human playtesting.** No softlock is known, and all automated checks pass on the exported build. Use v0.4.1, not v0.4.0: v0.4.0 has two high-severity bugs (items 1 and 2 below).

## Confirmed bugs (all fixed in v0.4.1, commit `b404a0d`)

Each bug was confirmed in-engine or by reading the code before fixing, then re-tested after the fix.

| # | Severity | Bug | Evidence | Fix |
| --- | --- | --- | --- | --- |
| 1 | High | Restoring the **extraction** checkpoint re-ran the core overload three times: 12 search units instead of 3 (32 units instead of 23), triple noise and blackout | `--rv_cpx`: before FAIL (12 x-units), after **PASS** (3) | A silent (restore) capacitor destroy no longer emits; an already-counted stack is ignored |
| 2 | High | A **won mission could turn into "Operator down"**: units could still kill the player in the 1.5 s before the end screen, and the checkpoint was already cleared | Code path confirmed (no state guard on damage) | No damage once COMPLETE |
| 3 | Medium | **D1 swung into the dock forklift and D7 into the corridor wall.** A side effect of the M4 door-direction fix | `--rv_doors`: physics contacts, then clear | Swing limit fitted per door and side at load (D1 85° toward the dock, D7 90° toward the corridor; all others 100°) |
| 4 | Medium | Units **pushed a door back after crossing it**; a head-on pair **deadlocked at D10** (one unit never got through in 16 s) | `--rv_traffic`: D2 1 flip, D10 1/2 arrived → 0 back-push flips; D10 2/2 in 8.4 s | Units only act on a door their path still crosses; an open door can't be flipped again within 2.5 s |
| 5 | Medium | The **blast door leaf parked inside the server-room wall** (z-fighting) instead of on its track | `--rv_blast`: track offset lost when moving, now kept | Rest offset stored, not read back (stale under physics sync) |
| 6 | Low | The **lift call station** showed the reused pump panel's "CW PUMP 2" nameplate | Capture | The plate is covered and re-titled "FREIGHT LIFT 2" |
| 7 | Low | The console completion and the blackout could overwrite the FAILED state for a dead player | Code path confirmed | Both skip for a dead player |
| 8 | Low | The reflection-probe refresh coroutine could resume after a quick restart ("instance is gone" error) | Code path confirmed | Runs through the mission event queue instead |
| 9 | Low | Holding F, looking away and back kept a station's hold progress | Code path confirmed | Refocusing resets the hold |

## Checks with no defect found

| Area | Result |
| --- | --- |
| Objective progression / softlocks | No hard softlock (code review): every station can always be completed. The D3 seal leaves three routes. Restart from checkpoint is offered on death and from the pause menu |
| Interactive objects (panels, breakers, valve, capacitors incl. destroyed variants, parked blast door) | No contact with level geometry (`--rv_doors`) |
| Visual sweep: 25 new views (D8–D11 both sides, galleries, stair tops, breaker B, antechamber, crawl corner/mouths, core rear, destroyed stacks) | No clipping or floating props apart from items 3, 5 and 6 |
| Robots vs locked/sealed doors | No breakthrough. Units chasing a player behind the sealed control wing wait at the doors |
| Crawlway | Units never enter it. They gather at the nearest reachable spot, which can be across a wall: the office corner, or 2 units at the mouths. No damage reached the hidden player |
| Navigation after the fixes | 12/12 routes; mission chain to COMPLETE; checkpoint restore PASS; M3 hunt test (11 room entries) |
| Heavy combat (High, 40 s, complication state, all units alerted, sustained fire) | **130 FPS avg**, p95 12.5 ms, p99 16.2 ms, 1% low 44 FPS, 2 frames >33 ms (60 and 120 ms), 12 kills, debris at its 36-piece cap |
| Release exe v0.4.0 and v0.4.1 | 3 + 2 launch/close cycles. Window responsive in 5–10 s (17.8 s on the first cold-cache launch of the new exe), about 1.53 GB, exit code 0, log 0 errors and 0 warnings |
| Exported v0.4.1 validation build | 7 scene reloads (restart mission and restart from checkpoint alternating) with node count flat (about 5,830), 0 orphan nodes, +66 objects in total. A quit in the middle of the complication exits cleanly. Extraction restore PASS; full mission chain PASS |

## Remaining risks for the playtest

1. **Ammo economy.** 255 rounds in total (rifle 30+150, pistol 15+60), no resupply. There are up to 28 units, and the capacitors need 1,260 damage.
   * A player who fights everything may run low before the core.
   * Recovery exists: *Restart from checkpoint* (also in the pause menu) restores full ammo.
   * Balance is unchanged here; watch for it in the playtest.
2. **Respawn proximity.** The "objectives" checkpoint respawns the player where the second objective was completed.
   * Example: at breaker B, the gallery sentry may be 3 m away if it was still alive.
   * Units get a 3 s grace after a restore.
3. **What a checkpoint does not restore:** room-breaker darkness, which doors were open, unit alert states, and ammo.
4. **Units pathing near a hidden player** stand at the nearest reachable point, which can be on the far side of a wall. This is visible but harmless.
5. **Open door leaves are not in the navmesh.** Units push them aside (rate-limited), so a head-on meeting at a door costs a few seconds.
6. **Rare frame hitches** in heavy combat: 2 in 40 s.
7. **Exit-time messages.**
   * The validation build reports leaked texture RIDs; this existed before M4.
   * Occasionally it also reports resources still in use at exit. This is intermittent, did not reproduce with `--verbose`, and the exit code is 0.
   * The shipped release build's log was clean in every run.
8. **Cosmetic:** after a restore, flickering lights also take the emergency brown-out; in live play they don't.
9. **Not tested here:** balance by a human, other GPUs, and code signing.

## Builds

| Build | Path | SHA-256 |
| --- | --- | --- |
| v0.4.0 (unchanged) | `dist/BREACH_0.4.0/Breach.exe` | `cea9e836c198df8113353cf7a783a61196f43f8ec2f18493fc24e016c03a2c30` |
| **v0.4.1 (playtest this)** | `dist/BREACH_0.4.1/Breach.exe` (582,352,560 bytes) | `59c43f952f66caf6fcf9a849016cc584cd4f683e5bebab4249a980029399f9e4` |

**Evidence** is in `captures/rv_*` (local), including:
* `rv_after/` (fix verification);
* `rv_sweep/` (25 views);
* `rv_fixshots/` (D1, D7, lift panel, parked blast door);
* `rv_reg/` (regression and combat).
