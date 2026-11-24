# BREACH audio M4.3 (staging/audio_m43) - weapon shot layers: sources and processing

Rebuild: `python -I tools/m2/audio_m43.py` (no new downloads; all recordings were already in staging/audio/raw/).
All recordings are CC0 1.0 (licence recorded in staging/audio/raw/<id>/SOURCE.json, verified on the asset page when fetched). Everything else is synthesized by tools/m2/audio_m43.py (first-party).
Format: 16-bit PCM WAV, 48 kHz; mono except shot_room_* (stereo, decorrelated L/R). No dither (tails end in digital silence).
`preview/` holds audition mixes only (not game assets). `metrics.json` holds the measurements below for every file.

## Source assets

| id (raw/ dir) | asset | author | licence | page |
|---|---|---|---|---|
| oga_100_metal_wood_rubberduck | 100 CC0 metal and wood SFX | rubberduck | CC0 | https://opengameart.org/content/100-cc0-metal-and-wood-sfx |
| oga_free_firearm_sound_library | The Free Firearm Sound Library | Ben Jaszczak, et al. (Submitted by bart ) | CC0 | https://opengameart.org/content/the-free-firearm-sound-library |
| oga_handgun_reload_zer0sol | Handgun Reload Sound Effect | zer0_sol | CC0 | https://opengameart.org/content/handgun-reload-sound-effect |
| oga_kenney_rpg | 50 RPG sound effects | Kenney | CC0 | https://opengameart.org/content/50-rpg-sound-effects |
| oga_metal_impact_bmaczero | Metal Impact Sounds | BMacZero | CC0 | https://opengameart.org/content/metal-impact-sounds |
| oga_shotgun_reload_zer0sol | Shotgun Reload Sound effects | zer0_sol | CC0 | https://opengameart.org/content/shotgun-reload-sound-effects |

## Measured (first 250 ms band energies relative to 400-2000 Hz; crest = peak - RMS over 400 ms)

