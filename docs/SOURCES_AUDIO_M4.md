# BREACH audio M4 (staging/audio_m4) - sources and processing

Rebuild: `python -I tools/m2/audio_fetch.py oga_chain_winch_bart` (the only new download; all other sources were already in staging/audio/raw/), then `python -I tools/m2/audio_m4.py`.
All recordings are CC0 1.0 (licence verified on each asset's OpenGameArt page, stored in raw/<id>/SOURCE.json). Everything else is synthesized, first-party work of this project.

Format: 16-bit PCM WAV, 48 kHz; mono for all positional sounds, stereo only for ambience_* loops (alarm_loop and lift_motor_loop are mono, positional).
Summary: 24 outputs use CC0 recordings (0 edited recordings only, 24 layered with synthesis); 2 are fully synthesized.

Loudness (max 100 ms RMS, same hierarchy as M2/M3): core_overload -9 (finale, loudest set piece, still under the player's rifle peak), capacitor_destroyed -12, breaker_close -14, blast_door_open -15, lift_arrive -16, alarm_loop -17, capacitor_hit -17, robot_wake -18, breaker_hum_rise -20, relay_voice_beep -22, arc_crackle -22, lift_call / lift_motor_loop -24, crawl_step -25; ambience loops about -31 dBFS mean like the M2/M3 beds. Loops are steady-state (circular reverb/filters, whole-cycle tones, crossfaded beds, time-wrapped events) and checked for a seamless end-to-start join.

## Source assets

| id (raw/ dir) | asset | author | licence | page |
|---|---|---|---|---|
| oga_100_metal_wood_rubberduck | 100 CC0 metal and wood SFX | rubberduck | CC0 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx |
| oga_100_sfx2_rubberduck | 100 CC0 SFX #2 | rubberduck | CC0 | https://opengameart.org/content/100-cc0-sfx-2 |
| oga_30_loops_rubberduck | 30 CC0 SFX loops | rubberduck | CC0 | https://opengameart.org/content/30-cc0-sfx-loops |
| oga_75_breaking_rubberduck | 75 CC0 breaking / falling / hit sfx | rubberduck | CC0 | https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx |
| oga_chain_winch_bart | Chain winch sounds | bart | CC0 | https://opengameart.org/content/chain-winch-sounds |
| oga_circuit_breaker | SFX - Circuit breaker | CleytonKauffman | CC0 | https://opengameart.org/content/sfx-circuit-breaker |
| oga_edev_loop_qubodup | Electronic device loop | qubodup | CC0 | https://opengameart.org/content/electronic-device-loop |
| oga_electricity_bmaczero | Electricity Sound Effects | BMacZero | CC0 | https://opengameart.org/content/electricity-sound-effects-0 |
| oga_fan_loop_qubodup | (defect) motor loop | qubodup | CC0 | https://opengameart.org/content/defect-motor-loop |
| oga_fantozzi_steps | Fantozzi's Footsteps (Grass/Sand & Stone) | Fantozzi (Submitted by qubodup) | CC0 | https://opengameart.org/content/fantozzis-footsteps-grasssand-stone |
| oga_kenney_interface | Interface Sounds | Kenney | CC0 | https://opengameart.org/content/interface-sounds |
| oga_kenney_scifi | Sci-Fi Sounds | Kenney | CC0 | https://opengameart.org/content/sci-fi-sounds |
| oga_kenney_ui | 51 UI sound effects (buttons, switches and clicks) | Kenney | CC0 | https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks |
| oga_mechanical_bmaczero | Mechanical Sounds | BMacZero | CC0 | https://opengameart.org/content/mechanical-sounds |
| oga_metal_interactions_qubodup | Metal Interactions | qubodup | CC0 | https://opengameart.org/content/metal-interactions |
| oga_steam_hisses_bart | Steam release sounds | bart | CC0 | https://opengameart.org/content/steam-release-sounds |
| oga_workshop_bart | 68 Workshop Sounds | bart | CC0 | https://opengameart.org/content/68-workshop-sounds |

## Output files

### alarm_loop.wav
- format: 16-bit PCM, 48000 Hz, mono, 3.20 s; peak -6.8 dBFS, mean -22.0 dBFS, max 100 ms RMS -17.0 dBFS; seam step at P19 of in-file sample steps, edge RMS diff 1.4 dB
- source: synthesized (tools/m2/synth_audio_v2.py and tools/m2/audio_m4.py)
- processing: synthesized 3.2 s seamless klaxon loop: two low industrial horn blasts per cycle (detuned saw pair ~half a semitone apart for a rough beating tone, faint sub-octave, HP 110 Hz, 560/1450/2600 Hz horn formants, hard saturation): a rising 150->166 Hz blast then a longer falling 146->116 Hz blast; circular (steady-state) convolution with a synthesized 3.5 s industrial-hall IR so the reverb tail wraps across the loop point; LP 6 kHz; loop rotated so it starts in the tail, first blast at 0.32 s

### ambience_core.wav
- format: 16-bit PCM, 48000 Hz, stereo, 16.00 s; peak -19.0 dBFS, mean -30.9 dBFS, max 100 ms RMS -31.5 dBFS; seam step at P54 of in-file sample steps, edge RMS diff 1.0 dB
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: 16 s seamless stereo loop: synthesized deep resonant drone (detuned low partials ~36.7/37.1 Hz beating, 51.9 Hz tritone, 55 and 73.5 Hz, all with whole cycles over the loop), slowly sweeping high-Q resonant noise (periodic centre 90-320 Hz), metallic resonances at 233/331 Hz with periodic swells, 'breathing' sub modulation; occasional arcs (BMacZero 'spark.wav' and 'continuousspark.wav', CC0, with synthesized crackle) through the 3.5 s industrial-hall IR, time-wrapped across the loop point

### ambience_pump.wav
- format: 16-bit PCM, 48000 Hz, stereo, 12.00 s; peak -18.0 dBFS, mean -30.8 dBFS, max 100 ms RMS -29.8 dBFS; seam step at P76 of in-file sample steps, edge RMS diff 0.3 dB
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_loop_water_01.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- source: "100 CC0 SFX #2" by rubberduck, file `sfx100v2_loop_water_03.ogg` - https://opengameart.org/content/100-cc0-sfx-2 (download https://opengameart.org/sites/default/files/sfx_100_v2.zip) - licence CC0
- source: "30 CC0 SFX loops" by rubberduck, file `pump_01.ogg` - https://opengameart.org/content/30-cc0-sfx-loops (download https://opengameart.org/sites/default/files/sfx_loops.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: 12 s seamless stereo loop of a large pump room: rubberduck '100 CC0 SFX #2' loop_water_01 / loop_water_03 (CC0, water flow, LP 7 kHz) as L/R-decorrelated beds, rubberduck '30 CC0 SFX loops' pump_01 (CC0, 0.7x, LP 2.5 kHz) as the pump, synthesized pump drone (29.5 Hz harmonics with a 1.5 Hz pumping pulse, whole cycles over the loop); synthesized water drips through the industrial-hall IR, time-wrapped across the loop point; beds equal-power crossfaded

### ambience_switchgear.wav
- format: 16-bit PCM, 48000 Hz, stereo, 10.00 s; peak -21.5 dBFS, mean -31.3 dBFS, max 100 ms RMS -30.4 dBFS; seam step at P94 of in-file sample steps, edge RMS diff 0.4 dB
- source: "(defect) motor loop" by qubodup, file `fan_interval.wav` - https://opengameart.org/content/defect-motor-loop (download https://opengameart.org/sites/default/files/fan_interval.wav) - licence CC0
- source: "Electronic device loop" by qubodup, file `qubodup-edev.flac` - https://opengameart.org/content/electronic-device-loop (download https://opengameart.org/sites/default/files/qubodup-edev.flac) - licence CC0
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: 10 s seamless stereo loop of a switchgear room: synthesized transformer hum (100 Hz dominant with 50/150/200/300/400/600 Hz, slow periodic drift, whole cycles), mains-synchronous magnetostriction rasp (gated noise, circular filtering), qubodup '(defect) motor loop' fan recording (CC0, stereo, LP 4 kHz) and qubodup 'Electronic device loop' (CC0, low level) as cooling fans; two faint arc ticks (BMacZero 'spark.wav', CC0) through a small-room IR, time-wrapped; beds crossfaded

### arc_crackle_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.45 s; peak -4.1 dBFS, mean -25.7 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: short transformer arcing, 0.35 s: BMacZero 'continuousspark.wav' (real Tesla-generator arc pulses, CC0), HP 400 Hz, two bursts, layered with synthesized Poisson crackle and stuttering mains-synchronous arc buzz; small-room IR (wet 0.12)

### arc_crackle_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.59 s; peak -3.8 dBFS, mean -26.4 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: short transformer arcing, 0.55 s: BMacZero 'spark.wav' (real arc, CC0), HP 300 Hz, layered with synthesized Poisson crackle and stuttering mains-synchronous arc buzz; small-room IR (wet 0.12)

### arc_crackle_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.80 s; peak -7.0 dBFS, mean -26.4 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: short transformer arcing, 0.75 s: BMacZero 'continuousspark.wav' (CC0) at the start, layered with synthesized Poisson crackle and stuttering mains-synchronous arc buzz; small-room IR (wet 0.12)

### blast_door_open.wav
- format: 16-bit PCM, 48000 Hz, mono, 3.96 s; peak -5.0 dBFS, mean -24.1 dBFS, max 100 ms RMS -15.0 dBFS
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_slam_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "Mechanical Sounds" by BMacZero, file `clank1.wav` - https://opengameart.org/content/mechanical-sounds (download https://opengameart.org/sites/default/files/clank1.wav) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_04.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "Steam release sounds" by bart, file `steam hisses - Marker #2.wav` - https://opengameart.org/content/steam-release-sounds (download https://opengameart.org/sites/default/files/steam_hisses.zip) - licence CC0
- source: "30 CC0 SFX loops" by rubberduck, file `rolling.ogg` - https://opengameart.org/content/30-cc0-sfx-loops (download https://opengameart.org/sites/default/files/sfx_loops.zip) - licence CC0
- source: "30 CC0 SFX loops" by rubberduck, file `machine_11.ogg` - https://opengameart.org/content/30-cc0-sfx-loops (download https://opengameart.org/sites/default/files/sfx_loops.zip) - licence CC0
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - dragging metal.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: heavy hydraulic blast door, 3.6 s: three locking-bolt retractions (rubberduck 'metal_slam_01' (CC0), BMacZero 'clank1' (CC0), rubberduck 'metal_hit_04' (CC0), each over a synthesized low modal clunk + sub thump), bart 'steam hisses' Marker #2 (CC0) as the hydraulic release, then the slide: rubberduck '30 CC0 SFX loops' rolling.ogg (CC0, slowed 0.45x, looped) + loop machine_11 (CC0, 0.7x, LP 800 Hz) + bart workshop 'dragging metal' (CC0, 0.6x, LP 2.5 kHz) + synthesized sub rumble, all with a ramp-up/ramp-down envelope; end-stop clunk; concrete-room IR (wet 0.3)

### breaker_close.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.73 s; peak -2.6 dBFS, mean -21.7 dBFS, max 100 ms RMS -14.0 dBFS
- source: "SFX - Circuit breaker" by CleytonKauffman, file `switch on.wav` - https://opengameart.org/content/sfx-circuit-breaker (download https://opengameart.org/sites/default/files/Circuit%20Breaker.zip) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_slam_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: large main breaker closing: CleytonKauffman 'SFX - Circuit breaker' switch on (CC0) slowed 0.6x (lever throw), rubberduck 'metal_slam_01' (CC0) as the lever slamming home, BMacZero 'spark.wav' (real arc, CC0) as the arc snap; synthesized crack, 60 ms mains-synchronous arc buzz, sub thump; concrete-room IR (wet 0.25)

### breaker_hum_rise.wav
- format: 16-bit PCM, 48000 Hz, mono, 1.50 s; peak -13.2 dBFS, mean -23.8 dBFS, max 100 ms RMS -20.0 dBFS
- source: synthesized (tools/m2/synth_audio_v2.py and tools/m2/audio_m4.py)
- processing: synthesized transformer energizing, 1.5 s: inrush thump, 50 Hz mains hum with 100 Hz dominant and harmonics up to 600 Hz rising in level and richness (higher harmonics arrive later), mains-synchronous magnetostriction rasp (gated noise, BP 1.8 kHz) rising; ends at full level with a short fade

### capacitor_destroyed.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.07 s; peak -2.1 dBFS, mean -20.2 dBFS, max 100 ms RMS -12.0 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_glass_breaking_01.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_02.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- source: "Sci-Fi Sounds" by Kenney, file `Audio/explosionCrunch_000.ogg` - https://opengameart.org/content/sci-fi-sounds (download https://opengameart.org/sites/default/files/sci-fi_sounds.zip) - licence CC0
- source: "Sci-Fi Sounds" by Kenney, file `Audio/lowFrequency_explosion_001.ogg` - https://opengameart.org/content/sci-fi-sounds (download https://opengameart.org/sites/default/files/sci-fi_sounds.zip) - licence CC0
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_glass_falling_02.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_falling_04.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: capacitor bank failing, 2.5 s: crack (rubberduck 'bfh1_glass_breaking_01' + 'metal_hit_02', CC0), burst (Kenney 'Sci-Fi Sounds' explosionCrunch_000 and lowFrequency_explosion_001, CC0), electrical roar (synthesized dense arc crackle + 50 Hz arc buzz + BMacZero 'continuousspark.wav' (CC0) repeated, decaying over 1.8 s with stutters), falling debris (rubberduck 'bfh1_glass_falling_02' and 'bfh1_metal_falling_04', CC0); concrete-room IR (wet 0.3), compression

### capacitor_hit_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.60 s; peak -2.5 dBFS, mean -24.1 dBFS, max 100 ms RMS -17.0 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_glass_hit_01.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_03.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: bullet on a capacitor stack: rubberduck 'bfh1_glass_hit_01.ogg' (CC0, glass) and 'metal_hit_03.ogg' (CC0, metal), onset-trimmed, HP 250 Hz; synthesized dense crackle burst, discharge buzz and a 3.4 kHz glassy ping; concrete-room IR (wet 0.12)

### capacitor_hit_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.58 s; peak -2.0 dBFS, mean -24.2 dBFS, max 100 ms RMS -17.0 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_glass_hit_02.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_hit_05.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: bullet on a capacitor stack: rubberduck 'bfh1_glass_hit_02.ogg' (CC0, glass) and 'metal_hit_05.ogg' (CC0, metal), onset-trimmed, HP 250 Hz; synthesized dense crackle burst, discharge buzz and a 3.4 kHz glassy ping; concrete-room IR (wet 0.12)

### capacitor_hit_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.57 s; peak -1.0 dBFS, mean -24.2 dBFS, max 100 ms RMS -17.1 dBFS
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_glass_breaking_02.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_metal_hit_02.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: bullet on a capacitor stack: rubberduck 'bfh1_glass_breaking_02.ogg' (CC0, glass) and 'bfh1_metal_hit_02.ogg' (CC0, metal), onset-trimmed, HP 250 Hz; synthesized dense crackle burst, discharge buzz and a 3.4 kHz glassy ping; BMacZero 'spark.wav' (CC0); concrete-room IR (wet 0.12)

### core_overload.wav
- format: 16-bit PCM, 48000 Hz, mono, 5.00 s; peak -3.8 dBFS, mean -15.3 dBFS, max 100 ms RMS -9.0 dBFS
- source: "Electricity Sound Effects" by BMacZero, file `continuousspark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/continuousspark.wav) - licence CC0
- source: "Electricity Sound Effects" by BMacZero, file `spark.wav` - https://opengameart.org/content/electricity-sound-effects-0 (download https://opengameart.org/sites/default/files/spark.wav) - licence CC0
- source: "Sci-Fi Sounds" by Kenney, file `Audio/lowFrequency_explosion_001.ogg` - https://opengameart.org/content/sci-fi-sounds (download https://opengameart.org/sites/default/files/sci-fi_sounds.zip) - licence CC0
- source: "Sci-Fi Sounds" by Kenney, file `Audio/explosionCrunch_002.ogg` - https://opengameart.org/content/sci-fi-sounds (download https://opengameart.org/sites/default/files/sci-fi_sounds.zip) - licence CC0
- source: "Sci-Fi Sounds" by Kenney, file `Audio/lowFrequency_explosion_000.ogg` - https://opengameart.org/content/sci-fi-sounds (download https://opengameart.org/sites/default/files/sci-fi_sounds.zip) - licence CC0
- source: "Sci-Fi Sounds" by Kenney, file `Audio/explosionCrunch_000.ogg` - https://opengameart.org/content/sci-fi-sounds (download https://opengameart.org/sites/default/files/sci-fi_sounds.zip) - licence CC0
- source: "75 CC0 breaking / falling / hit sfx" by rubberduck, file `bfh1_glass_breaking_03.ogg` - https://opengameart.org/content/75-cc0-breaking-falling-hit-sfx (download https://opengameart.org/sites/default/files/sfx_breaking_and_falling.zip) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_falling_02.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: finale multi-stage discharge, 5.0 s: (1) synthesized 1.4 s capacitor overload whine (from audio_m3) with BMacZero arc recordings (CC0); (2) first discharge at 1.4 s - synthesized tesla-style crack/thump + BMacZero 'spark.wav' + Kenney 'Sci-Fi Sounds' lowFrequency_explosion_001 (CC0) - followed by an electrical roar; (3) second, bigger discharge at 2.4 s with Kenney explosionCrunch_002 (CC0); (4) a fast 0.8 s re-charge whine; (5) the final burst at 3.3 s: Kenney lowFrequency_explosion_000 + explosionCrunch_000 (CC0), rubberduck 'bfh1_glass_breaking_03' and 'metal_falling_02' debris (CC0), dense crackle; whole mix compressed, sent through the synthesized 3.5 s industrial-hall IR (wet 0.35), then 6 dB into a look-ahead limiter

### crawl_step_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.70 s; peak -13.6 dBFS, mean -32.0 dBFS, max 100 ms RMS -25.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL1.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_05.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: cramped duct step: Fantozzi 'Stone' footstep (CC0, StoneL1, pitch varied) used as excitation for a synthesized thin sheet-metal duct resonator bank (7 modes 140-1500 Hz) plus the dry step, rubberduck 'metal_sheet_05.ogg' (CC0, sheet metal flex, HP 120 Hz) at -6 dB, two small rattle clicks; synthesized duct IR (24 dense reflections within 8 ms, T60 0.25 s)

### crawl_step_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.67 s; peak -11.7 dBFS, mean -31.7 dBFS, max 100 ms RMS -25.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR2.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_04.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: cramped duct step: Fantozzi 'Stone' footstep (CC0, StoneR2, pitch varied) used as excitation for a synthesized thin sheet-metal duct resonator bank (7 modes 140-1500 Hz) plus the dry step, rubberduck 'metal_sheet_04.ogg' (CC0, sheet metal flex, HP 120 Hz) at -6 dB, two small rattle clicks; synthesized duct IR (24 dense reflections within 8 ms, T60 0.25 s)

### crawl_step_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.70 s; peak -13.8 dBFS, mean -31.0 dBFS, max 100 ms RMS -25.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneL3.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_02.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: cramped duct step: Fantozzi 'Stone' footstep (CC0, StoneL3, pitch varied) used as excitation for a synthesized thin sheet-metal duct resonator bank (7 modes 140-1500 Hz) plus the dry step, rubberduck 'metal_sheet_02.ogg' (CC0, sheet metal flex, HP 120 Hz) at -6 dB, two small rattle clicks; synthesized duct IR (24 dense reflections within 8 ms, T60 0.25 s)

### crawl_step_3.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.67 s; peak -12.6 dBFS, mean -32.1 dBFS, max 100 ms RMS -25.0 dBFS
- source: "Fantozzi's Footsteps (Grass/Sand & Stone)" by Fantozzi (Submitted by qubodup), file `Fantozzi-footsteps/flac/Fantozzi-StoneR1.flac` - https://opengameart.org/content/fantozzis-footsteps-grasssand-stone (download https://opengameart.org/sites/default/files/Fantozzi-footsteps.7z) - licence CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_sheet_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx (download https://opengameart.org/sites/default/files/100-CC0-wood-metal-SFX.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: cramped duct step: Fantozzi 'Stone' footstep (CC0, StoneR1, pitch varied) used as excitation for a synthesized thin sheet-metal duct resonator bank (7 modes 140-1500 Hz) plus the dry step, rubberduck 'metal_sheet_01.ogg' (CC0, sheet metal flex, HP 120 Hz) at -6 dB, two small rattle clicks; synthesized duct IR (24 dense reflections within 8 ms, T60 0.25 s)

### lift_arrive.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.56 s; peak -7.0 dBFS, mean -27.8 dBFS, max 100 ms RMS -16.0 dBFS
- source: "30 CC0 SFX loops" by rubberduck, file `machine_11.ogg` - https://opengameart.org/content/30-cc0-sfx-loops (download https://opengameart.org/sites/default/files/sfx_loops.zip) - licence CC0
- source: "Chain winch sounds" by bart, file `winch - Marker #9.wav` - https://opengameart.org/content/chain-winch-sounds (download https://opengameart.org/sites/default/files/winch.zip) - licence CC0
- source: "Mechanical Sounds" by BMacZero, file `clank1.wav` - https://opengameart.org/content/mechanical-sounds (download https://opengameart.org/sites/default/files/clank1.wav) - licence CC0
- source: "Mechanical Sounds" by BMacZero, file `rattle1.wav` - https://opengameart.org/content/mechanical-sounds (download https://opengameart.org/sites/default/files/rattle1.wav) - licence CC0
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - metal clatter.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: heavy lift arriving, ~2.4 s: the lift-motor layers (synthesized motor + rubberduck machine_11 + bart chain winch, CC0) varispeed-decelerating to a stop over 1.1 s, a heavy stop clunk (BMacZero 'clank1' (CC0) slowed 0.7x over a synthesized low clunk + sub thump) at 1.1 s, a gate rattle at 1.35 s (BMacZero 'rattle1' + bart workshop 'metal clatter', CC0); concrete-room IR (wet 0.25)

### lift_call.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.78 s; peak -10.4 dBFS, mean -31.2 dBFS, max 100 ms RMS -24.0 dBFS
- source: "Metal Interactions" by qubodup, file `metal_interactions/metal_button_press2.wav` - https://opengameart.org/content/metal-interactions (download https://opengameart.org/sites/default/files/metal_interactions.7z) - licence CC0
- source: "SFX - Circuit breaker" by CleytonKauffman, file `switch off.wav` - https://opengameart.org/content/sfx-circuit-breaker (download https://opengameart.org/sites/default/files/Circuit%20Breaker.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: qubodup 'Metal Interactions' metal_button_press2 (CC0), HP 150 Hz; relay clunk 0.22 s later: CleytonKauffman 'SFX - Circuit breaker' switch off (CC0) slowed 0.75x over a synthesized small low clunk (modal 180/420 Hz); small-room IR (wet 0.1)

### lift_motor_loop.wav
- format: 16-bit PCM, 48000 Hz, mono, 4.00 s; peak -15.5 dBFS, mean -26.1 dBFS, max 100 ms RMS -24.0 dBFS; seam step at P60 of in-file sample steps, edge RMS diff 0.2 dB
- source: "30 CC0 SFX loops" by rubberduck, file `machine_11.ogg` - https://opengameart.org/content/30-cc0-sfx-loops (download https://opengameart.org/sites/default/files/sfx_loops.zip) - licence CC0
- source: "Chain winch sounds" by bart, file `winch - Marker #9.wav` - https://opengameart.org/content/chain-winch-sounds (download https://opengameart.org/sites/default/files/winch.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: 4.0 s seamless loop: synthesized freight-lift motor (50 Hz mains harmonics, rotor whine 412.5 Hz + slot harmonic, whole cycles over the loop, slight periodic load swell) + rubberduck '30 CC0 SFX loops' machine_11 (CC0, 0.8x, LP 1.5 kHz) and bart 'Chain winch sounds' Marker #9 (CC0, 0.8x, LP 3 kHz, low level) as cable/chain run, both made into seamless beds by equal-power crossfades; circular LP 6 kHz

### relay_voice_beep_0.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.27 s; peak -14.2 dBFS, mean -23.7 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/glitch_001.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: synthesized 'system announcement' chirp (no speech): two rising tones (C6 -> G6) over a formant-filtered synthetic voice buzz (saw 220->260 Hz through moving vowel-like formants), radio band-limit 350 Hz-3.4 kHz, sample-and-hold bit-crush to 12 kHz; Kenney 'Interface Sounds' glitch_001.ogg (CC0) as a digital squelch at the start

### relay_voice_beep_1.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.28 s; peak -13.3 dBFS, mean -23.3 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/glitch_002.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: synthesized 'system announcement' chirp (no speech): three short tones (E6-C6-E6) over a formant-filtered synthetic voice buzz (saw 240->200 Hz through moving vowel-like formants), radio band-limit 350 Hz-3.4 kHz, sample-and-hold bit-crush to 12 kHz; Kenney 'Interface Sounds' glitch_002.ogg (CC0) as a digital squelch at the start

### relay_voice_beep_2.wav
- format: 16-bit PCM, 48000 Hz, mono, 0.32 s; peak -15.1 dBFS, mean -23.5 dBFS, max 100 ms RMS -22.0 dBFS
- source: "Interface Sounds" by Kenney, file `Audio/glitch_003.ogg` - https://opengameart.org/content/interface-sounds (download https://opengameart.org/sites/default/files/kenney_interfaceSounds.zip) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: synthesized 'system announcement' chirp (no speech): a 35 Hz FM warble around 1.2 kHz falling at the end over a formant-filtered synthetic voice buzz (saw 200->180 Hz through moving vowel-like formants), radio band-limit 350 Hz-3.4 kHz, sample-and-hold bit-crush to 12 kHz; Kenney 'Interface Sounds' glitch_003.ogg (CC0) as a digital squelch at the start

### robot_wake.wav
- format: 16-bit PCM, 48000 Hz, mono, 2.20 s; peak -2.0 dBFS, mean -23.2 dBFS, max 100 ms RMS -18.8 dBFS
- source: "51 UI sound effects (buttons, switches and clicks)" by Kenney, file `switch18.wav` - https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks (download https://opengameart.org/sites/default/files/UI_SFX_Set.zip) - licence CC0
- source: "SFX - Circuit breaker" by CleytonKauffman, file `switch off.wav` - https://opengameart.org/content/sfx-circuit-breaker (download https://opengameart.org/sites/default/files/Circuit%20Breaker.zip) - licence CC0
- source: "51 UI sound effects (buttons, switches and clicks)" by Kenney, file `switch16.wav` - https://opengameart.org/content/51-ui-sound-effects-buttons-switches-and-clicks (download https://opengameart.org/sites/default/files/UI_SFX_Set.zip) - licence CC0
- source: "68 Workshop Sounds" by bart, file `workshop/workshop - drill5.wav` - https://opengameart.org/content/68-workshop-sounds (download https://opengameart.org/sites/default/files/workshop.7z) - licence CC0
- plus synthesized layers (tools/m2/synth_audio_v2.py, audio_m3.py, audio_m4.py)
- processing: dormant robot powering up, 2.0 s: relay clicks (Kenney '51 UI sound effects' switch18 and switch16, CC0; CleytonKauffman circuit breaker switch off at -8 dB, CC0), a swelling 50 Hz power hum, rising servo whine (bart workshop 'drill5' (CC0) varispeed 0.35x -> 0.85x plus a synthesized rising geared servo), an optic hum (synthesized 880 -> 1320 Hz tone with 12 Hz tremolo and a focus chirp at 1.45 s), two servo twitch clicks; concrete-room IR (wet 0.15)

