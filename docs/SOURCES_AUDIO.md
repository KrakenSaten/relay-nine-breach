# BREACH audio (staging/audio) - sources and processing

Rebuild: `python -I tools/m2/audio_fetch.py` (downloads + licence check into staging/audio/raw/<id>/), then `python -I tools/m2/audio_build.py`.
All recordings are CC0 1.0 (licence verified on each asset's own OpenGameArt page; the licence field is re-parsed by audio_fetch.py and stored in raw/<id>/SOURCE.json). Everything else is synthesized (tools/m2/synth_audio_v2.py), first-party work of this project. No CC-BY / CC-BY-SA / unclear material is used.

Format: 16-bit PCM WAV, 48 kHz; mono for all positional sounds, stereo only for ambience_* beds.
Summary: 71 outputs use CC0 recordings (17 edited recordings only, 54 recordings layered with synthesis); 9 are fully synthesized (tools/m2/synth_audio_v2.py).

## Source assets

| id (raw/ dir) | asset | author | licence | page |
|---|---|---|---|---|
| oga_100_metal_wood_rubberduck | 100 CC0 metal and wood SFX | rubberduck | CC0 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx |
| oga_100_sfx2_rubberduck | 100 CC0 SFX #2 | rubberduck | CC0 | https://opengameart.org/content/100-cc0-sfx-2 |
| oga_75_breaking_rubberduck | 75 CC0 breaking / falling / hit sfx | rubberduck | CC0 | https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx |
| oga_airvent_loop | Airvent Loop | Longor | CC0 | https://opengameart.org/content/airvent-loop |
| oga_creaky_hinge | Creaky Door Hinge Spooky | w.forster.1 (OpenGameArt user) | CC0 | https://opengameart.org/content/creaky-door-hinge-spooky |
| oga_door_lock_cough_e | Door Lock Sounds | Cough-E | CC0 | https://opengameart.org/content/door-lock-sounds |
| oga_door_set_qubodup | Door Open, Door Close Set | qubodup | CC0 | https://opengameart.org/content/door-open-door-close-set |
| oga_edev_loop_qubodup | Electronic device loop | qubodup | CC0 | https://opengameart.org/content/electronic-device-loop |
| oga_electricity_bmaczero | Electricity Sound Effects | BMacZero | CC0 | https://opengameart.org/content/electricity-sound-effects-0 |
| oga_equipment_click_lfa | Equipment Click | LFA | CC0 | https://opengameart.org/content/equipment-click |
| oga_fan_loop_qubodup | (defect) motor loop | qubodup | CC0 | https://opengameart.org/content/defect-motor-loop |
| oga_fantozzi_steps | Fantozzi's Footsteps (Grass/Sand & Stone) | Fantozzi (Submitted by qubodup) | CC0 | https://opengameart.org/content/fantozzis-footsteps-grasssand-stone |
| oga_free_firearm_sound_library | The Free Firearm Sound Library | Ben Jaszczak, et al. (Submitted by bart) | CC0 | https://opengameart.org/content/the-free-firearm-sound-library |
| oga_generator_loop | Generator (loop) | YCbCr | CC0 | https://opengameart.org/content/generator-loop |
| oga_handgun_reload_zer0sol | Handgun Reload Sound Effect | zer0_sol | CC0 | https://opengameart.org/content/handgun-reload-sound-effect |
| oga_heartbeat_qubodup | Heartbeat (single sound) | Independent.nu (Submitted by qubodup) | CC0 | https://opengameart.org/content/heartbeat-single-sound |
| oga_kenney_interface | Interface Sounds | Kenney | CC0 | https://opengameart.org/content/interface-sounds |
| oga_kenney_rpg | 50 RPG sound effects | Kenney | CC0 | https://opengameart.org/content/50-rpg-sound-effects |
| oga_metal_steps_thimras | Metal footsteps on concrete | Thimras | CC0 | https://opengameart.org/content/metal-footsteps-on-concrete |
| oga_steam_hisses_bart | Steam release sounds | bart | CC0 | https://opengameart.org/content/steam-release-sounds |
| oga_steps_leather_cloth | Footsteps Leather, Cloth, Armor | HaelDB | CC0 (dual-licensed: OGA-BY 3.0 / CC0; used under CC0) | https://opengameart.org/content/footsteps-leather-cloth-armor |
| oga_workshop_bart | 68 Workshop Sounds | bart | CC0 | https://opengameart.org/content/68-workshop-sounds |

## Loudness and loop checks

Every one-shot is normalised to a peak ceiling and then turned down to a per-family short-term loudness target (max 100 ms RMS, dBFS): rifle -10.5, pistol -12 (peak-limited at -13), tesla_shot -12.5, door_breach -12, robot_death -13.5, robot_step -15.5, robot hits -16, suppressed shots -20/-21, handling -20..-24, impacts -21/-22, footsteps -26/-27, shell tinks -27, ads_in -31, cloth -35; UI ticks/clicks sit at -29..-35 and UI chimes at -21/-22. Variants of a family are matched to the family median. Loops (ambience_*, robot_idle_loop, electric_buzz_loop) have no fades: recorded beds are equal-power crossfaded tail-into-head, synthesized periodic layers use whole cycles over the loop length and circular (steady-state) filtering; the end-to-start sample step is checked to lie inside the normal distribution of in-file steps.

## Searched but not used / not found

- No CC0/PD recordings of suppressed gunshots, rifle charging handles, robot servos/hydraulics, fluorescent-light buzz, klaxons or shell casings were found; these are hybrids of CC0 recordings and synthesis, or fully synthesized.
- OpenGameArt 'Iron Door' and 'Electric Buzz' (themightyglider) and 'Machine shutting down' (Cough-E) were skipped: they are derivatives of Freesound/other recordings whose own licence could not be verified.
- A Wikimedia Commons audio search returned mostly speech/pronunciation files; its few gunshot files were not needed (the CC0 Free Firearm Sound Library is far better) and were not used. Freesound (login) and Kenney.nl (no scriptable download) were not used directly; Kenney packs were taken from Kenney's own CC0 uploads on OpenGameArt.

## Output files

### ads_in.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.30 s; peak -15.4 dBFS, mean -34.5 dBFS, max 100 ms RMS -31.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth4.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Kenney RPG Audio 'cloth4' (short cloth movement, first 0.25 s), HP 200 Hz; synthesized light grip tick at 0.12 s

### ambience_facility.wav
- format: 16-bit PCM, 48000 Hz, stereo, 12.00 s; peak -18.0 dBFS, mean -31.7 dBFS, max 100 ms RMS -31.3 dBFS; seam step at P59 of in-file sample steps, edge RMS diff 1.0 dB
- source: "Airvent Loop" by Longor, file `airvent-large-loop.wav` - https://opengameart.org/content/airvent-loop (download https://opengameart.org/sites/default/files/airvent-large-loop.wav) - licence CC0
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_loop_machine_02.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: 12 s seamless stereo loop: Longor 'Airvent Loop' (CC0) as ventilation bed (decorrelated L/R offsets, LP 5 kHz); rubberduck '100 CC0 SFX #2' loop_machine_02 (CC0) slowed 0.75x, LP 900 Hz, through a synthesized industrial-hall IR as distant machinery; synthesized room tone (filtered noise, 50 Hz hum, 29.5 Hz machine drone, reverberant metal ticks/clanks); all beds equal-power crossfaded tail-into-head

### ambience_hall.wav
- format: 16-bit PCM, 48000 Hz, stereo, 12.00 s; peak -17.0 dBFS, mean -31.1 dBFS, max 100 ms RMS -30.4 dBFS; seam step at P64 of in-file sample steps, edge RMS diff 0.2 dB
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_loop_machine_01.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- source: "Generator (loop)" by YCbCr, file `loop_generator_1.mp3` - https://opengameart.org/content/generator-loop (download https://opengameart.org/sites/default/files/loop_generator_1.mp3) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: 12 s seamless stereo loop: synthesized turbine drone (25 Hz shaft harmonics, 425 Hz blade-pass with 0.25 Hz beating, modulated broadband roar, air) + rubberduck loop_machine_01 (CC0) slowed 0.5x and YCbCr 'Generator (loop)' (CC0) slowed 0.7x, both low-passed and sent through a synthesized 3.5 s industrial-hall IR; distant reverberant clanks; crossfaded loop

### ambience_servers.wav
- format: 16-bit PCM, 48000 Hz, stereo, 10.00 s; peak -18.0 dBFS, mean -31.5 dBFS, max 100 ms RMS -33.2 dBFS; seam step at P86 of in-file sample steps, edge RMS diff 0.3 dB
- source: "(defect) motor loop" by qubodup, file `fan_interval.wav` - https://opengameart.org/content/defect-motor-loop (download https://opengameart.org/sites/default/files/fan_interval.wav) - licence CC0
- source: "Electronic device loop" by qubodup, file `qubodup-edev.flac` - https://opengameart.org/content/electronic-device-loop (download https://opengameart.org/sites/default/files/qubodup-edev.flac) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: 10 s seamless stereo loop: qubodup '(defect) motor loop' GPU-fan recording (CC0, stereo, HP 80 Hz) and qubodup 'Electronic device loop' hard-disk recording (CC0, HP 150 Hz, low level) as beds; synthesized rack fans (5 detuned blade-pass tones), broadband fan noise, 50 Hz electrical hum and HDD ticks; crossfaded loop

### bolt.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.50 s; peak -7.0 dBFS, mean -26.1 dBFS, max 100 ms RMS -20.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: zer0sol 'Handgun Reload' recording, full slide rack (pull + release, 1.0-1.55 s) slowed to 0.86x for a heavier rifle charging handle, HP 100 Hz; synthesized bolt-slam body (modal 560/1650/3100 Hz) under the release transient; small-room IR (wet 0.1)

### door_breach.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.51 s; peak -3.7 dBFS, mean -19.3 dBFS, max 100 ms RMS -12.0 dBFS
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_slam_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "Door Open, Door Close Set" by qubodup, file `qubodup-DoorSet/flac/qubodup-DoorClose04.flac` - https://opengameart.org/content/door-open-door-close-set (download https://opengameart.org/sites/default/files/qubodup-DoorSet.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized kick thump + lock burst (modal clicks) + steel-slab resonance and wall slam; layered with rubberduck CC0 'metal_slam_01' (at 5 ms) and qubodup DoorClose04 (heavy slam, CC0, at 160 ms), both HP 40 Hz; debris ticks; concrete-room IR (wet 0.35)

### door_locked.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.86 s; peak -8.8 dBFS, mean -27.5 dBFS, max 100 ms RMS -23.0 dBFS
- source: "Door Lock Sounds" by Cough-E, file `DoorLockSounds/LockedDoorHandleJiggle.wav` - https://opengameart.org/content/door-lock-sounds (download https://opengameart.org/sites/default/files/DoorLockSounds.zip) - licence CC0
- processing: Cough-E 'Door Lock Sounds' LockedDoorHandleJiggle (CC0), onset-trimmed, HP 100 Hz; small-room IR (wet 0.1)

### door_open.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.00 s; peak -7.2 dBFS, mean -27.7 dBFS, max 100 ms RMS -19.0 dBFS
- source: "Door Open, Door Close Set" by qubodup, file `qubodup-DoorSet/flac/qubodup-DoorOpen03.flac` - https://opengameart.org/content/door-open-door-close-set (download https://opengameart.org/sites/default/files/qubodup-DoorSet.7z) - licence CC0
- source: "Creaky Door Hinge Spooky" by w.forster.1 (OpenGameArt user), file `creaky_door_hinge.wav` - https://opengameart.org/content/creaky-door-hinge-spooky (download https://opengameart.org/sites/default/files/creaky_door_hinge.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: qubodup 'Door Open, Door Close Set' DoorOpen03 (heavy door with squeak, CC0) slowed to 0.85x, HP 40 Hz, +3 dB low shelf at 120 Hz; w.forster 'Creaky Door Hinge' (CC0, 0.6-2.0 s, slowed 0.8x, band-limited) as the hinge creak; concrete-room IR (wet 0.25)

### dry_fire.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.13 s; peak -2.0 dBFS, mean -25.1 dBFS, max 100 ms RMS -24.0 dBFS
- source: "Equipment Click" by LFA, file `equipmentclick.wav` - https://opengameart.org/content/equipment-click (download https://opengameart.org/sites/default/files/equipmentclick.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: LFA 'Equipment Click' (stapler click, 2.26 s onward) as the trigger break, HP 300 Hz; synthesized hammer/striker fall (modal click 2.9 kHz + 760 Hz body) 28 ms later

### electric_buzz_loop.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.00 s; peak -22.0 dBFS, mean -32.5 dBFS, max 100 ms RMS -32.5 dBFS; seam step at P93 of in-file sample steps, edge RMS diff 0.0 dB
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized 2.0 s loop: fluorescent ballast buzz (100 Hz pulse train through resonant band-pass, 100 Hz harmonic series, mains-synchronous noise rasp) - all periodic with whole cycles, so the loop is sample-seamless

### extraction_alarm.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.36 s; peak -10.1 dBFS, mean -21.4 dBFS, max 100 ms RMS -18.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized two-tone industrial klaxon (587/440 Hz detuned saw stacks, horn formant EQ, saturation, slight vibrato), two cycles, concrete-room IR

### foley_cloth_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.45 s; peak -16.7 dBFS, mean -38.3 dBFS, max 100 ms RMS -35.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth1.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- processing: Kenney RPG Audio 'cloth1.ogg' (CC0), HP 150 Hz, LP 9 kHz, 0.45 s max, gentle fades

### foley_cloth_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.45 s; peak -20.5 dBFS, mean -39.5 dBFS, max 100 ms RMS -35.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth3.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- processing: Kenney RPG Audio 'cloth3.ogg' (CC0), HP 150 Hz, LP 9 kHz, 0.45 s max, gentle fades

### foley_cloth_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.45 s; peak -16.0 dBFS, mean -38.9 dBFS, max 100 ms RMS -36.1 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/clothBelt.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- processing: Kenney RPG Audio 'clothBelt.ogg' (CC0), HP 150 Hz, LP 9 kHz, 0.45 s max, gentle fades

### foley_cloth_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.36 s; peak -17.5 dBFS, mean -38.5 dBFS, max 100 ms RMS -35.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth2.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- processing: Kenney RPG Audio 'cloth2.ogg' (CC0), HP 150 Hz, LP 9 kHz, 0.45 s max, gentle fades

### heartbeat.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.90 s; peak -13.6 dBFS, mean -29.2 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Heartbeat (single sound)" by Independent.nu (Submitted by qubodup), file `heartbeat.mp3_.flac` - https://opengameart.org/content/heartbeat-single-sound (download https://opengameart.org/sites/default/files/heartbeat.mp3_.flac) - licence CC0
- processing: Independent.nu 'Heartbeat (single sound)' via qubodup (CC0), 0.1-1.0 s (one lub-dub), LP 400 Hz, HP 25 Hz, fade-out

### hitmarker.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.08 s; peak -3.0 dBFS, mean -24.4 dBFS, max 100 ms RMS -25.4 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: crisp modal click (detuned partial clusters around 4.6 kHz), short metallic 2.9 kHz ping and a high-passed noise tsk, light compression

### hitmarker_kill.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.22 s; peak -3.0 dBFS, mean -25.2 dBFS, max 100 ms RMS -22.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: double modal tick (35 ms apart), ringing 2.35 kHz ping, small thump and noise tsk, light compression

### impact_concrete_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.37 s; peak -5.1 dBFS, mean -27.7 dBFS, max 100 ms RMS -22.0 dBFS
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_stones_01.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized bullet-into-concrete layer (HP noise crack, swept low-passed body, modal debris grains, dust hiss) layered with a rubberduck CC0 stone/rock hit recording (onset-trimmed, HP 150 Hz) as debris; small-room IR (wet 0.1)

### impact_concrete_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.33 s; peak -1.0 dBFS, mean -28.9 dBFS, max 100 ms RMS -23.9 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_rock_hit_01.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized bullet-into-concrete layer (HP noise crack, swept low-passed body, modal debris grains, dust hiss) layered with a rubberduck CC0 stone/rock hit recording (onset-trimmed, HP 150 Hz) as debris; small-room IR (wet 0.1)

### impact_concrete_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.40 s; peak -2.1 dBFS, mean -27.7 dBFS, max 100 ms RMS -22.0 dBFS
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_stones_03.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized bullet-into-concrete layer (HP noise crack, swept low-passed body, modal debris grains, dust hiss) layered with a rubberduck CC0 stone/rock hit recording (onset-trimmed, HP 150 Hz) as debris; small-room IR (wet 0.1)

### impact_metal_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.31 s; peak -3.0 dBFS, mean -25.6 dBFS, max 100 ms RMS -21.1 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_hit_03.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: rubberduck CC0 metal hit recording, onset-trimmed, HP 250 Hz, +3 dB at 4 kHz; layered with a synthesized bullet crack (0.8 ms HP noise) and spark crackle; small-room IR (wet 0.12)

### impact_metal_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.34 s; peak -3.3 dBFS, mean -26.2 dBFS, max 100 ms RMS -21.1 dBFS
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_02.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: rubberduck CC0 metal hit recording, onset-trimmed, HP 250 Hz, +3 dB at 4 kHz; layered with a synthesized bullet crack (0.8 ms HP noise) and spark crackle; small-room IR (wet 0.12)

### impact_metal_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.19 s; peak -3.0 dBFS, mean -27.4 dBFS, max 100 ms RMS -24.6 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_hit_01.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: rubberduck CC0 metal hit recording, onset-trimmed, HP 250 Hz, +3 dB at 4 kHz; layered with a synthesized bullet crack (0.8 ms HP noise) and spark crackle; small-room IR (wet 0.12)

### mag_in.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.34 s; peak -6.0 dBFS, mean -29.7 dBFS, max 100 ms RMS -24.6 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: zer0sol 'Handgun Reload' recording, 0.56-0.98 s (magazine insertion and seat), HP 150 Hz; synthesized low 'seat' resonance (modal 420/1150 Hz) under the main transient; small-room IR (wet 0.08)

### mag_out.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.35 s; peak -2.6 dBFS, mean -28.4 dBFS, max 100 ms RMS -23.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: zer0sol 'Handgun Reload' recording, 0.07-0.45 s (magazine release and drop-out), HP 180 Hz, low-mid cut; synthesized release-button click (modal) layered on the front; small-room IR (wet 0.08)

### pistol_shot_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.71 s; peak -1.0 dBFS, mean -21.3 dBFS, max 100 ms RMS -13.1 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Free Firearm Sound Library (Walther PPQ 9 mm) near-distance shot: direct sound cut at 140 ms (before the outdoor echo), mono, HP 30 Hz; layered with a synthesized crack and faint slide clicks; presence EQ, compression, soft clip; convolved with a synthesized concrete-room IR (wet 0.36, wet return HP 250 Hz); synthesized sub thump (160->58 Hz) added after the reverb; 6 dB into a 1.5 ms look-ahead peak limiter + light soft clip

### pistol_shot_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.79 s; peak -1.0 dBFS, mean -21.7 dBFS, max 100 ms RMS -13.1 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Free Firearm Sound Library (Walther PPQ 9 mm) near-distance shot: direct sound cut at 140 ms (before the outdoor echo), mono, HP 30 Hz; layered with a synthesized crack and faint slide clicks; presence EQ, compression, soft clip; convolved with a synthesized concrete-room IR (wet 0.36, wet return HP 250 Hz); synthesized sub thump (160->58 Hz) added after the reverb; 6 dB into a 1.5 ms look-ahead peak limiter + light soft clip

### pistol_shot_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.78 s; peak -1.1 dBFS, mean -21.7 dBFS, max 100 ms RMS -13.1 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Free Firearm Sound Library (Walther PPQ 9 mm) near-distance shot: direct sound cut at 140 ms (before the outdoor echo), mono, HP 30 Hz; layered with a synthesized crack and faint slide clicks; presence EQ, compression, soft clip; convolved with a synthesized concrete-room IR (wet 0.36, wet return HP 250 Hz); synthesized sub thump (160->58 Hz) added after the reverb; 6 dB into a 1.5 ms look-ahead peak limiter + light soft clip

### pistol_shot_suppressed_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.40 s; peak -4.1 dBFS, mean -27.0 dBFS, max 100 ms RMS -21.0 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Blast removed: the same Free Firearm Sound Library 9 mm shot low-passed at 850 Hz with a 25 ms envelope; synthesized suppressor 'pfft' and slide clicks layered with the real slide slam from the zer0sol handgun reload recording (pitch varied per variant); corridor IR (wet 0.18, return HP 200 Hz)

### pistol_shot_suppressed_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.35 s; peak -4.0 dBFS, mean -31.4 dBFS, max 100 ms RMS -25.9 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Blast removed: the same Free Firearm Sound Library 9 mm shot low-passed at 850 Hz with a 25 ms envelope; synthesized suppressor 'pfft' and slide clicks layered with the real slide slam from the zer0sol handgun reload recording (pitch varied per variant); corridor IR (wet 0.18, return HP 200 Hz)

### pistol_shot_suppressed_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.38 s; peak -4.4 dBFS, mean -26.7 dBFS, max 100 ms RMS -21.0 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Blast removed: the same Free Firearm Sound Library 9 mm shot low-passed at 850 Hz with a 25 ms envelope; synthesized suppressor 'pfft' and slide clicks layered with the real slide slam from the zer0sol handgun reload recording (pitch varied per variant); corridor IR (wet 0.18, return HP 200 Hz)

### pistol_slide.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.22 s; peak -6.8 dBFS, mean -24.5 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect (download https://opengameart.org/sites/default/files/reload.wav) - licence CC0
- processing: zer0sol 'Handgun Reload' recording, slide-release slam (1.17-1.47 s), HP 150 Hz; small-room IR (wet 0.08)

### player_hurt.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.50 s; peak -6.9 dBFS, mean -21.6 dBFS, max 100 ms RMS -16.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: BMacZero 'spark.wav' (CC0) jolt layered with synthesized arc buzz, crackle, body thump (150->48 Hz) and low noise hit; no voice

### ricochet.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.60 s; peak -9.0 dBFS, mean -26.1 dBFS, max 100 ms RMS -20.5 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_hit_06.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: rubberduck CC0 metal hit 'bfh1_metal_hit_06' (onset-trimmed, HP 300 Hz) + synthesized ricochet whine (swept tone + resonant band-passed noise, 5 kHz -> 1.5 kHz); small-room IR

### rifle_shot_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.83 s; peak -1.5 dBFS, mean -19.0 dBFS, max 100 ms RMS -10.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Free Firearm Sound Library near-distance shot (AR-15): direct sound cut at 170 ms (before the outdoor echo), summed to mono, HP 30 Hz; layered with a synthesized transient crack and faint bolt-carrier clicks; +2 dB presence at 2.6 kHz, compression, soft clip; convolved with a synthesized concrete-room IR (exponentially decaying 3-band noise + sparse early reflections, T60 ~0.8 s; wet 0.42, wet return HP 220 Hz); synthesized sub thump (120->50 Hz) added after the reverb; 7 dB into a 1.5 ms look-ahead peak limiter + light soft clip for density

### rifle_shot_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.80 s; peak -1.4 dBFS, mean -18.9 dBFS, max 100 ms RMS -10.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Free Firearm Sound Library near-distance shot (AR-15): direct sound cut at 170 ms (before the outdoor echo), summed to mono, HP 30 Hz; layered with a synthesized transient crack and faint bolt-carrier clicks; +2 dB presence at 2.6 kHz, compression, soft clip; convolved with a synthesized concrete-room IR (exponentially decaying 3-band noise + sparse early reflections, T60 ~0.8 s; wet 0.42, wet return HP 220 Hz); synthesized sub thump (120->50 Hz) added after the reverb; 7 dB into a 1.5 ms look-ahead peak limiter + light soft clip for density

### rifle_shot_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.89 s; peak -1.2 dBFS, mean -19.3 dBFS, max 100 ms RMS -10.5 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AK-47/C_28P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Free Firearm Sound Library near-distance shot (AK-47): direct sound cut at 170 ms (before the outdoor echo), summed to mono, HP 30 Hz; layered with a synthesized transient crack and faint bolt-carrier clicks; +2 dB presence at 2.6 kHz, compression, soft clip; convolved with a synthesized concrete-room IR (exponentially decaying 3-band noise + sparse early reflections, T60 ~0.8 s; wet 0.42, wet return HP 220 Hz); synthesized sub thump (120->50 Hz) added after the reverb; 7 dB into a 1.5 ms look-ahead peak limiter + light soft clip for density

### rifle_shot_suppressed_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.40 s; peak -3.0 dBFS, mean -26.0 dBFS, max 100 ms RMS -20.1 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Blast removed: the same Free Firearm Sound Library shot 4-pole low-passed at 650 Hz with a 30 ms envelope (body only, ~-12 dB); synthesized suppressor 'pfft' (swept noise burst), small sub thump and bolt-carrier clicks (modal resonators) layered with the real slide/bolt slam from the zer0sol handgun reload recording slowed to 0.8x (LP 7 kHz); corridor IR (wet 0.2, return HP 200 Hz)

### rifle_shot_suppressed_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.36 s; peak -3.0 dBFS, mean -28.6 dBFS, max 100 ms RMS -23.1 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Blast removed: the same Free Firearm Sound Library shot 4-pole low-passed at 650 Hz with a 30 ms envelope (body only, ~-12 dB); synthesized suppressor 'pfft' (swept noise burst), small sub thump and bolt-carrier clicks (modal resonators) layered with the real slide/bolt slam from the zer0sol handgun reload recording slowed to 0.8x (LP 7 kHz); corridor IR (wet 0.2, return HP 200 Hz)

### rifle_shot_suppressed_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.42 s; peak -3.8 dBFS, mean -26.2 dBFS, max 100 ms RMS -20.1 dBFS
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart), file `Prepared SFX Library/AK-47/C_28P.wav` - https://opengameart.org/content/the-free-firearm-sound-library (download https://opengameart.org/sites/default/files/Prepared%20SFX%20Library.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Blast removed: the same Free Firearm Sound Library shot 4-pole low-passed at 650 Hz with a 30 ms envelope (body only, ~-12 dB); synthesized suppressor 'pfft' (swept noise burst), small sub thump and bolt-carrier clicks (modal resonators) layered with the real slide/bolt slam from the zer0sol handgun reload recording slowed to 0.8x (LP 7 kHz); corridor IR (wet 0.2, return HP 200 Hz)

