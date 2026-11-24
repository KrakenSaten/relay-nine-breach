# BREACH M4.4 - Ambience polish (v0.4.3 -> v0.4.4)

Owner playtest of v0.4.3: graphics good, weapon audio much better, gameplay good, **background ambience slightly hollow**.
This pass changes only the ambience. Weapon audio, graphics and gameplay code are untouched.

Status: **automated checks only.** The change has not been human-playtested; it awaits the owner's listening approval.
Master and the earlier builds are unchanged (see the end of this report).

## What caused the hollow sound

Measured with in-engine Movie Maker recordings (`--rv_ambaudio`: 10 listening spots, 5 s still and a 6 s 360-degree turn each), with each layer muted in turn.

1. **The room beds were heard only as a reverb tail (main cause).**
   - Each room has a looping 3D bed (machinery, air, water) placed inside the room's reverb `Area3D`.
   - In Godot 4.7, a 3D player inside a reverb area that does not override the bus sends **no dry signal**: it goes to the reverb bus only.
   - Our reverb buses run `dry = 0`, so every bed reached the listener purely as Freeverb output.
   - Muting the reverb buses silenced the beds almost exactly as much as muting the beds themselves. At the dock spot: all layers -43.3 dB, reverb muted -46.7, beds muted -47.0.
   - That wet-only path was:
     - **Thin:** the reverb input high-pass removed most of the beds' bass. At the dock, 31-125 Hz was about 20 dB below the bed asset's own balance.
     - **Tube-like:** the predelay feedback and the comb filters left strong comb resonances. Cepstral peaks at the predelay were z 10-23 in the dock, servers and control room, against a noise level of about 4.
2. **Decorrelated, partly phase-inverted bass in the stereo beds.**
   - The beds were built from independently synthesised L/R channels and from time-offset copies of the same recording.
   - Their L/R correlation below 250 Hz was about 0. In `ambience_hall` (-0.23 / -0.38) and `ambience_core` the bass was partly phase-inverted.
   - Real room tone is almost fully coherent at the two ears at those wavelengths.
   - Decorrelated bass gives the phasey "hole in the middle" on headphones and partly cancels on speakers.
   - The global 2D bed (`ambience_facility`, heard everywhere) had the same problem.
3. **Smaller contributors.**
   - **Full-bandwidth bleed:** beds from big rooms carried through the walls at full bandwidth. The pump-room bed was in range in the office and corridor, and the turbine-hall bed in the corridor.
   - **Duplicated loop:** the corridor bed and the global bed are the same loop and started on the same sample.
   - **Point-source panning:** the stereo beds panned hard as one point (up to 7 dB L/R swing while turning).

## What changed

| change | where |
|---|---|
| Room beds skip the reverb zones (`area_mask = 0`): heard dry, with the room acoustics already baked into each bed. Other positional sounds keep the zones. | `scripts/level/level_builder.gd` `_audio_zones` |
| Bass made coherent in all 8 stereo beds. Mid/side, whole loop as one circular FFT (the loop seam stays sample-exact). Each band gets at least the diffuse-field coherence of two points 18 cm apart (1.0 at DC, 0 from about 950 Hz). Band power is kept; nothing changes above about 1 kHz. No new sources. | `tools/m2/audio_m44.py` -> `assets/audio/ambience_*.wav` (originals kept in `staging/audio_m44/orig/`) |
| Beds of other rooms are heard through the wall: -6 dB and a high-shelf from 500 Hz, crossfaded over 0.6 s when the listener changes room (`Game.room_at`). | `level_builder.gd` `_process` |
| Bed panning strength 0.35, so a bed surrounds the listener instead of swinging between ears. | `level_builder.gd` |
| Corridor bed starts half a loop after the global bed (same loop). | `level_builder.gd` |
| Bed volumes rebalanced so each room keeps its v0.4.3 loudness (K-weighted, at the listening spots), now that the beds play dry. | `level_builder.gd` `ROOM_AUDIO` |

## Measured (v0.4.3 -> v0.4.4, in-engine, same spots)

