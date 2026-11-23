# BREACH v0.4.2: tactical ammunition resupply (2026-11-23)

* **Problem:** the owner repeatedly ran dry. The player carries 255 rounds and had no resupply, against up to 28 units and 1,260 HP of capacitor stacks.
* **Change:** three limited ammunition caches along the mission route.
* **Unchanged:** starting ammo, weapon handling, unit stats, robot drops (none) and mission flow.

## Supply points

| Cache | Location | Stock (rifle / pistol) | Why there |
| --- | --- | --- | --- |
| Security ammo cache | Security office, north wall (1.7, -12.4), beside the lockdown panel | **60 / 30** | Objective 1 (lockdown); after clearing the office garrison |
| Switchgear ammo cache | Switchgear hall, south wall (36.2, -2.6), near breaker A | **60 / 15** | Objective 2 (power); the defended hall |
| Control ammo cache | Relay control, south wall (23.2, -26.6) | **90 / 30** | Upload defence, and the last stop before the relay core |

* **Total extra:** +210 rifle and +75 pistol, against a start of 180 and 75.
* **Tuning:**
  * Cache stock: `Expansion.CACHE_STOCK` in `scripts/level/expansion.gd`.
  * Restore floor: `Mission.RESTORE_MIN_RIFLE` / `RESTORE_MIN_PISTOL` in `scripts/core/mission.gd`.

## Rules

* **Interaction:** hold **F** for 1 s, the same hold-to-use pattern as the panels and breakers. Releasing early gives nothing.
* **Carry limit:**
  * The reserve can't exceed the starting reserve: 150 rifle, 60 pistol.
  * A cache gives only what fits; the rest stays in it for later.
* **Finite stock:** a cache never refills. At an empty cache, holding gives nothing.
* **Checkpoints:**
  * A checkpoint records carried ammo and each cache's stock, and restarting restores both. Rounds taken after the save are therefore undone, which prevents farming by dying.
  * A restore never gives less than **90 rifle / 30 pistol** in total (magazine + reserve), so a retry can't start dry.
  * Before v0.4.2, a restore always refilled ammo to full.
* **Feedback:**
  * An "AMMUNITION" stencil on the green case (the same case as the dock armory).
  * A status lamp: green (more than half), amber, red (empty).
  * Three ammo cans on top that disappear as stock runs down.
  * A stock readout ("RIFLE 60 | PISTOL 30" or "EMPTY").
  * The prompt shows the stock, or "AMMUNITION FULL", or "EMPTY".
  * On pickup: a message ("AMMUNITION +60 RIFLE +30 PISTOL"), a magazine sound and a short green flash.
  * A faint green glow, so caches can be found in the blackout.
* **Noise:** using a cache makes a quiet 5 m noise.

## Validation (automated; not a human playtest)

| Check | Editor | Exported v0.4.2 |
| --- | --- | --- |
| Full player takes nothing | OK | OK |
| Low player empties a cache (+60/+30) | OK | OK |
| Empty cache, repeated hold: nothing | OK | OK |
| Carry limit: tops up to 150/60, leaves the rest (control 90/30 → 80/25) | OK | OK |
| At the limit: prompt "AMMUNITION FULL", stock unchanged | OK | OK |
| Rifle-only top-up leaves the pistol stock | OK | OK |
| Hold released at 0.5 s: nothing taken | OK | OK |
| Checkpoint restores cache stock and carried ammo; a post-save pickup is undone | PASS | PASS |
| Restore floor (saved 4+0 / 0+0 → 4+86 / 0+30) | PASS | PASS |
| Caches vs level geometry | No contact | — |
| Robot routes with the caches in the navmesh | 12/12, 0 displaced patrol points | — |
| Full mission chain | COMPLETE | COMPLETE |
| Release exe launch/close ×2 | — | Exit code 0, log clean |

Captures: `captures/m4_ammo/`.

**Builds:**
* `dist/BREACH_0.4.2/Breach.exe`: SHA-256 `6f96107e71a3cab78b53caa1a6b4415e37ae20243f73d4cc340b550caa6d87bd`.
* v0.4.1 and v0.4.0 unchanged.

Final balance tuning is left to the owner's next manual playtest.