| file | len s | peak dBFS | RMS400 | crest | sub | body | presence | air | note |
|---|---|---|---|---|---|---|---|---|---|
| rifle_close_0 | 0.56 | -1.0 | -16.0 | 15.0 | -5.5 | +1.5 | -3.5 | -10.6 |  |
| rifle_close_1 | 0.56 | -1.0 | -16.0 | 15.0 | -5.5 | +1.5 | -3.5 | -10.5 |  |
| rifle_close_2 | 0.56 | -1.0 | -16.0 | 15.0 | -5.5 | +1.5 | -3.5 | -10.5 |  |
| rifle_close_3 | 0.56 | -1.0 | -16.5 | 15.5 | -5.5 | +1.5 | -3.5 | -10.5 |  |
| rifle_supp_close_0 | 0.48 | -8.5 | -24.2 | 15.7 | -7.0 | +2.8 | -6.8 | -18.7 | 8.1 dB under open rifle RMS |
| rifle_supp_close_1 | 0.48 | -8.5 | -24.2 | 15.7 | -7.0 | +2.8 | -6.8 | -18.6 | 8.1 dB under open rifle RMS |
| rifle_supp_close_2 | 0.48 | -8.3 | -24.2 | 16.0 | -7.0 | +2.8 | -6.8 | -19.0 | 8.1 dB under open rifle RMS |
| rifle_supp_close_3 | 0.48 | -8.5 | -24.2 | 15.7 | -7.0 | +2.8 | -6.8 | -18.3 | 8.1 dB under open rifle RMS |
| pistol_close_0 | 0.47 | -1.0 | -17.9 | 16.9 | -8.0 | -0.0 | -2.5 | -9.6 |  |
| pistol_close_1 | 0.47 | -1.0 | -18.0 | 17.0 | -8.0 | -0.0 | -2.5 | -9.6 |  |
| pistol_close_2 | 0.47 | -1.0 | -18.0 | 17.0 | -8.0 | +0.0 | -2.5 | -9.6 |  |
| pistol_close_3 | 0.47 | -1.0 | -18.2 | 17.2 | -8.0 | +0.0 | -2.5 | -9.8 |  |
| rifle_mech_0 | 0.25 | -6.0 | -20.7 | 14.7 | -32.9 | -15.0 | +5.8 | +3.6 |  |
| rifle_mech_1 | 0.25 | -6.0 | -21.1 | 15.1 | -31.8 | -14.0 | +6.3 | +3.3 |  |
| rifle_mech_2 | 0.25 | -6.0 | -21.5 | 15.5 | -34.9 | -16.6 | +5.4 | +3.8 |  |
| pistol_mech_0 | 0.17 | -6.0 | -21.0 | 15.0 | -32.2 | -22.6 | +5.6 | +7.3 |  |
| pistol_mech_1 | 0.17 | -6.0 | -21.5 | 15.5 | -33.0 | -21.7 | +5.0 | +7.1 |  |
| pistol_mech_2 | 0.17 | -6.0 | -21.0 | 15.0 | -32.0 | -21.7 | +4.6 | +5.8 |  |
| shot_room_small_0 | 0.75 | -8.0 | -26.0 | 18.0 | -4.4 | +5.2 | -5.0 | -17.3 | L/R corr -0.05; decay T20x3 0.68 s |
| shot_room_small_1 | 0.75 | -8.0 | -24.9 | 16.9 | -2.6 | +3.6 | -5.2 | -17.1 | L/R corr +0.22; decay T20x3 0.66 s |
| shot_room_medium_0 | 1.35 | -8.0 | -24.0 | 16.0 | -7.9 | +3.9 | -4.6 | -17.5 | L/R corr -0.02; decay T20x3 1.04 s |
| shot_room_medium_1 | 1.35 | -8.0 | -24.7 | 16.7 | -7.6 | +4.0 | -6.2 | -17.4 | L/R corr +0.13; decay T20x3 0.98 s |
| shot_room_large_0 | 2.70 | -8.0 | -23.2 | 15.2 | -5.1 | +6.0 | -4.2 | -15.4 | L/R corr +0.09; decay T20x3 2.04 s |
| shot_room_large_1 | 2.70 | -8.0 | -24.3 | 16.3 | -9.5 | +3.0 | -5.6 | -15.9 | L/R corr +0.08; decay T20x3 2.27 s |
| shot_room_huge_0 | 3.50 | -8.0 | -25.3 | 17.3 | -5.1 | +6.4 | -4.4 | -14.6 | L/R corr +0.03; decay T20x3 2.77 s |
| shot_room_huge_1 | 3.50 | -8.0 | -23.1 | 15.1 | -6.5 | +6.3 | -5.2 | -15.1 | L/R corr +0.10; decay T20x3 2.75 s |
| shot_room_duct_0 | 0.60 | -8.0 | -26.4 | 18.4 | -6.8 | +2.9 | -7.6 | -19.7 | L/R corr +0.13; decay T20x3 0.65 s |
| shot_room_duct_1 | 0.60 | -8.0 | -26.2 | 18.2 | -8.2 | -1.0 | -11.5 | -23.2 | L/R corr -0.08; decay T20x3 0.59 s |
| shot_room_supp_small_0 | 0.75 | -17.7 | -36.7 | 19.0 | -4.8 | +7.4 | -9.2 | -30.9 | L/R corr -0.19; decay T20x3 0.63 s |
| shot_room_supp_small_1 | 0.75 | -18.2 | -34.5 | 16.2 | -3.0 | +5.1 | -9.6 | -29.3 | L/R corr +0.35; decay T20x3 0.60 s |
| shot_room_supp_medium_0 | 1.35 | -17.9 | -33.9 | 16.0 | -8.5 | +5.0 | -9.7 | -30.9 | L/R corr -0.00; decay T20x3 0.97 s |
| shot_room_supp_medium_1 | 1.35 | -18.4 | -34.5 | 16.1 | -8.3 | +4.4 | -10.2 | -28.5 | L/R corr +0.18; decay T20x3 0.94 s |
| shot_room_supp_large_0 | 2.70 | -18.9 | -33.2 | 14.3 | -5.8 | +6.1 | -8.3 | -28.7 | L/R corr +0.08; decay T20x3 2.05 s |
| shot_room_supp_large_1 | 2.70 | -20.1 | -34.6 | 14.5 | -7.8 | +3.5 | -8.4 | -26.1 | L/R corr +0.06; decay T20x3 2.03 s |
| shot_room_supp_huge_0 | 3.50 | -19.4 | -35.6 | 16.2 | -4.8 | +7.6 | -7.5 | -26.6 | L/R corr +0.01; decay T20x3 2.79 s |
| shot_room_supp_huge_1 | 3.50 | -17.9 | -33.0 | 15.2 | -8.9 | +6.9 | -8.4 | -25.1 | L/R corr +0.13; decay T20x3 2.72 s |
| shot_room_supp_duct_0 | 0.60 | -16.6 | -36.5 | 19.9 | -9.1 | +0.4 | -12.7 | -33.8 | L/R corr +0.10; decay T20x3 0.59 s |
| shot_room_supp_duct_1 | 0.60 | -16.2 | -35.5 | 19.3 | -8.3 | -0.3 | -14.6 | -32.5 | L/R corr +0.09; decay T20x3 0.55 s |
| shot_slap_0 | 0.20 | -6.0 | -27.6 | 21.6 | -50.8 | -6.9 | -5.3 | -29.2 |  |
| shot_slap_1 | 0.20 | -6.0 | -26.4 | 20.4 | -54.3 | -6.7 | -5.1 | -24.7 |  |
| shot_slap_2 | 0.20 | -6.0 | -28.3 | 22.3 | -50.2 | -7.5 | -6.2 | -26.2 |  |
| shot_slap_supp_0 | 0.20 | -15.0 | -36.6 | 21.6 | -69.0 | -0.5 | -7.7 | -38.8 |  |
| shot_slap_supp_1 | 0.20 | -13.5 | -35.4 | 21.9 | -74.1 | -5.0 | -7.2 | -39.3 |  |
| shot_slap_supp_2 | 0.20 | -15.0 | -37.3 | 22.2 | -70.1 | -7.9 | -5.7 | -42.5 |  |

