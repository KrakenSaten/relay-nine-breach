# BREACH 0.2.0: standalone Windows build (2026-11-23)

**Result: PASS.** One remaining caveat for distribution beyond this PC: the exe is not code-signed.

## Output

| Item | Value |
| --- | --- |
| Executable | `C:\AAA\Breach\dist\BREACH\Breach.exe` (Windows x64, release template, game data embedded) |
| Executable size | 568,525,784 bytes (542.2 MiB) |
| Distribution folder | `dist/BREACH/`, 542.4 MiB total: `Breach.exe`, `README.txt`, `CREDITS.txt`, `GODOT_LICENSE.txt`, `GODOT_COPYRIGHT.txt` |
| SHA-256 | `6f83afe84a825453ba1ded22f1afb8498c88c6b54d50c031526c0c24324cb016` |
| Version info | Product "Relay Nine: BREACH", file/product version 0.2.0.0, description, copyright set; app icon embedded (16–256 px .ico) |
| Engine / templates | Godot 4.7.2-stable. Official export templates from github.com/godotengine/godot releases, SHA-512 verified against the published SHA512-SUMS.txt |

Package contents: 632 files. The largest share is VRAM-compressed textures (BPTC/S3TC, about 441 MB), then scenes (about 16 MB) and QOA-compressed audio (about 2 MB). All 50 model scenes and all 80 sounds are included.
**Excluded from the release:** `captures/`, `staging/`, `tools/`, `docs/`, `branding/`, `scripts/test/` (the automated test harness), `*.md`, `*.cmd`, `*.py`. Verified by parsing the embedded PCK: no development files are present.

## Runtime dependencies

* Windows 10/11 x64.
* A GPU with Vulkan drivers (Forward+ renderer). The D3D12 fallback DLLs were not bundled.
* Nothing else: no VC++ redistributable and no .NET. The engine is statically linked.
* Measured footprint: about 1.45 GB working set at the briefing screen on the test PC.

## Validation (focused; exported binaries only, run from a folder outside the project)

Two presets are exported from the same project and templates. **Windows Release** is the shipped exe. **Windows Validation** is identical except that it includes the test harness (3 extra files), so the exported build can be driven automatically. The validation build is not shipped.

| Check | Release exe (no args) | Validation exe (`--autotest`) |
| --- | --- | --- |
| Launches without editor or project files | PASS. Title "Relay Nine: BREACH" (no DEBUG), responding, briefing rendered | PASS. Release template, `debug=false`, no `project.godot` beside the exe |
| Clean exit | PASS, exit code 0 | PASS, exit code 0 |
| Log | 0 errors / 0 warnings | 0 errors / 0 warnings |
| Renderer | — | Vulkan, Intel Arc B580 |
| Audio | — | WASAPI, default device; 30/30 sound families load |
| Settings | — | Low→High switch reaches the renderer: scale 0.77→1.00, SDFGI off→on, TAA on |
| Weapons | — | ADS alignment exact; scripted engagement kills; capacitor shot kills and overloads |
| Teslabots | — | 6 units into combat, 42 telegraphed windups, cover/flank/assault roles, peeking |
| Night vision | — | On, battery draining |
| Mission | — | Connect → HACK → EXTRACT (D6 unsealed) → lift → COMPLETE |

## Defects found and fixed during export validation

1. **Crash on quit (0xC0000374 heap corruption)** in the exported build. Out-of-tree template nodes (a `static` attachment root in `Weapon`, and the prop/kit source scenes) were only released during engine teardown. They are now freed deterministically, and the exit code is 0.
2. **Error spam (about 1,100 errors per pistol reload).** A missing magazine hand-socket was cached as `null` metadata, which Godot treats as deleting the key. It is now cached in a dictionary.
3. A missing window icon at runtime (the icon file had been excluded). The icon moved to `res://icon.ico` and is included.
4. A transient FSR2/TAA warning when switching presets. The upscaler is now applied before TAA.
5. The FPS counter now defaults to off for players (F3 toggles it).

## Remaining release blockers / caveats

* **Not code-signed.** On other PCs, Windows SmartScreen will warn on first run. Signing needs a certificate (the owner's decision).
* **Tested on one machine only** (Arc B580). Not tried on other GPU vendors, Vulkan-less systems, or other resolutions and DPI settings.
* **Size.** 542 MiB, mostly 2k textures. Capping non-hero textures at 1k would roughly halve it if download size matters.
* No installer or uninstaller. The game is a portable exe, and settings live in `%APPDATA%\Godot\app_userdata\Relay Nine- BREACH\`.

## Rebuild

```powershell
& C:\AAA\tools\godot\Godot_v4.7.2-stable_win64_console.exe --headless --path C:\AAA\Breach --export-release "Windows Release" dist/BREACH/Breach.exe
```