| room | loudness change (LU) | L/R bass coherence 20-60 / 60-120 / 120-250 Hz | body 31-250 Hz vs 500 Hz-2 kHz | comb peak z (about 4 = none) |
|---|---|---|---|---|
| dock | +1.2 | 0.41 / 0.03 / 0.00 -> 1.00 / 0.99 / 0.92 | -4.6 -> +0.5 dB | 19.5 -> 4.0 |
| corridor | +0.3 | 0.24 / 0.06 / 0.02 -> 1.00 / 0.99 / 0.93 | -0.3 -> +3.9 dB | 6.0 -> 4.0 |
| office | -0.6 | 0.21 / -0.09 / 0.02 -> 1.00 / 1.00 / 0.95 | -1.6 -> +4.5 dB | 4.3 -> 8.1 (the 100 Hz ballast buzz itself) |
| turbine hall | +0.3 | 0.54 / 0.01 / -0.05 -> 0.99 / 0.99 / 0.93 | +1.4 -> +6.4 dB | 3.8 -> 4.7 |
| servers | +0.3 | 0.30 / 0.03 / 0.00 -> 1.00 / 0.98 / 0.94 | -0.1 -> +2.6 dB | 22.6 -> 3.3 |
| control | +0.3 | 0.41 / 0.06 / 0.00 -> 1.00 / 1.00 / 0.93 | +0.6 -> +7.0 dB | 10.1 -> 4.0 |
| pump station | -0.8 | 0.05 / -0.13 / 0.02 -> 1.00 / 0.98 / 0.92 | -3.6 -> +4.5 dB | 4.5 -> 4.5 |
| switchgear | +0.2 | 0.31 / -0.04 / 0.14 -> 1.00 / 1.00 / 0.95 | +1.9 -> +7.2 dB | 3.6 -> 3.4 |
| relay core | -0.1 | 0.07 / 0.13 / 0.01 -> 1.00 / 0.99 / 0.93 | +1.9 -> +3.2 dB | 4.1 -> 4.0 |
| tunnel (no bed) | -1.5 (neighbouring beds now muffled) | 0.31 / 0.00 / 0.03 -> 1.00 / 0.99 / 0.93 | -0.2 -> +2.3 dB | 3.4 -> 4.0 |

- L/R level swing during the 360-degree turn: up to 7.2 dB before, 2.2-4.4 dB after.
- Above about 1 kHz the beds stay decorrelated (wide), as a diffuse field is.
- Full numbers: `captures/m44_ambience_compare/metrics.txt`.

**Weapon audio unchanged.**
- The weapon code, assets and the Weapons bus are untouched.
- `--rv_gunaudio` (v0.4.3 final capture vs v0.4.4) matched across all 25 segments: peak, RMS over 400 ms and body ratio. Largest RMS difference 1.1 dB, mean -0.3 dB. That is within the spread of the random shot variants, with no systematic shift.
- Ambience loudness was matched, so the weapon-to-background balance is kept.

## Listening material

`captures/m44_ambience_compare/NN_<room>_v043_then_v044.ogg`, 10 clips, one per room. Each clip plays v0.4.3 (5 s still, then a 6 s turn), 1 s of silence, then the same for v0.4.4. These are in-engine recordings with robots removed. Logs: `capture_log_v043.txt` and `capture_log_v044.txt`.

## Remaining / not changed

- **Other positional sounds, same engine behaviour.** Robot sounds, impacts, door and lift loops, and player foley played through `Sfx.play_local` are also heard only through the reverb bus while inside a reverb zone. I left them unchanged because their current sound was approved in the playtest. If wanted, a separate small pass could send them dry plus reverb (for example, the zones overriding the bus to Master).
- **Godot reverb buses unchanged.** They still have their input high-pass and predelay feedback; this only matters for the sounds above.
- **Room detection is box-based.** Through-wall muffling uses the room boxes: in doorways and box gaps a bed may sound muffled for a moment (0.6 s crossfade).
- **Office buzz now dry.** The office bed is the mono ballast buzz; it is now heard dry and is a little more noticeable.

## Validation (automated)

- **In-engine ambience recordings:** v0.4.3 with each layer muted in turn (4 runs), then v0.4.4 at old and at rebalanced volumes. The v0.4.3 reverb-muted run was cut short by the run timeout after 7 of 10 rooms; that was enough for the diagnosis.
- **Gun-audio recording:** compared with the M4.3 final capture.
- **Exported validation build:** `--m4load` loads the full mission with 0 script errors.
- **Not run:** no benchmark or full mission run. The runtime change is a 9-entry loop per frame plus property changes on 9 players.

## Build

- `dist/BREACH_0.4.4/Breach.exe` SHA-256 `17334e04711cae6edae31c2ec2f1c11cc756b2f6c01e2698602e6aacd0d4dcd1`, with README.txt, CREDITS.txt (unchanged: no new sources), GODOT_COPYRIGHT.txt and GODOT_LICENSE.txt.
- Unchanged:
  - `dist/BREACH_0.4.3/Breach.exe` `9d57c3dc…c37107`
  - `dist/BREACH_0.4.2/Breach.exe` `6f96107e…6d87bd`
  - all earlier dist folders
- Branch `m43-quality-pass`. Master is not merged.