## Room impulse responses as built

| room | first-order reflections, ms after the direct sound | IR RT60 (T20x3, 400-2000 Hz) |
|---|---|---|
| small_0 | 4.6, 6.3, 7.6, 9.9, 10.5 | 0.44 s |
| small_1 | 4.9, 6.8, 7.3, 7.4, 9.5 | 0.46 s |
| medium_0 | 7.8, 10.6, 11.3, 14.3, 34.9 | 0.92 s |
| medium_1 | 7.5, 9.6, 11.6, 15.3, 36.4 | 0.90 s |
| large_0 | 45.1, 48.4, 64.9, 65.3, 106.4 | 2.01 s |
| large_1 | 45.1, 50.9, 62.4, 79.3, 92.4 | 2.05 s |
| huge_0 | 69.0, 69.4, 75.2, 78.9, 84.8 | 2.75 s |
| huge_1 | 69.0, 70.8, 72.5, 77.6, 87.4 | 2.67 s |
| duct_0 | 0.6, 1.0, 1.0, 1.2, 15.2 | 0.38 s |
| duct_1 | 0.7, 0.9, 1.1, 1.1, 16.6 | 0.38 s |

## Output files

### rifle_close_0.wav
- source: synthesized
- processing: Free Firearm Sound Library AR-15 near-distance shot (left mic, direct sound only, 0.30 s, varispeed x1.000) as the real transient/blast texture; synthesized layers: supersonic crack (HP 2.2 kHz noise, 0.8 ms), Friedlander muzzle-blast pulse, low-mid body (250->112 Hz swept sine + 110-430 Hz noise, 50-60 ms), mid bark (formant noise 640/1080/1720 Hz, 46 ms), sub thump (88->47 Hz), gas hiss, short dry 105 ms noise tail; measured-target mastering: 4 broad EQ bands + density stage (look-ahead limiter + tanh) iterated until band levels and crest factor match the targets; HP 28 Hz; peak -1 dBFS

### rifle_close_1.wav
- source: synthesized
- processing: Free Firearm Sound Library AR-15 near-distance shot (left mic, direct sound only, 0.30 s, varispeed x0.975) as the real transient/blast texture; synthesized layers: supersonic crack (HP 2.2 kHz noise, 0.8 ms), Friedlander muzzle-blast pulse, low-mid body (250->112 Hz swept sine + 110-430 Hz noise, 50-60 ms), mid bark (formant noise 640/1080/1720 Hz, 46 ms), sub thump (88->47 Hz), gas hiss, short dry 105 ms noise tail; measured-target mastering: 4 broad EQ bands + density stage (look-ahead limiter + tanh) iterated until band levels and crest factor match the targets; HP 28 Hz; peak -1 dBFS