### robot_alert.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.34 s; peak -12.7 dBFS, mean -22.4 dBFS, max 100 ms RMS -17.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: three low detuned saw tones (233 Hz, 165 Hz tritone drop, then 220->150 Hz bend) ring-modulated at 31 Hz with a sub-octave, formant EQ and saturation; concrete-room IR

### robot_death.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.80 s; peak -2.7 dBFS, mean -19.7 dBFS, max 100 ms RMS -13.5 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_falling_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized power-down whine (1.2 kHz -> 45 Hz), arc buzz and crackle, layered with BMacZero 'continuousspark.wav' (CC0) at the start, rubberduck CC0 'metal_falling_01' (metal collapse, HP 80 Hz) at 0.5 s, synthesized knee/torso impacts (sub thumps + plate modes) and debris ticks; concrete-room IR (wet 0.35)

### robot_hit.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.59 s; peak -3.0 dBFS, mean -25.8 dBFS, max 100 ms RMS -18.4 dBFS
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: rubberduck CC0 'metal_hit_01' (heavy metal hit, onset-trimmed, HP 120 Hz) layered with a synthesized armour-plate hit (bullet crack + 7-mode plate resonance + low thud) and spark crackle; concrete-room IR (wet 0.12)

### robot_hydraulic_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.77 s; peak -11.3 dBFS, mean -27.6 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Steam release sounds" by bart, file `steam hisses - Marker #5.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: bart 'steam hisses' (CC0) segment (pressure release), HP 400 Hz with envelope, layered with synthesized hydraulic layer (valve click, pressure groan 70-95 Hz, fluid rumble, piston end-stop clunk); small-room IR

