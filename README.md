# Relay Nine: BREACH

Singleplayer close-quarters tactical FPS set in the Relay Nine universe, built in
Godot 4.7.2 (Forward+). Current version: 0.4.5 (M4 mission, quality pass, ambience
polish, Operation DEADBAND briefing).

## Requirements

* Windows x64
* Godot 4.7.2-stable (standard build, not .NET):
  `winget install GodotEngine.GodotEngine --version 4.7.2`
* Git LFS (`git lfs install`) for the capture videos
* Optional, for asset generators in `tools/`: Python 3.12+

## Setup

`Play_BREACH.cmd` looks for Godot in `..\tools\godot\`, next to the project folder:

```
<parent>\Breach\                                   this repository
<parent>\tools\godot\Godot_v4.7.2-stable_win64.exe
```

```powershell
git clone https://github.com/KrakenSaten/relay-nine-breach.git Breach
cd Breach
git lfs pull
```

The first run imports all assets into `.godot/` (a few minutes). You can do it up front:

```powershell
..\tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path . --import
```

## Run

```powershell
.\Play_BREACH.cmd
```

Force a graphics preset with `.\Play_BREACH.cmd --quality=0` (Low) through `3`
(Ultra), or set it in Settings. To edit, open `project.godot` in the Godot 4.7.2 editor.

## Build (Windows export)

Install the official Godot 4.7.2 export templates, then:

```powershell
..\tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path . --export-release "Windows Release" dist/BREACH_0.4.5/Breach.exe
```

Presets are in `export_presets.cfg` ("Windows Release", "Windows Validation").
Builds in `dist/` are not stored in Git. See [docs/RELEASE.md](docs/RELEASE.md).

## Controls

| Action | Key |
| --- | --- |
| Move / sprint / crouch / jump | WASD / Shift / Ctrl or C / Space |
| Lean | Q / E |
| Aim / fire / reload / fire mode | RMB / LMB / R / B |
| Rifle / pistol | 1 / 2 / mouse wheel |
| Interact (hold at console) | F |
| Breach (kick) door | V |
| Deploy / pick up shield | G / F |
| Night vision (battery) | N |
| Loadout / pause / FPS counter | T / Esc / F3 |

## Docs

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): systems and design
* [docs/REPORT_M4.md](docs/REPORT_M4.md), [docs/REVIEW_M43.md](docs/REVIEW_M43.md), [docs/REVIEW_M44_AMBIENCE.md](docs/REVIEW_M44_AMBIENCE.md), [docs/REVIEW_M45_BRIEFING.md](docs/REVIEW_M45_BRIEFING.md): M4 mission and 0.4.x passes
* [docs/REPORT_M3.md](docs/REPORT_M3.md): M3 animation, environment, effects, performance, v0.3.0
* [docs/REPORT_M2.md](docs/REPORT_M2.md): M2 visual overhaul, AI refinement, performance, regression results
* [docs/REPORT.md](docs/REPORT.md): M1 report
* [ASSETS.md](ASSETS.md): every asset source and license
* `captures/`: screenshots and a gameplay clip from the running build
