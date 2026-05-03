@echo off
setlocal EnableExtensions EnableDelayedExpansion

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

for %%E in (mov mp4 m4v avi mkv webm) do (
    for /r "%MOVIES_DIR%" %%F in (*.%%E) do (
        set "FOUND_VIDEO=1"
        set "VIDEO=%%~fF"
        set "GIF=%%~dpnF.gif"
        set "PALETTE=%%~dpnF_palette.png"

        echo Converting:
        echo   %%~fF

        ffmpeg -y -i "%%~fF" -vf "fps=15,scale=iw:-1:flags=lanczos,palettegen=stats_mode=diff" -frames:v 1 -update 1 "!PALETTE!"
        if errorlevel 1 (
            echo Failed to generate palette for:
            echo   %%~fF
            echo.
        ) else (
            ffmpeg -y -i "%%~fF" -i "!PALETTE!" -lavfi "fps=15,scale=iw:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a" "!GIF!"
            if errorlevel 1 (
                echo Failed to create GIF for:
                echo   %%~fF
            )
        )

        if exist "!PALETTE!" del /q "!PALETTE!"
        echo.
    )
)

if "%FOUND_VIDEO%"=="0" (
    echo No videos found in %MOVIES_DIR%
) else (
    echo Finished converting videos to GIF.
)

endlocal
pause