### robot_hydraulic_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.86 s; peak -10.2 dBFS, mean -27.4 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Steam release sounds" by bart, file `steam hisses - Marker #4.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: bart 'steam hisses' (CC0) segment (pressure release), HP 400 Hz with envelope, layered with synthesized hydraulic layer (valve click, pressure groan 70-95 Hz, fluid rumble, piston end-stop clunk); small-room IR

### robot_hydraulic_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.97 s; peak -10.1 dBFS, mean -27.5 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Steam release sounds" by bart, file `steam hisses - Marker #3.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: bart 'steam hisses' (CC0) segment (pressure release), HP 400 Hz with envelope, layered with synthesized hydraulic layer (valve click, pressure groan 70-95 Hz, fluid rumble, piston end-stop clunk); small-room IR

### robot_idle_loop.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.00 s; peak -19.0 dBFS, mean -27.8 dBFS, max 100 ms RMS -26.3 dBFS; seam step at P94 of in-file sample steps, edge RMS diff 0.8 dB
- source: "Generator (loop)" by YCbCr, file `loop_generator_1.mp3` - https://opengameart.org/content/generator-loop (download https://opengameart.org/sites/default/files/loop_generator_1.mp3) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized 2.0 s loop: 50 Hz transformer hum harmonics (whole cycles), coil whine, fan noise and ticks (crossfaded) + YCbCr 'Generator (loop)' (CC0) made into a 2.0 s seamless bed (HP 40 Hz, LP 2 kHz); seamless (no fades)

