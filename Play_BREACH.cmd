@echo off
rem Launches Relay Nine: BREACH with Godot 4.7.2.
rem   Play_BREACH.cmd [--quality=0..3]   Low, Medium, High, Ultra
rem   Play_BREACH.cmd --find-godot       print the Godot it would use, then exit
rem
rem Godot 4.7.2 is looked for in this order; the first match of that version wins:
rem   1. ..\tools\godot\ next to this folder (portable install)
rem   2. PATH: Godot_v4.7.2-stable_win64.exe, its _console variant, godot.exe
rem   3. winget package folders (per-user, then machine-wide)
setlocal EnableExtensions DisableDelayedExpansion
set "WANT=4.7.2.stable"
set "EXE=Godot_v4.7.2-stable_win64.exe"
set "CEXE=Godot_v4.7.2-stable_win64_console.exe"
set "GODOT="
set "CHECKED="
for %%I in ("%~dp0..\tools\godot") do set "PORTABLE=%%~fI"

rem 1. Portable install (the original layout).
call :try "%PORTABLE%\%EXE%"
call :try "%PORTABLE%\%CEXE%"

rem 2. PATH.
for %%N in ("%EXE%" "%CEXE%" "godot.exe") do (
  for /f "delims=" %%P in ('where %%~N 2^>nul') do call :try "%%P"
)

rem 3. winget (GodotEngine.GodotEngine package, user and machine scope).
for %%R in ("%LOCALAPPDATA%\Microsoft\WinGet\Packages" "%ProgramFiles%\WinGet\Packages") do (
  for /d %%D in ("%%~R\GodotEngine.GodotEngine_*") do (
    call :try "%%~D\%EXE%"
    call :try "%%~D\%CEXE%"
  )
)

if not defined GODOT goto :notfound

if /i "%~1"=="--find-godot" (
  echo %GODOT%
  exit /b 0
)
rem "%~dp0." avoids the trailing backslash escaping the closing quote.
start "" "%GODOT%" --path "%~dp0." -- %*
exit /b 0

:notfound
echo.
echo  Relay Nine: BREACH needs Godot %WANT:.stable=% (standard build, not .NET).
echo  It was not found in:
echo    - %PORTABLE%\
echo    - PATH
echo    - winget package folders
if defined CHECKED (
  echo  Godot executables found, but with the wrong version:
  call echo %%CHECKED%%
)
echo.
echo  Install it with:
echo    winget install GodotEngine.GodotEngine --version 4.7.2
echo  or put %EXE% in %PORTABLE%\
echo.
if /i not "%~1"=="--find-godot" pause
exit /b 1

rem :try <path> - use <path> if it exists and reports version %WANT%.
:try
if defined GODOT exit /b 0
if not exist "%~1" exit /b 1
set "VER="
for /f "delims=" %%V in ('""%~1" --version 2^>nul"') do if not defined VER set "VER=%%V"
if not defined VER set "VER=unknown"
call set "HEAD=%%VER:~0,12%%"
if /i "%HEAD%"=="%WANT%" (
  set "GODOT=%~f1"
  exit /b 0
)
set "CHECKED=%CHECKED%    %~f1 (%VER%)"
exit /b 1
