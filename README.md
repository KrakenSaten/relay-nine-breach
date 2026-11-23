# Relay Nine: BREACH — Vertical Slice 0.1

Singleplayer close-quarters tactical FPS set in the Relay Nine universe. One
indoor mission at Substation 9-B: infiltrate, connect the relay override, defend
the upload against Teslabot security units, extract.

## Run

```powershell
.\Play_BREACH.cmd
```

This needs Godot 4.7.2 at `C:\AAA\tools\godot` (installed with
`winget install GodotEngine.GodotEngine --version 4.7.2`). Graphics presets can
be forced with `.\Play_BREACH.cmd --quality=0` (Low) through `3` (Ultra), or set
in Settings.

### Standalone build

`dist/BREACH/Breach.exe` is a self-contained Windows x64 release (no Godot needed). See
[docs/RELEASE.md](docs/RELEASE.md) for the size, dependencies, validation and rebuild command.

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
* [docs/REPORT_M2.md](docs/REPORT_M2.md): M2 visual overhaul, AI refinement, performance, regression results
* [docs/REPORT.md](docs/REPORT.md): M1 report
* [ASSETS.md](ASSETS.md): every asset source and license
* `captures/`: screenshots and a gameplay clip from the running build