### robot_servo_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.54 s; peak -11.5 dBFS, mean -24.8 dBFS, max 100 ms RMS -22.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill short 1.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: bart '68 Workshop Sounds' cordless-drill burst (CC0) slowed to 0.62x (heavier gear-motor whine), HP 120 Hz, 0.5 s with start/stop envelope; layered with a synthesized geared-servo layer (harmonic motor tone + gear-mesh band + brush noise + stop clunk)

### robot_servo_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.59 s; peak -10.5 dBFS, mean -24.4 dBFS, max 100 ms RMS -22.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill short 2.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: bart '68 Workshop Sounds' cordless-drill burst (CC0) slowed to 0.58x (heavier gear-motor whine), HP 120 Hz, 0.5 s with start/stop envelope; layered with a synthesized geared-servo layer (harmonic motor tone + gear-mesh band + brush noise + stop clunk)

### robot_servo_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.63 s; peak -10.5 dBFS, mean -24.9 dBFS, max 100 ms RMS -22.0 dBFS
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill3.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: bart '68 Workshop Sounds' cordless-drill burst (CC0) slowed to 0.66x (heavier gear-motor whine), HP 120 Hz, 0.5 s with start/stop envelope; layered with a synthesized geared-servo layer (harmonic motor tone + gear-mesh band + brush noise + stop clunk)