### rifle_close_2.wav
- source: synthesized
- processing: Free Firearm Sound Library AR-15 near-distance shot (left mic, direct sound only, 0.30 s, varispeed x1.028) with the SKS near shot (U_14P.wav) blended under it at -5 dB as the real transient/blast texture; synthesized layers: supersonic crack (HP 2.2 kHz noise, 0.8 ms), Friedlander muzzle-blast pulse, low-mid body (250->112 Hz swept sine + 110-430 Hz noise, 50-60 ms), mid bark (formant noise 640/1080/1720 Hz, 46 ms), sub thump (88->47 Hz), gas hiss, short dry 105 ms noise tail; measured-target mastering: 4 broad EQ bands + density stage (look-ahead limiter + tanh) iterated until band levels and crest factor match the targets; HP 28 Hz; peak -1 dBFS

### rifle_close_3.wav
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/SKS/U_14P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- processing: Free Firearm Sound Library AR-15 near-distance shot (left mic, direct sound only, 0.30 s, varispeed x1.012) with the SKS near shot (U_14P.wav) blended under it at -5 dB as the real transient/blast texture; synthesized layers: supersonic crack (HP 2.2 kHz noise, 0.8 ms), Friedlander muzzle-blast pulse, low-mid body (250->112 Hz swept sine + 110-430 Hz noise, 50-60 ms), mid bark (formant noise 640/1080/1720 Hz, 46 ms), sub thump (88->47 Hz), gas hiss, short dry 105 ms noise tail; measured-target mastering: 4 broad EQ bands + density stage (look-ahead limiter + tanh) iterated until band levels and crest factor match the targets; HP 28 Hz; peak -1 dBFS

### rifle_supp_close_0.wav
- source: synthesized
- processing: NOT a filtered copy of the open shot - its own layer stack: reduced bullet crack (first 2 ms of the Free Firearm Sound Library AR-15 shot high-passed at 2.4 kHz + 0.6 ms synthesized snap), suppressor thud/pop (335->150 Hz swept sine, 30 ms; can resonances 545/905 Hz), low body (178->104 Hz, 38 ms), the recording's 170-1500 Hz blast texture with a softened 1.2 ms attack, gas chuff (340-1350 Hz noise 50 ms + 1.3-3.3 kHz noise 21 ms, 2-3 ms attack), small sub; varispeed/pitch x1.000; measured-target mastering (EQ + limiter/tanh density stage); level set so RMS(400 ms) is 8.1 dB under the mean of rifle_close_*

### rifle_supp_close_1.wav
- source: synthesized
- processing: NOT a filtered copy of the open shot - its own layer stack: reduced bullet crack (first 2 ms of the Free Firearm Sound Library AR-15 shot high-passed at 2.4 kHz + 0.6 ms synthesized snap), suppressor thud/pop (335->150 Hz swept sine, 30 ms; can resonances 545/905 Hz), low body (178->104 Hz, 38 ms), the recording's 170-1500 Hz blast texture with a softened 1.2 ms attack, gas chuff (340-1350 Hz noise 50 ms + 1.3-3.3 kHz noise 21 ms, 2-3 ms attack), small sub; varispeed/pitch x0.975; measured-target mastering (EQ + limiter/tanh density stage); level set so RMS(400 ms) is 8.1 dB under the mean of rifle_close_*

### rifle_supp_close_2.wav
- source: synthesized
- processing: NOT a filtered copy of the open shot - its own layer stack: reduced bullet crack (first 2 ms of the Free Firearm Sound Library AR-15 shot high-passed at 2.4 kHz + 0.6 ms synthesized snap), suppressor thud/pop (335->150 Hz swept sine, 30 ms; can resonances 545/905 Hz), low body (178->104 Hz, 38 ms), the recording's 170-1500 Hz blast texture with a softened 1.2 ms attack, gas chuff (340-1350 Hz noise 50 ms + 1.3-3.3 kHz noise 21 ms, 2-3 ms attack), small sub; varispeed/pitch x1.028; measured-target mastering (EQ + limiter/tanh density stage); level set so RMS(400 ms) is 8.1 dB under the mean of rifle_close_*

