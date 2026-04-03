@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "MOVIES_DIR=%SCRIPT_DIR%movies"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo ffmpeg is not installed or not in PATH.
    echo Install it first, then run this script again.
    exit /b 1
)

if not exist "%MOVIES_DIR%" (
    echo Movies folder not found: %MOVIES_DIR%
    exit /b 1
)

set "FOUND_VIDEO=0"

for /r "%MOVIES_DIR%" %%F in (*.mov *.mp4 *.m4v *.avi *.mkv *.webm) do (
    set "FOUND_VIDEO=1"
    set "VIDEO=%%~fF"
    set "GIF=%%~dpnF.gif"
    set "PALETTE=%%~dpnF_palette.png"

    echo Converting:
    echo   %%~fF

    ffmpeg -y -i "%%~fF" -vf "fps=15,scale=iw:-1:flags=lanczos,palettegen=stats_mode=diff" "!PALETTE!" && ^
    ffmpeg -y -i "%%~fF" -i "!PALETTE!" -lavfi "fps=15,scale=iw:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a" "!GIF!"

    if exist "!PALETTE!" del /q "!PALETTE!"
    echo.
)

if "%FOUND_VIDEO%"=="0" (
    echo No videos found in %MOVIES_DIR%
) else (
    echo Finished converting videos to GIF.
)