### robot_step_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.67 s; peak -4.3 dBFS, mean -22.4 dBFS, max 100 ms RMS -15.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_03.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #1.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.62-0.7x for mass, HP 40 Hz; layered with synthesized sub thump (110->34 Hz), low-passed impact noise, armour-plate modal clank, debris ticks, and bart 'steam hisses' (CC0) as the hydraulic hiss (HP 2 kHz, 0.35 s, delayed 50 ms); concrete-room IR (wet 0.2)

### robot_step_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.69 s; peak -5.6 dBFS, mean -22.7 dBFS, max 100 ms RMS -15.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_07.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #2.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.62-0.7x for mass, HP 40 Hz; layered with synthesized sub thump (110->34 Hz), low-passed impact noise, armour-plate modal clank, debris ticks, and bart 'steam hisses' (CC0) as the hydraulic hiss (HP 2 kHz, 0.35 s, delayed 50 ms); concrete-room IR (wet 0.2)

### robot_step_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.69 s; peak -3.6 dBFS, mean -22.3 dBFS, max 100 ms RMS -15.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_11.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #3.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.62-0.7x for mass, HP 40 Hz; layered with synthesized sub thump (110->34 Hz), low-passed impact noise, armour-plate modal clank, debris ticks, and bart 'steam hisses' (CC0) as the hydraulic hiss (HP 2 kHz, 0.35 s, delayed 50 ms); concrete-room IR (wet 0.2)