### rifle_supp_close_3.wav
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/SKS/U_14P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- processing: NOT a filtered copy of the open shot - its own layer stack: reduced bullet crack (first 2 ms of the Free Firearm Sound Library AR-15 shot high-passed at 2.4 kHz + 0.6 ms synthesized snap), suppressor thud/pop (335->150 Hz swept sine, 30 ms; can resonances 545/905 Hz), low body (178->104 Hz, 38 ms), the recording's 170-1500 Hz blast texture with a softened 1.2 ms attack, gas chuff (340-1350 Hz noise 50 ms + 1.3-3.3 kHz noise 21 ms, 2-3 ms attack), small sub; varispeed/pitch x1.012; measured-target mastering (EQ + limiter/tanh density stage); level set so RMS(400 ms) is 8.1 dB under the mean of rifle_close_*

### pistol_close_0.wav
- source: synthesized
- processing: Free Firearm Sound Library Walther PPQ 9 mm near-distance shot (left mic, direct sound, varispeed x1.000); synthesized layers: crack with air (HP 2.8 kHz, 0.7 ms + HP 5.2 kHz hiss 17 ms), short Friedlander blast pulse, body (330->188 Hz swept sine 33 ms + 140-430 Hz noise), higher bark (formants 940/1520/2380 Hz, 30 ms), small sub (112->62 Hz); measured-target mastering (EQ + limiter/tanh density stage); peak -1 dBFS

### pistol_close_1.wav
- source: synthesized
- processing: Free Firearm Sound Library Walther PPQ 9 mm near-distance shot (left mic, direct sound, varispeed x0.972); synthesized layers: crack with air (HP 2.8 kHz, 0.7 ms + HP 5.2 kHz hiss 17 ms), short Friedlander blast pulse, body (330->188 Hz swept sine 33 ms + 140-430 Hz noise), higher bark (formants 940/1520/2380 Hz, 30 ms), small sub (112->62 Hz); measured-target mastering (EQ + limiter/tanh density stage); peak -1 dBFS

### pistol_close_2.wav
- source: synthesized
- processing: Free Firearm Sound Library Walther PPQ 9 mm near-distance shot (left mic, direct sound, varispeed x1.026); synthesized layers: crack with air (HP 2.8 kHz, 0.7 ms + HP 5.2 kHz hiss 17 ms), short Friedlander blast pulse, body (330->188 Hz swept sine 33 ms + 140-430 Hz noise), higher bark (formants 940/1520/2380 Hz, 30 ms), small sub (112->62 Hz); measured-target mastering (EQ + limiter/tanh density stage); peak -1 dBFS

### pistol_close_3.wav
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/Walther PPQ/X_39P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/Carl Gustav M45/G_31P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- processing: Free Firearm Sound Library Walther PPQ 9 mm near-distance shot (left mic, direct sound, varispeed x1.014) with a Carl Gustav M45 9 mm near shot blended under it at -6 dB; synthesized layers: crack with air (HP 2.8 kHz, 0.7 ms + HP 5.2 kHz hiss 17 ms), short Friedlander blast pulse, body (330->188 Hz swept sine 33 ms + 140-430 Hz noise), higher bark (formants 940/1520/2380 Hz, 30 ms), small sub (112->62 Hz); measured-target mastering (EQ + limiter/tanh density stage); peak -1 dBFS

