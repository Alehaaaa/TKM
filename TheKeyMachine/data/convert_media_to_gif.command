#!/bin/bash

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MOVIES_DIR="$SCRIPT_DIR/movies"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg is not installed or not in PATH."
    echo "Install it first, then run this script again."
    exit 1
fi

if [ ! -d "$MOVIES_DIR" ]; then
    echo "Movies folder not found: $MOVIES_DIR"
    exit 1
fi

found_video=0

while IFS= read -r -d '' video; do
    found_video=1
    gif="${video%.*}.gif"
    palette="${video%.*}_palette.png"

    echo "Converting:"
    echo "  $video"

    ffmpeg -y -i "$video" -vf "fps=15,scale=iw:-1:flags=lanczos,palettegen=stats_mode=diff" "$palette" &&
    ffmpeg -y -i "$video" -i "$palette" -lavfi "fps=15,scale=iw:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=sierra2_4a" "$gif"

    rm -f "$palette"
    echo
done < <(find "$MOVIES_DIR" -type f \( \
    -iname "*.mov" -o \
    -iname "*.mp4" -o \
    -iname "*.m4v" -o \
    -iname "*.avi" -o \
    -iname "*.mkv" -o \
    -iname "*.webm" \) -print0)

if [ "$found_video" -eq 0 ]; then
    echo "No videos found in $MOVIES_DIR"
else
    echo "Finished converting videos to GIF."
fi
