@echo off
rem Launches Relay Nine: BREACH with the bundled Godot 4.7.2 runtime.
rem Optional: Play_BREACH.cmd --quality=0..3   (Low, Medium, High, Ultra)
set GODOT=%~dp0..\tools\godot\Godot_v4.7.2-stable_win64.exe
if not exist "%GODOT%" (
  echo Godot 4.7.2 not found at %GODOT%
  echo Install it with:  winget install GodotEngine.GodotEngine --version 4.7.2
  pause
  exit /b 1
)
rem "%~dp0." avoids the trailing backslash escaping the closing quote.
start "" "%GODOT%" --path "%~dp0." -- %*