### rifle_mech_0.wav
- source: "Shotgun Reload Sound effects" by zer0_sol, file `ShotgunSounds/Shell in Chamber.mp3` - https://opengameart.org/content/shotgun-reload-sound-effects - CC0
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect - CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalLatch.ogg` - https://opengameart.org/content/50-rpg-sound-effects - CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_spring_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx - CC0
- source: "Metal Impact Sounds" by BMacZero, file `clink2.wav` - https://opengameart.org/content/metal-impact-sounds - CC0
- processing: bolt-carrier cycle: zer0sol 'Shotgun Reload' action impact (CC0, 1.11 s event, x0.95) as the carrier hitting the buffer at t=0; rubberduck 'metal_spring_01' (CC0, real spring) + synthesized chirped buffer-spring twang; zer0sol 'Handgun Reload' slide slam (CC0, x0.86) as the carrier going into battery at 50 ms with Kenney 'metalLatch' (CC0) as the bolt lock; faint case-ejection clink at 108 ms (BMacZero 'clink2' x2.3 + synthesized brass modes 4.3-9.3 kHz); synthesized receiver 'clack' body (modes 430-1900 Hz, 5-7 ms) under both impacts; HP 170 Hz, +1 dB 3.5 kHz, -3 dB shelf above 7 kHz (energy stays centred at 2-8 kHz, where the suppressed shot is weakest); no reverb; peak -6 dBFS

### rifle_mech_1.wav
- source: "Shotgun Reload Sound effects" by zer0_sol, file `ShotgunSounds/Shell in Chamber.mp3` - https://opengameart.org/content/shotgun-reload-sound-effects - CC0
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect - CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalLatch.ogg` - https://opengameart.org/content/50-rpg-sound-effects - CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_spring_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx - CC0
- source: "Metal Impact Sounds" by BMacZero, file `clink2.wav` - https://opengameart.org/content/metal-impact-sounds - CC0
- processing: bolt-carrier cycle: zer0sol 'Shotgun Reload' action impact (CC0, 1.11 s event, x0.92) as the carrier hitting the buffer at t=0; rubberduck 'metal_spring_01' (CC0, real spring) + synthesized chirped buffer-spring twang; zer0sol 'Handgun Reload' slide slam (CC0, x0.83) as the carrier going into battery at 54 ms with Kenney 'metalLatch' (CC0) as the bolt lock; faint case-ejection clink at 121 ms (BMacZero 'clink2' x2.3 + synthesized brass modes 4.3-9.3 kHz); synthesized receiver 'clack' body (modes 430-1900 Hz, 5-7 ms) under both impacts; HP 170 Hz, +1 dB 3.5 kHz, -3 dB shelf above 7 kHz (energy stays centred at 2-8 kHz, where the suppressed shot is weakest); no reverb; peak -6 dBFS

### rifle_mech_2.wav
- source: "Shotgun Reload Sound effects" by zer0_sol, file `ShotgunSounds/Shell in Chamber.mp3` - https://opengameart.org/content/shotgun-reload-sound-effects - CC0
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect - CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalLatch.ogg` - https://opengameart.org/content/50-rpg-sound-effects - CC0
- source: "100 CC0 metal and wood SFX" by rubberduck, file `metal_spring_01.ogg` - https://opengameart.org/content/100-cc0-metal-and-wood-sfx - CC0
- source: "Metal Impact Sounds" by BMacZero, file `clink2.wav` - https://opengameart.org/content/metal-impact-sounds - CC0
- processing: bolt-carrier cycle: zer0sol 'Shotgun Reload' action impact (CC0, 1.11 s event, x0.98) as the carrier hitting the buffer at t=0; rubberduck 'metal_spring_01' (CC0, real spring) + synthesized chirped buffer-spring twang; zer0sol 'Handgun Reload' slide slam (CC0, x0.89) as the carrier going into battery at 47 ms with Kenney 'metalLatch' (CC0) as the bolt lock; faint case-ejection clink at 99 ms (BMacZero 'clink2' x2.3 + synthesized brass modes 4.3-9.3 kHz); synthesized receiver 'clack' body (modes 430-1900 Hz, 5-7 ms) under both impacts; HP 170 Hz, +1 dB 3.5 kHz, -3 dB shelf above 7 kHz (energy stays centred at 2-8 kHz, where the suppressed shot is weakest); no reverb; peak -6 dBFS

### pistol_mech_0.wav
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect - CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalClick.ogg` - https://opengameart.org/content/50-rpg-sound-effects - CC0
- source: "Metal Impact Sounds" by BMacZero, file `clink2.wav` - https://opengameart.org/content/metal-impact-sounds - CC0
- processing: slide cycle: zer0sol 'Handgun Reload' (CC0) slide rear-stop impact (1.11 s, x1.08) as the slide hitting its rear stop at t=0 and the slide-release slam (1.18 s, x1.06) as the slide returning to battery at 40 ms; Kenney 'metalClick' (CC0) tick; faint case clink at 82 ms (BMacZero 'clink2' x2.6 + synthesized brass modes); synthesized slide 'clack' body (modes 540-2500 Hz) under both impacts; HP 220 Hz, -3 dB shelf above 7 kHz; no reverb; peak -6 dBFS