### robot_step_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.71 s; peak -6.1 dBFS, mean -22.5 dBFS, max 100 ms RMS -15.5 dBFS
- source: "Metal footsteps on concrete" by Thimras, file `metal_steps_15.wav` - https://opengameart.org/content/metal-footsteps-on-concrete (download https://opengameart.org/sites/default/files/metal_steps_48k24b.7z) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #4.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Thimras 'metal footsteps on concrete' step (CC0) slowed to 0.62-0.7x for mass, HP 40 Hz; layered with synthesized sub thump (110->34 Hz), low-passed impact noise, armour-plate modal clank, debris ticks, and bart 'steam hisses' (CC0) as the hydraulic hiss (HP 2 kHz, 0.35 s, delayed 50 ms); concrete-room IR (wet 0.2)

### robot_weakpoint.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.72 s; peak -2.0 dBFS, mean -26.9 dBFS, max 100 ms RMS -19.2 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: BMacZero 'Electricity Sound Effects' spark.wav (real Tesla-generator spark, CC0), onset-trimmed, HP 300 Hz; layered with synthesized capacitor 'ping' (2.95 kHz glassy modes), dense crackle, arc buzz and pop; concrete-room IR (wet 0.15)

### robot_zap.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.51 s; peak -3.3 dBFS, mean -23.9 dBFS, max 100 ms RMS -19.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: BMacZero 'continuousspark.wav' (real Tesla-generator arc pulses, CC0), HP 400 Hz, gated into a stutter; layered with synthesized mains-synchronous arc buzz bursts and crackle; small-room IR

