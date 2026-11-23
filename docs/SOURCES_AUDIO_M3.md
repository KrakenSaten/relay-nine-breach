# BREACH audio M3 (staging/audio_m3) - sources and processing

Rebuild: `python -I tools/m2/audio_m3.py` (uses the CC0 downloads already in staging/audio/raw/; no new downloads were needed).
All recordings are CC0 1.0 (licence verified on each asset's OpenGameArt page, stored in raw/<id>/SOURCE.json). Everything else is synthesized, first-party work of this project.

Format: 16-bit PCM WAV, 48 kHz; mono for all positional sounds, stereo only for ambience_* loops.
Summary: 51 outputs use CC0 recordings (3 edited recordings only, 48 layered with synthesis); 0 are fully synthesized.

Loudness: one-shots follow the same short-term loudness hierarchy as M2 (max 100 ms RMS): weapon mechanics -19..-27, cloth_raise -31, rifle_mech -21 (meant to sit under a shot), shot_distant -22, robot_collapse -13, robot_step_heavy -14.5, robot_stagger/armor_break -15, robot_capacitor_whine -18, robot servos/hiss/scuff -22/-23. shot_tail_small -18.5 and shot_tail_hall -16.5, i.e. 8 / 6 dB under rifle_shot_dry_* (play both at 0 dB). rifle_shot_dry_* / pistol_shot_dry_* are optional extras matching rifle_shot_* / pistol_shot_* levels. Ambience loops sit at about -31 dBFS mean like the M2 beds and are checked for a seamless end-to-start join.

## Source assets

| id (raw/ dir) | asset | author | licence | page |
|---|---|---|---|---|
| oga_100_metal_wood_rubberduck | 100 CC0 metal and wood SFX | rubberduck | CC0 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx |
| oga_100_sfx2_rubberduck | 100 CC0 SFX #2 | rubberduck | CC0 | https://opengameart.org/content/100-cc0-sfx-2 |
| oga_75_breaking_rubberduck | 75 CC0 breaking / falling / hit sfx | rubberduck | CC0 | https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx |
| oga_airvent_loop | Airvent Loop | Longor | CC0 | https://opengameart.org/content/airvent-loop |
| oga_circuit_breaker | SFX - Circuit breaker | CleytonKauffman | CC0 | https://opengameart.org/content/sfx-circuit-breaker |
| oga_creaky_hinge | Creaky Door Hinge Spooky | w.forster.1 (OpenGameArt user) | CC0 | https://opengameart.org/content/creaky-door-hinge-spooky |
| oga_electricity_bmaczero | Electricity Sound Effects | BMacZero | CC0 | https://opengameart.org/content/electricity-sound-effects-0 |
| oga_fan_loop_qubodup | (defect) motor loop | qubodup | CC0 | https://opengameart.org/content/defect-motor-loop |
| oga_free_firearm_sound_library | The Free Firearm Sound Library | Ben Jaszczak, et al. (Submitted by bart) | CC0 | https://opengameart.org/content/the-free-firearm-sound-library |
| oga_gun_reload_bmaczero | Gun Reload Sound Effects | BMacZero | CC0 | https://opengameart.org/content/gun-reload-sound-effects |
| oga_handgun_reload_zer0sol | Handgun Reload Sound Effect | zer0_sol | CC0 | https://opengameart.org/content/handgun-reload-sound-effect |
| oga_kenney_rpg | 50 RPG sound effects | Kenney | CC0 | https://opengameart.org/content/50-rpg-sound-effects |
| oga_kenney_ui | 51 UI sound effects (buttons, switches and clicks) | Kenney | CC0 | https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks |
| oga_metal_clangs_bart | Metal clang sounds | bart | CC0 | https://opengameart.org/content/metal-clang-sounds |
| oga_metal_steps_thimras | Metal footsteps on concrete | Thimras | CC0 | https://opengameart.org/content/metal-footsteps-on-concrete |
| oga_shotgun_reload_zer0sol | Shotgun Reload Sound effects | zer0_sol | CC0 | https://opengameart.org/content/shotgun-reload-sound-effects |
| oga_steam_hisses_bart | Steam release sounds | bart | CC0 | https://opengameart.org/content/steam-release-sounds |
| oga_steps_leather_cloth | Footsteps Leather, Cloth, Armor | HaelDB | CC0 (dual-licensed: OGA-BY 3.0 / CC0; used under CC0) | https://opengameart.org/content/footsteps-leather-cloth-armor |
| oga_workshop_bart | 68 Workshop Sounds | bart | CC0 | https://opengameart.org/content/68-workshop-sounds |

## Output files

### ambience_control.wav
- format: 16-bit PCM, 48000 Hz, stereo, 10.00 s; peak -21.0 dBFS, mean -31.1 dBFS, max 100 ms RMS -30.7 dBFS; seam step at P97 of in-file sample steps, edge RMS diff 0.4 dB
- source: "(defect) motor loop" by qubodup, file `fan_interval.wav` - https://opengameart.org/content/defect-motor-loop (download https://opengameart.org/sites/default/files/fan_interval.wav) - licence CC0
- source: "SFX - Circuit breaker" by CleytonKauffman, file `switch on.wav` - https://opengameart.org/content/sfx-circuit-breaker (download https://opengameart.org/sites/default/files/Circuit%20Breaker.zip) - licence CC0
- source: "SFX - Circuit breaker" by CleytonKauffman, file `switch off.wav` - https://opengameart.org/content/sfx-circuit-breaker (download https://opengameart.org/sites/default/files/Circuit%20Breaker.zip) - licence CC0
- source: "51 UI sound effects (buttons, switches and clicks)" by Kenney, file `switch16.wav` - https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks (download https://opengameart.org/sites/default/files/UI_SFX_Set.zip) - licence CC0
- source: "51 UI sound effects (buttons, switches and clicks)" by Kenney, file `switch18.wav` - https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks (download https://opengameart.org/sites/default/files/UI_SFX_Set.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: 10 s seamless stereo loop of a control room: synthesized equipment hum (50 Hz mains harmonics with 100 Hz transformer buzz, slow periodic level drift, faint 2.2 kHz electronics whine), qubodup '(defect) motor loop' GPU-fan recording (CC0, LP 2.5 kHz, low level) as the soft fan, synthesized pink-noise room tone; occasional relay clicks from CleytonKauffman 'SFX - Circuit breaker' switch on/off (CC0) and Kenney '51 UI sound effects' switch16/switch18 (CC0), HP 300 Hz, through a small-room IR; beds crossfaded, events wrapped tail-into-head

### ambience_dock.wav
- format: 16-bit PCM, 48000 Hz, stereo, 12.00 s; peak -18.0 dBFS, mean -32.7 dBFS, max 100 ms RMS -32.6 dBFS; seam step at P93 of in-file sample steps, edge RMS diff 1.6 dB
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_air_01.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- source: "Airvent Loop" by Longor, file `airvent-large-loop.wav` - https://opengameart.org/content/airvent-loop (download https://opengameart.org/sites/default/files/airvent-large-loop.wav) - licence CC0
- source: "Creaky Door Hinge Spooky" by w.forster.1 (OpenGameArt user), file `creaky_door_hinge.wav` - https://opengameart.org/content/creaky-door-hinge-spooky (download https://opengameart.org/sites/default/files/creaky_door_hinge.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: 12 s seamless stereo loop of a large loading bay: synthesized wind through the bay door (band-passed noise with periodic gust curves, resonant whistle, low buffeting; circular filtering), rubberduck '100 CC0 SFX #2' air_01 (CC0, slowed 0.8x, LP 3 kHz) as wind texture bed, Longor 'Airvent Loop' (CC0, LP 1.5 kHz) as ventilation hum with a quiet synthesized 50 Hz mains hum; occasional metal ticks (synthesized modal ticks) and one distant creak (w.forster 'Creaky Door Hinge', CC0, 0.6x, LP 2 kHz) through the 3.5 s industrial-hall IR; beds equal-power crossfaded, events wrapped tail-into-head

### cloth_raise.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.35 s; peak -14.6 dBFS, mean -34.8 dBFS, max 100 ms RMS -31.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth1.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_lth2.ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_cloth3.ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- processing: Kenney RPG Audio 'cloth1' (0.05-0.40 s) layered with HaelDB 'step_lth2' (leather creak, CC0) and 'step_cloth3' (CC0), HP 180 Hz, LP 10 kHz, gentle fades

### pistol_mag_release.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.35 s; peak -5.1 dBFS, mean -29.4 dBFS, max 100 ms RMS -24.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: zer0sol 'Handgun Reload' (CC0) 0.07-0.40 s: magazine release and the magazine sliding out, HP 180 Hz, -3 dB at 350 Hz; synthesized release-button click in front; small-room IR (wet 0.08)

### pistol_mag_seat.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.32 s; peak -2.7 dBFS, mean -25.8 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- processing: zer0sol 'Handgun Reload' (CC0) 0.56-0.92 s: magazine insertion and seat, HP 150 Hz; small-room IR (wet 0.08)

### pistol_shot_dry_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.26 s; peak -1.0 dBFS, mean -17.7 dBFS, max 100 ms RMS -13.6 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: OPTIONAL EXTRA (for use with shot_tail_*): pistol_shot_0 without the baked room tail - same Free Firearm Sound Library chain, 120 ms early-reflection IR (wet 0.28), sub thump, limiter

### pistol_shot_dry_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.26 s; peak -1.0 dBFS, mean -17.6 dBFS, max 100 ms RMS -13.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: OPTIONAL EXTRA (for use with shot_tail_*): pistol_shot_1 without the baked room tail - same Free Firearm Sound Library chain, 120 ms early-reflection IR (wet 0.28), sub thump, limiter

### pistol_shot_dry_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.26 s; peak -1.0 dBFS, mean -17.6 dBFS, max 100 ms RMS -13.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: OPTIONAL EXTRA (for use with shot_tail_*): pistol_shot_2 without the baked room tail - same Free Firearm Sound Library chain, 120 ms early-reflection IR (wet 0.28), sub thump, limiter

### pistol_slide_rack.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.42 s; peak -5.8 dBFS, mean -24.3 dBFS, max 100 ms RMS -20.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- processing: zer0sol 'Handgun Reload' (CC0) 1.00-1.55 s: full slide rack (pull back + release slam) at original speed, HP 120 Hz; small-room IR (wet 0.08)

### rifle_bolt_release.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.41 s; peak -5.5 dBFS, mean -24.0 dBFS, max 100 ms RMS -19.0 dBFS
- source: "Shotgun Reload Sound effects" by zer0_sol, file `ShotgunSounds/Shell in Chamber.mp3` - https://opengameart.org/content/shotgun-reload-sound-effects (download https://opengameart.org/sites/default/files/shotgunsounds.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: zer0sol 'Shotgun Reload' Shell in Chamber (CC0): the action slamming closed (1.02-1.36 s) slowed to 0.92x, HP 100 Hz; synthesized bolt-catch press click 25 ms ahead and a short low slam body (modal 520/1500 Hz); small-room IR (wet 0.1)

### rifle_charge_pull.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.39 s; peak -11.6 dBFS, mean -27.2 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Shotgun Reload Sound effects" by zer0_sol, file `ShotgunSounds/Rack.mp3` - https://opengameart.org/content/shotgun-reload-sound-effects (download https://opengameart.org/sites/default/files/shotgunsounds.zip) - licence CC0
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: zer0sol 'Shotgun Reload' Rack (CC0): the pull-back stroke (0.60-0.78 s) slowed to 0.9x, HP 120 Hz, with the zer0sol handgun slide pull (1.04-1.17 s, 0.85x, LP 7 kHz) layered at -8 dB for the sliding ring; small-room IR (wet 0.08)

### rifle_charge_release.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.27 s; peak -8.8 dBFS, mean -24.3 dBFS, max 100 ms RMS -20.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalLatch.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: zer0sol 'Handgun Reload' slide-release slam (CC0) slowed to 0.8x (bolt carrier running home), HP 100 Hz, LP 8 kHz; Kenney RPG 'metalLatch' (CC0) 45 ms later as the charging handle latching; small-room IR (wet 0.1)

### rifle_mag_drop_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.51 s; peak -5.9 dBFS, mean -29.0 dBFS, max 100 ms RMS -22.0 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_falling_03.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: rubberduck '75 CC0 breaking/falling/hit' bfh1_metal_falling_03.ogg (CC0, small metal object hitting the floor and bouncing), onset-trimmed, pitch 0.95x, HP 120 Hz, 4-pole LP 7 kHz (tames the small-object ring); synthesized low floor-contact thud under the first hit; concrete-room IR (wet 0.12)

### rifle_mag_drop_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.47 s; peak -9.7 dBFS, mean -28.7 dBFS, max 100 ms RMS -22.0 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_falling_04.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: rubberduck '75 CC0 breaking/falling/hit' bfh1_metal_falling_04.ogg (CC0, small metal object hitting the floor and bouncing), onset-trimmed, pitch 1.05x, HP 120 Hz, 4-pole LP 7 kHz (tames the small-object ring); synthesized low floor-contact thud under the first hit; concrete-room IR (wet 0.12)

### rifle_mag_pouch.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.41 s; peak -8.7 dBFS, mean -30.8 dBFS, max 100 ms RMS -27.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/beltHandle2.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth3.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: Kenney RPG Audio 'beltHandle2' (leather + buckle clinks, CC0) and 'cloth3' (first 0.3 s, CC0), HP 150 Hz; synthesized light magazine rattle (two modal clicks); small-room IR (wet 0.06)

### rifle_mag_release.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.22 s; peak -4.1 dBFS, mean -28.4 dBFS, max 100 ms RMS -25.0 dBFS
- source: "Gun Reload Sound Effects" by BMacZero, file `clipload2.wav` - https://opengameart.org/content/gun-reload-sound-effects (download https://opengameart.org/sites/default/files/clipload2.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: BMacZero 'clipload2' (CC0, small latch clicks) slowed to 0.9x, HP 250 Hz; synthesized release-button click (modal) in front and a short polymer/metal friction burst (mag starting to slide); small-room IR (wet 0.08)

### rifle_mag_seat.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.31 s; peak -7.0 dBFS, mean -24.7 dBFS, max 100 ms RMS -20.0 dBFS
- source: "Gun Reload Sound Effects" by BMacZero, file `clipload1.wav` - https://opengameart.org/content/gun-reload-sound-effects (download https://opengameart.org/sites/default/files/clipload1.wav) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalLatch.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: BMacZero 'clipload1' (CC0, magazine/clip seating thunk) as the main hit, Kenney RPG 'metalLatch' (CC0) as the catch click 6 ms later, both HP 120 Hz; synthesized low seat body (modal 380/1050 Hz, short); small-room IR (wet 0.08)

### rifle_mech_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.24 s; peak -3.5 dBFS, mean -24.7 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalClick.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bolt-carrier cycle heard close to the gun: zer0sol 'Handgun Reload' slide-release slam (CC0) slowed to 0.82x as the carrier hitting the buffer, the same slam at 0.95x 42-48 ms later as the carrier returning to battery, Kenney RPG 'metalClick' (CC0) transient; synthesized buffer-spring twang and modal clicks; small-room IR (wet 0.08)

### rifle_mech_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.26 s; peak -6.7 dBFS, mean -25.0 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalClick.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bolt-carrier cycle heard close to the gun: zer0sol 'Handgun Reload' slide-release slam (CC0) slowed to 0.78x as the carrier hitting the buffer, the same slam at 0.90x 42-48 ms later as the carrier returning to battery, Kenney RPG 'metalClick' (CC0) transient; synthesized buffer-spring twang and modal clicks; small-room IR (wet 0.08)

### rifle_mech_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.25 s; peak -5.3 dBFS, mean -24.9 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalClick.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bolt-carrier cycle heard close to the gun: zer0sol 'Handgun Reload' slide-release slam (CC0) slowed to 0.86x as the carrier hitting the buffer, the same slam at 1.00x 42-48 ms later as the carrier returning to battery, Kenney RPG 'metalClick' (CC0) transient; synthesized buffer-spring twang and modal clicks; small-room IR (wet 0.08)

### rifle_shot_dry_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.30 s; peak -1.3 dBFS, mean -14.9 dBFS, max 100 ms RMS -10.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: OPTIONAL EXTRA (for use with shot_tail_*): rifle_shot_0 without the baked room tail - same Free Firearm Sound Library chain, only a 120 ms early-reflection IR (wet 0.3), synthesized sub thump, look-ahead limiter

### rifle_shot_dry_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.30 s; peak -1.1 dBFS, mean -14.9 dBFS, max 100 ms RMS -10.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: OPTIONAL EXTRA (for use with shot_tail_*): rifle_shot_1 without the baked room tail - same Free Firearm Sound Library chain, only a 120 ms early-reflection IR (wet 0.3), synthesized sub thump, look-ahead limiter

### rifle_shot_dry_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.30 s; peak -1.1 dBFS, mean -14.9 dBFS, max 100 ms RMS -10.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AK-47/C_28P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: OPTIONAL EXTRA (for use with shot_tail_*): rifle_shot_2 without the baked room tail - same Free Firearm Sound Library chain, only a 120 ms early-reflection IR (wet 0.3), synthesized sub thump, look-ahead limiter

### robot_armor_break_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.06 s; peak -1.7 dBFS, mean -27.5 dBFS, max 100 ms RMS -19.4 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - scrape5.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_03.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_falling_02.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: plate tearing off: synthesized bolt-shear crack (strong modal click + HP noise) and spark crackle, bart workshop 'scrape5' (CC0) sped up 1.5x as the tear (0.12 s), rubberduck 'metal_sheet_03.ogg' (CC0, sheet-metal bend/wobble, HP 100 Hz) and rubberduck 'bfh1_metal_falling_02.ogg' (CC0) at 0.32 s as the plate hitting the floor; concrete-room IR (wet 0.2)

### robot_armor_break_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.76 s; peak -1.0 dBFS, mean -25.7 dBFS, max 100 ms RMS -19.4 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - scrape5.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_06.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_falling_03.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: plate tearing off: synthesized bolt-shear crack (strong modal click + HP noise) and spark crackle, bart workshop 'scrape5' (CC0) sped up 1.5x as the tear (0.12 s), rubberduck 'metal_sheet_06.ogg' (CC0, sheet-metal bend/wobble, HP 100 Hz) and rubberduck 'bfh1_metal_falling_03.ogg' (CC0) at 0.28 s as the plate hitting the floor; concrete-room IR (wet 0.2)

### robot_armor_break_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.78 s; peak -1.0 dBFS, mean -28.0 dBFS, max 100 ms RMS -19.9 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - scrape5.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_falling_04.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: plate tearing off: synthesized bolt-shear crack (strong modal click + HP noise) and spark crackle, bart workshop 'scrape5' (CC0) sped up 1.5x as the tear (0.12 s), rubberduck 'metal_sheet_01.ogg' (CC0, sheet-metal bend/wobble, HP 100 Hz) and rubberduck 'bfh1_metal_falling_04.ogg' (CC0) at 0.36 s as the plate hitting the floor; concrete-room IR (wet 0.2)

### robot_capacitor_whine.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.20 s; peak -8.3 dBFS, mean -23.3 dBFS, max 100 ms RMS -18.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: synthesized 1.2 s overload: rising capacitor/inverter whine (380 Hz -> 5.3 kHz, beating partials, growing pitch instability), coil overtone, swelling 50 Hz hum, accelerating crackle and arc buzz; BMacZero 'continuousspark.wav' (real Tesla-generator arcs, CC0) repeated and swelling over the last 0.6 s; ends abruptly (8 ms) for the overload burst; small-room IR (wet 0.12)

### robot_collapse_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.50 s; peak -4.7 dBFS, mean -20.7 dBFS, max 100 ms RMS -13.0 dBFS
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_falling_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "Metal clang sounds" by bart, file `clang - Marker #8.wav` - https://opengameart.org/content/metal-clang-sounds (download https://opengameart.org/sites/default/files/clangs.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: heavy body hitting the floor: rubberduck '100 CC0 metal and wood' metal_falling_01 (CC0, metal crash/clatter, HP 60 Hz) with bart 'Metal clang sounds' Marker #8 (CC0, first 0.8 s, slowed 0.7x) under the first hit; synthesized impacts (sub thumps 95->28 Hz, low-passed impact noise, plate modes) at 0.00 and 0.30 s, settling debris ticks; concrete-room IR (wet 0.3)

### robot_collapse_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.48 s; peak -3.5 dBFS, mean -19.6 dBFS, max 100 ms RMS -13.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - loud clatter.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- source: "Metal clang sounds" by bart, file `clang - Marker #8.wav` - https://opengameart.org/content/metal-clang-sounds (download https://opengameart.org/sites/default/files/clangs.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: heavy body hitting the floor: bart '68 Workshop Sounds' 'loud clatter' (CC0, metal crash/clatter, HP 60 Hz) with bart 'Metal clang sounds' Marker #8 (CC0, first 0.8 s, slowed 0.7x) under the first hit; synthesized impacts (sub thumps 95->28 Hz, low-passed impact noise, plate modes) at 0.00 and 0.24 s, settling debris ticks; concrete-room IR (wet 0.3)

### robot_hydraulic_hiss_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.52 s; peak -9.3 dBFS, mean -28.4 dBFS, max 100 ms RMS -23.0 dBFS
- source: "Steam release sounds" by bart, file `steam hisses - Marker #1.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart 'steam hisses' Marker #1 (CC0) 0.50 s segment, HP 500 Hz, sharp attack and exponential release; synthesized valve click at the start; small-room IR (wet 0.08)

### robot_hydraulic_hiss_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.50 s; peak -10.9 dBFS, mean -28.3 dBFS, max 100 ms RMS -23.0 dBFS
- source: "Steam release sounds" by bart, file `steam hisses - Marker #3.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart 'steam hisses' Marker #3 (CC0) 0.65 s segment, HP 500 Hz, sharp attack and exponential release; synthesized valve click at the start; small-room IR (wet 0.08)

### robot_hydraulic_hiss_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.47 s; peak -7.2 dBFS, mean -28.0 dBFS, max 100 ms RMS -23.0 dBFS
- source: "Steam release sounds" by bart, file `steam hisses - Marker #4.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart 'steam hisses' Marker #4 (CC0) 0.45 s segment, HP 500 Hz, sharp attack and exponential release; synthesized valve click at the start; small-room IR (wet 0.08)

### robot_scuff_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.94 s; peak -8.9 dBFS, mean -25.9 dBFS, max 100 ms RMS -22.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - scrape5.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'scrape5' (CC0, metal scraping), 0.42 s of source from 0.90 s slowed to 0.70x (0.6 s) for weight, HP 60 Hz, LP 7 kHz, swell/decay envelope; synthesized low friction rumble (low-passed brown noise) and grit crackle; concrete-room IR (wet 0.12)

### robot_scuff_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.90 s; peak -10.4 dBFS, mean -26.8 dBFS, max 100 ms RMS -22.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - scrape4.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'scrape4' (CC0, metal scraping), 0.39 s of source from 1.00 s slowed to 0.65x (0.6 s) for weight, HP 60 Hz, LP 7 kHz, swell/decay envelope; synthesized low friction rumble (low-passed brown noise) and grit crackle; concrete-room IR (wet 0.12)

### robot_scuff_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.93 s; peak -11.8 dBFS, mean -28.8 dBFS, max 100 ms RMS -22.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - dragging metal.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'dragging metal' (CC0, metal scraping), 0.43 s of source from 3.45 s slowed to 0.72x (0.6 s) for weight, HP 60 Hz, LP 7 kHz, swell/decay envelope; synthesized low friction rumble (low-passed brown noise) and grit crackle; concrete-room IR (wet 0.12)

### robot_servo_short_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.29 s; peak -11.5 dBFS, mean -25.8 dBFS, max 100 ms RMS -23.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill1.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'drill1' (CC0) motor burst slowed to 0.75x, HP 120 Hz, 0.20 s with fast rise/fall; layered with a short synthesized geared-servo whir (harmonic motor tone + gear-mesh band + stop tick)

### robot_servo_short_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.35 s; peak -12.6 dBFS, mean -25.8 dBFS, max 100 ms RMS -23.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill2.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'drill2' (CC0) motor burst slowed to 0.70x, HP 120 Hz, 0.26 s with fast rise/fall; layered with a short synthesized geared-servo whir (harmonic motor tone + gear-mesh band + stop tick)

### robot_servo_short_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.27 s; peak -13.6 dBFS, mean -26.2 dBFS, max 100 ms RMS -23.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill4.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'drill4' (CC0) motor burst slowed to 0.80x, HP 120 Hz, 0.18 s with fast rise/fall; layered with a short synthesized geared-servo whir (harmonic motor tone + gear-mesh band + stop tick)

### robot_servo_short_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.39 s; peak -11.9 dBFS, mean -25.3 dBFS, max 100 ms RMS -23.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill5.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: bart '68 Workshop Sounds' 'drill5' (CC0) motor burst slowed to 0.72x, HP 120 Hz, 0.30 s with fast rise/fall; layered with a short synthesized geared-servo whir (harmonic motor tone + gear-mesh band + stop tick)

### robot_stagger.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.07 s; peak -6.3 dBFS, mean -22.8 dBFS, max 100 ms RMS -15.0 dBFS
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_04.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill2.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: rubberduck '100 CC0 metal and wood' metal_hit_04 (CC0, heavy clank), HP 80 Hz, with a synthesized armour-plate hit underneath; 'servo protest': bart cordless-drill recording (CC0) varispeed-strained (0.48-0.7x with stutter) plus a synthesized low geared servo with grinding AM; sub thump; concrete-room IR (wet 0.18)

### robot_step_heavy_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.62 s; peak -6.0 dBFS, mean -21.7 dBFS, max 100 ms RMS -14.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_05.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #3.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: running footfall: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.58x, HP 40 Hz; synthesized sub thump (125->32 Hz, drive), low-passed impact noise and armour clank (from robot_step), bart 'steam hisses' (CC0) as a short 0.15 s pressure pfft, debris ticks; concrete-room IR (wet 0.16)

### robot_step_heavy_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.64 s; peak -6.3 dBFS, mean -21.8 dBFS, max 100 ms RMS -14.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_10.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #4.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: running footfall: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.61x, HP 40 Hz; synthesized sub thump (125->32 Hz, drive), low-passed impact noise and armour clank (from robot_step), bart 'steam hisses' (CC0) as a short 0.15 s pressure pfft, debris ticks; concrete-room IR (wet 0.16)

### robot_step_heavy_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.62 s; peak -5.3 dBFS, mean -21.6 dBFS, max 100 ms RMS -14.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_15.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #5.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: running footfall: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.60x, HP 40 Hz; synthesized sub thump (125->32 Hz, drive), low-passed impact noise and armour clank (from robot_step), bart 'steam hisses' (CC0) as a short 0.15 s pressure pfft, debris ticks; concrete-room IR (wet 0.16)

### robot_step_heavy_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.67 s; peak -6.9 dBFS, mean -22.0 dBFS, max 100 ms RMS -14.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_20.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #1.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: running footfall: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.63x, HP 40 Hz; synthesized sub thump (125->32 Hz, drive), low-passed impact noise and armour clank (from robot_step), bart 'steam hisses' (CC0) as a short 0.15 s pressure pfft, debris ticks; concrete-room IR (wet 0.16)

### selector_switch.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.20 s; peak -5.2 dBFS, mean -29.1 dBFS, max 100 ms RMS -26.0 dBFS
- source: "51 UI sound effects (buttons, switches and clicks)" by Kenney, file `switch3.wav` - https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks (download https://opengameart.org/sites/default/files/UI_SFX_Set.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: Kenney '51 UI sound effects' switch3 (a real mechanical switch, CC0), HP 400 Hz; synthesized metal detent click (modal 3.9 kHz cluster) 2 ms after the transient; small-room IR (wet 0.06)

### shot_distant_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.60 s; peak -6.0 dBFS, mean -31.8 dBFS, max 100 ms RMS -24.4 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_24P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: Free Firearm Sound Library AR-15 *mid-distance* recording (D_24P, shot 1, CC0) with its natural outdoor echoes, 4-pole LP 1.6 kHz, HP 50 Hz, +3 dB low shelf at 150 Hz, transient softened (compressor), through the synthesized large-hall IR (wet 0.5); 1.6 s with fade-out

### shot_distant_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.60 s; peak -6.0 dBFS, mean -31.9 dBFS, max 100 ms RMS -24.3 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_24P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: Free Firearm Sound Library AR-15 *mid-distance* recording (D_24P, shot 2, CC0) with its natural outdoor echoes, 4-pole LP 1.6 kHz, HP 50 Hz, +3 dB low shelf at 150 Hz, transient softened (compressor), through the synthesized large-hall IR (wet 0.5); 1.6 s with fade-out

### shot_tail_hall.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.50 s; peak -5.0 dBFS, mean -25.4 dBFS, max 100 ms RMS -16.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: wet-only indoor reflection tail: the Free Firearm Sound Library AR-15 near shot chain (same as rifle_shot_0 without its baked tail) convolved with a synthesized large hall IR: 30 ms pre-delay, 20 early reflections over 160 ms plus discrete slap echoes at 85 and 190 ms, 3-band decay T60 1.8/1.5/0.6 s; wet return HP 200 Hz, LP 9 kHz; 1.5 s with a 0.3 s fade; level set relative to rifle_shot_dry_* (play both at 0 dB)

### shot_tail_small.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.90 s; peak -5.7 dBFS, mean -27.1 dBFS, max 100 ms RMS -18.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: wet-only indoor reflection tail: the Free Firearm Sound Library AR-15 near shot chain (same as rifle_shot_0 without its baked tail) convolved with a synthesized small concrete room IR: 18 dense early reflections within 25 ms, 3-band decay T60 0.75/0.7/0.3 s; wet return HP 200 Hz, LP 9 kHz; 0.9 s with a 0.3 s fade; level set relative to rifle_shot_dry_* (play both at 0 dB)

### weapon_draw.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.54 s; peak -5.6 dBFS, mean -29.1 dBFS, max 100 ms RMS -24.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/drawKnife3.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth1.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: Kenney RPG Audio 'drawKnife3' (sheath draw scrape, CC0) slowed to 0.85x and 'cloth1' (first 0.3 s, CC0), HP 150 Hz; zer0sol handgun-reload grip tap (CC0, the slide-release slam at -14 dB, 0.85x) and a synthesized grip rattle at the end; small-room IR (wet 0.08)

### weapon_holster.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.62 s; peak -5.8 dBFS, mean -29.1 dBFS, max 100 ms RMS -25.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth2.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/beltHandle1.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/dropLeather.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py and tools/m2/audio_m3.py)
- processing: Kenney RPG Audio 'cloth2' and 'beltHandle1' (CC0) as the weapon going into the holster/sling, 'dropLeather' (CC0, HP 100 Hz, -6 dB) as the seat thud at the end; small-room IR (wet 0.06)