### pistol_mech_1.wav
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect - CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalClick.ogg` - https://opengameart.org/content/50-rpg-sound-effects - CC0
- source: "Metal Impact Sounds" by BMacZero, file `clink2.wav` - https://opengameart.org/content/metal-impact-sounds - CC0
- processing: slide cycle: zer0sol 'Handgun Reload' (CC0) slide rear-stop impact (1.11 s, x1.12) as the slide hitting its rear stop at t=0 and the slide-release slam (1.18 s, x1.10) as the slide returning to battery at 37 ms; Kenney 'metalClick' (CC0) tick; faint case clink at 76 ms (BMacZero 'clink2' x2.6 + synthesized brass modes); synthesized slide 'clack' body (modes 540-2500 Hz) under both impacts; HP 220 Hz, -3 dB shelf above 7 kHz; no reverb; peak -6 dBFS

### pistol_mech_2.wav
- source: "Handgun Reload Sound Effect" by zer0_sol, file `reload.wav` - https://opengameart.org/content/handgun-reload-sound-effect - CC0
- source: "50 RPG sound effects" by Kenney, file `OGG/metalClick.ogg` - https://opengameart.org/content/50-rpg-sound-effects - CC0
- source: "Metal Impact Sounds" by BMacZero, file `clink2.wav` - https://opengameart.org/content/metal-impact-sounds - CC0
- processing: slide cycle: zer0sol 'Handgun Reload' (CC0) slide rear-stop impact (1.11 s, x1.05) as the slide hitting its rear stop at t=0 and the slide-release slam (1.18 s, x1.03) as the slide returning to battery at 43 ms; Kenney 'metalClick' (CC0) tick; faint case clink at 90 ms (BMacZero 'clink2' x2.6 + synthesized brass modes); synthesized slide 'clack' body (modes 540-2500 Hz) under both impacts; HP 220 Hz, -3 dB shelf above 7 kHz; no reverb; peak -6 dBFS

### shot_room_small_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_0 convolved with a synthesized stereo impulse response of a 3.3x4.3x2.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 5/6/8/10/10 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.46 s; measured T20x3 of the IR 0.44 s); HP 70 Hz; peak -8 dBFS

### shot_room_small_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_1 convolved with a synthesized stereo impulse response of a 3.3x4.3x2.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 5/7/7/7/10 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.46 s; measured T20x3 of the IR 0.46 s); HP 70 Hz; peak -8 dBFS

### shot_room_medium_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_0 convolved with a synthesized stereo impulse response of a 4.8x15.0x3.8 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 8/11/11/14/35 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.92 s; measured T20x3 of the IR 0.92 s); HP 70 Hz; peak -8 dBFS

### shot_room_medium_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_1 convolved with a synthesized stereo impulse response of a 4.8x15.0x3.8 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 8/10/12/15/36 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.92 s; measured T20x3 of the IR 0.90 s); HP 70 Hz; peak -8 dBFS

### shot_room_large_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_0 convolved with a synthesized stereo impulse response of a 20.0x30.0x9.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 45/48/65/65/106 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.05 s; measured T20x3 of the IR 2.01 s); HP 70 Hz; peak -8 dBFS

### shot_room_large_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_1 convolved with a synthesized stereo impulse response of a 20.0x30.0x9.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 45/51/62/79/92 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.05 s; measured T20x3 of the IR 2.05 s); HP 70 Hz; peak -8 dBFS

### shot_room_huge_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_0 convolved with a synthesized stereo impulse response of a 26.0x28.0x13.7 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 69/69/75/79/85 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.80 s; measured T20x3 of the IR 2.75 s); HP 70 Hz; peak -8 dBFS

### shot_room_huge_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_1 convolved with a synthesized stereo impulse response of a 26.0x28.0x13.7 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 69/71/72/78/87 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.80 s; measured T20x3 of the IR 2.67 s); HP 70 Hz; peak -8 dBFS

### shot_room_duct_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_0 convolved with a synthesized stereo impulse response of a 0.8x7.0x0.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 1/1/1/1/15 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.36 s; measured T20x3 of the IR 0.38 s), plus inharmonic sheet-metal panel modes (210 Hz-5 kHz, 25-70 ms); HP 70 Hz; peak -8 dBFS

### shot_room_duct_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_close_1 convolved with a synthesized stereo impulse response of a 0.8x7.0x0.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 1/1/1/1/17 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.36 s; measured T20x3 of the IR 0.38 s), plus inharmonic sheet-metal panel modes (210 Hz-5 kHz, 25-70 ms); HP 70 Hz; peak -8 dBFS

### shot_room_supp_small_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_0 convolved with a synthesized stereo impulse response of a 3.3x4.3x2.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 5/6/8/10/10 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.46 s; measured T20x3 of the IR 0.44 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_small_0

### shot_room_supp_small_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_1 convolved with a synthesized stereo impulse response of a 3.3x4.3x2.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 5/7/7/7/10 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.46 s; measured T20x3 of the IR 0.46 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_small_1

### shot_room_supp_medium_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_0 convolved with a synthesized stereo impulse response of a 4.8x15.0x3.8 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 8/11/11/14/35 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.92 s; measured T20x3 of the IR 0.92 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_medium_0

### shot_room_supp_medium_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_1 convolved with a synthesized stereo impulse response of a 4.8x15.0x3.8 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 8/10/12/15/36 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.92 s; measured T20x3 of the IR 0.90 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_medium_1

### shot_room_supp_large_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_0 convolved with a synthesized stereo impulse response of a 20.0x30.0x9.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 45/48/65/65/106 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.05 s; measured T20x3 of the IR 2.01 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_large_0

### shot_room_supp_large_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_1 convolved with a synthesized stereo impulse response of a 20.0x30.0x9.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 45/51/62/79/92 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.05 s; measured T20x3 of the IR 2.05 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_large_1

### shot_room_supp_huge_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_0 convolved with a synthesized stereo impulse response of a 26.0x28.0x13.7 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 69/69/75/79/85 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.80 s; measured T20x3 of the IR 2.75 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_huge_0

### shot_room_supp_huge_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_1 convolved with a synthesized stereo impulse response of a 26.0x28.0x13.7 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption, first-order floor bounce omitted (it merges with the dry shot); first-order reflections at 69/71/72/78/87 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 2.80 s; measured T20x3 of the IR 2.67 s); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_huge_1

### shot_room_supp_duct_0.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_0 convolved with a synthesized stereo impulse response of a 0.8x7.0x0.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 1/1/1/1/15 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.36 s; measured T20x3 of the IR 0.38 s), plus inharmonic sheet-metal panel modes (210 Hz-5 kHz, 25-70 ms); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_duct_0

### shot_room_supp_duct_1.wav
- source: synthesized
- processing: wet-only room response (no direct sound): rifle_supp_close_1 convolved with a synthesized stereo impulse response of a 0.8x7.0x0.6 m shoebox (image-source early reflections for two ear positions 18 cm apart with head-shadow gain, per-order HF absorption; first-order reflections at 1/1/1/1/17 ms after the direct sound) cross-faded into a diffuse tail (independent noise per ear, 9 octave bands with their own decay, mid RT60 0.36 s; measured T20x3 of the IR 0.38 s), plus inharmonic sheet-metal panel modes (210 Hz-5 kHz, 25-70 ms); HP 70 Hz, LP 6.5 kHz; level = the open-shot version's gain structure with RMS set 10 dB below shot_room_duct_1

### shot_slap_0.wav
- source: synthesized
- processing: one early wall reflection: rifle_close_1 band-limited 250-5000 Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; peak -6 dBFS

### shot_slap_1.wav
- source: synthesized
- processing: one early wall reflection: rifle_close_2 band-limited 250-5000 Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; peak -6 dBFS

### shot_slap_2.wav
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/SKS/U_14P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- processing: one early wall reflection: rifle_close_3 band-limited 250-5000 Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; peak -6 dBFS

### shot_slap_supp_0.wav
- source: synthesized
- processing: one early wall reflection: rifle_supp_close_1 band-limited 250-3600 Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; RMS 9 dB below the matching open slap (peak about -14 dBFS)

### shot_slap_supp_1.wav
- source: synthesized
- processing: one early wall reflection: rifle_supp_close_2 band-limited 250-3600 Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; RMS 9 dB below the matching open slap (peak about -14 dBFS)

### shot_slap_supp_2.wav
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/AR-15/D_32P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- source: "The Free Firearm Sound Library" by Ben Jaszczak, et al. (Submitted by bart ), file `Prepared SFX Library/SKS/U_14P.wav` - https://opengameart.org/content/the-free-firearm-sound-library - CC0
- processing: one early wall reflection: rifle_supp_close_3 band-limited 250-3600 Hz (4-pole each side), scattered by a rough-wall micro-diffusion kernel (7 taps within 2.6 ms), -1.5 dB shelf at 3 kHz, envelope shortened (tau 55 ms) to 0.2 s; mono, no sub; RMS 9 dB below the matching open slap (peak about -14 dBFS)