### shell_tink_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.45 s; peak -14.7 dBFS, mean -33.0 dBFS, max 100 ms RMS -27.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: brass-casing modal resonators (inharmonic tube modes ~4.3-5.6 kHz), 3-5 bounces with shrinking intervals, short roll; small-room IR

### shell_tink_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.46 s; peak -14.0 dBFS, mean -33.5 dBFS, max 100 ms RMS -27.6 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: brass-casing modal resonators (inharmonic tube modes ~4.3-5.6 kHz), 3-5 bounces with shrinking intervals, short roll; small-room IR

### shell_tink_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.39 s; peak -14.1 dBFS, mean -32.4 dBFS, max 100 ms RMS -27.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: brass-casing modal resonators (inharmonic tube modes ~4.3-5.6 kHz), 3-5 bounces with shrinking intervals, short roll; small-room IR

### shell_tink_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.41 s; peak -14.3 dBFS, mean -32.9 dBFS, max 100 ms RMS -27.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py)
- processing: synthesized: brass-casing modal resonators (inharmonic tube modes ~4.3-5.6 kHz), 3-5 bounces with shrinking intervals, short roll; small-room IR

### step_concrete_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.46 s; peak -12.3 dBFS, mean -33.2 dBFS, max 100 ms RMS -27.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL1.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- processing: Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1)

### step_concrete_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.46 s; peak -11.0 dBFS, mean -33.1 dBFS, max 100 ms RMS -27.7 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR1.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- processing: Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1)

### step_concrete_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.43 s; peak -11.7 dBFS, mean -32.6 dBFS, max 100 ms RMS -27.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL2.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- processing: Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1)

### step_concrete_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.45 s; peak -11.6 dBFS, mean -32.1 dBFS, max 100 ms RMS -27.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR2.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- processing: Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1)

### step_concrete_4.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.51 s; peak -13.1 dBFS, mean -33.0 dBFS, max 100 ms RMS -27.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL3.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- processing: Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1)

### step_concrete_5.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.46 s; peak -11.0 dBFS, mean -31.7 dBFS, max 100 ms RMS -27.9 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR3.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- processing: Fantozzi 'Stone' footstep (CC0 via OpenGameArt), onset-trimmed, HP 70 Hz, slight 3 kHz presence, corridor IR (wet 0.1)

### step_metal_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.61 s; peak -11.6 dBFS, mean -32.4 dBFS, max 100 ms RMS -26.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL2.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_metal.ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12)

### step_metal_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.53 s; peak -11.4 dBFS, mean -31.9 dBFS, max 100 ms RMS -26.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR2.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_metal (2).ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12)

### step_metal_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.62 s; peak -13.7 dBFS, mean -32.4 dBFS, max 100 ms RMS -26.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL3.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_metal (3).ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12)

### step_metal_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.55 s; peak -12.2 dBFS, mean -30.8 dBFS, max 100 ms RMS -26.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR3.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_metal (4).ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12)

### step_metal_4.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.56 s; peak -13.1 dBFS, mean -32.8 dBFS, max 100 ms RMS -26.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL1.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_metal.ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12)

### step_metal_5.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.56 s; peak -12.2 dBFS, mean -32.5 dBFS, max 100 ms RMS -26.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR1.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "Footsteps Leather, Cloth, Armor" by HaelDB, file `footsteps/step_metal (2).ogg` - https://opengameart.org/content/footsteps-leather-cloth-armor (download https://opengameart.org/sites/default/files/footsteps.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Fantozzi 'Stone' footstep (pitch -5..+5 %) used as excitation for a synthesized steel-plate resonator bank (6 inharmonic modes 170-3600 Hz), mixed with the dry step, plus a HaelDB 'step_metal' gear clink at -12 dB; corridor IR (wet 0.12)

### tesla_charge.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.60 s; peak -8.5 dBFS, mean -23.0 dBFS, max 100 ms RMS -18.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: synthesized: rising capacitor/inverter whine (260 Hz -> 3.6 kHz, beating partials), accelerating Poisson crackle, swelling mains hum and arc buzz, plus BMacZero 'continuousspark.wav' (CC0) rising underneath; small-room IR; 0.55 s

### tesla_shot.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.82 s; peak -3.1 dBFS, mean -19.7 dBFS, max 100 ms RMS -12.5 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: BMacZero 'spark.wav' (real arc crack, CC0) onset-aligned on top of a synthesized discharge: broadband crack, dense arc crackle, 50 Hz arc buzz, sub thump (170->42 Hz) and low boom, compressed and soft-clipped; concrete-room IR (wet 0.4)

### ui_click.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.10 s; peak -10.0 dBFS, mean -35.1 dBFS, max 100 ms RMS -35.2 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/click_001.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- processing: Kenney 'Interface Sounds' click_001 (CC0), onset-trimmed

### ui_hack_done.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.56 s; peak -14.2 dBFS, mean -27.7 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/confirmation_002.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- processing: Kenney 'Interface Sounds' confirmation_002 (CC0), small-room IR (wet 0.15)

### ui_hack_tick.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.04 s; peak -14.0 dBFS, mean -27.1 dBFS, max 100 ms RMS -31.2 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/tick_004.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- processing: Kenney 'Interface Sounds' tick_004 (CC0), onset-trimmed

### ui_objective.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.44 s; peak -14.0 dBFS, mean -26.2 dBFS, max 100 ms RMS -21.0 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/confirmation_001.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- processing: Kenney 'Interface Sounds' confirmation_001 (CC0), small-room IR (wet 0.15)

### weapon_switch.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.46 s; peak -7.1 dBFS, mean -29.4 dBFS, max 100 ms RMS -24.0 dBFS
- source: "50 RPG sound effects" by Kenney, file `OGG/cloth2.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalLatch.ogg` - https://opengameart.org/content/50-rpg-sound-effects (download https://opengameart.org/sites/default/files/RPGsounds_Kenney.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py)
- processing: Kenney RPG Audio 'cloth2' (sling/cloth rustle) + 'metalLatch' (handling clack at 0.2 s), HP 120 Hz; synthesized grip impact (modal); small-room IR (wet 0.1)

