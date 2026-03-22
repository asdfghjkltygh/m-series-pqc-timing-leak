#!/usr/bin/env python3
"""Render the demo highlight animation as an MP4 video.

Produces a terminal-styled video showing the bar comparison:
62.49 FAIL vs 0.58 PASS. Output is suitable for YouTube upload.

Requires: Pillow, ffmpeg (in PATH)
"""

import subprocess
import struct
import tempfile
import os
from PIL import Image, ImageDraw, ImageFont

# Video settings
WIDTH = 1920
HEIGHT = 1080
FPS = 30
BG_COLOR = (18, 18, 18)  # dark terminal background
DIM_COLOR = (140, 140, 140)
WHITE = (255, 255, 255)
RED = (255, 80, 80)
GREEN = (80, 255, 80)
MAGENTA = (200, 130, 255)

# Try to load a monospace font
FONT_PATHS = [
    "/System/Library/Fonts/SFMono-Regular.otf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.dfont",
    "/Library/Fonts/Courier New.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]

def load_font(size):
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


FONT_LARGE = load_font(36)
FONT_MED = load_font(28)
FONT_SMALL = load_font(22)

BAR_CHAR = "\u2501"  # box drawing heavy horizontal
MAX_BAR_WIDTH = 900  # pixels
BAR_HEIGHT = 32
BAR_Y_FAIL = 440
BAR_Y_PASS = 640
LEFT_MARGIN = 80


def make_frame(texts):
    """Create a frame with the given text elements.

    texts: list of (text, x, y, color, font)
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    for text, x, y, color, font in texts:
        draw.text((x, y), text, fill=color, font=font)
    return img


def frames_for_duration(seconds):
    return int(FPS * seconds)


def generate_frames():
    """Yield (Image, count) tuples for each visual state."""

    # Scene 1: Title fade in (1.5s)
    elements = [
        ("So what did we find?", LEFT_MARGIN, 200, WHITE, FONT_LARGE),
    ]
    yield make_frame(elements), frames_for_duration(2.0)

    # Scene 2: "The mandatory test..." label (0.5s hold before bar)
    elements.append(
        ("The mandatory test, run the standard way:", LEFT_MARGIN, 320, DIM_COLOR, FONT_MED)
    )
    yield make_frame(elements), frames_for_duration(1.0)

    # Scene 3: Animate the red bar growing (1.8s = 54 frames)
    bar_frames = frames_for_duration(1.8)
    for i in range(1, bar_frames + 1):
        frac = i / bar_frames
        bar_w = int(MAX_BAR_WIDTH * frac)
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)
        # Redraw static text
        draw.text((LEFT_MARGIN, 200), "So what did we find?", fill=WHITE, font=FONT_LARGE)
        draw.text((LEFT_MARGIN, 320), "The mandatory test, run the standard way:", fill=DIM_COLOR, font=FONT_MED)
        # Draw bar
        draw.rectangle(
            [LEFT_MARGIN, BAR_Y_FAIL, LEFT_MARGIN + bar_w, BAR_Y_FAIL + BAR_HEIGHT],
            fill=RED,
        )
        yield img, 1

    # Scene 4: Show score on the red bar (2s hold)
    def draw_full_red(img_or_none=None):
        img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
        draw = ImageDraw.Draw(img)
        draw.text((LEFT_MARGIN, 200), "So what did we find?", fill=WHITE, font=FONT_LARGE)
        draw.text((LEFT_MARGIN, 320), "The mandatory test, run the standard way:", fill=DIM_COLOR, font=FONT_MED)
        draw.rectangle(
            [LEFT_MARGIN, BAR_Y_FAIL, LEFT_MARGIN + MAX_BAR_WIDTH, BAR_Y_FAIL + BAR_HEIGHT],
            fill=RED,
        )
        draw.text((LEFT_MARGIN + MAX_BAR_WIDTH + 20, BAR_Y_FAIL - 4), "62.49", fill=RED, font=FONT_LARGE)
        draw.text((LEFT_MARGIN + MAX_BAR_WIDTH + 140, BAR_Y_FAIL - 4), "FAIL", fill=RED, font=FONT_LARGE)
        return img

    yield draw_full_red(), frames_for_duration(2.5)

    # Scene 5: Add "The same test..." label (1s)
    def draw_with_pass_label(bar_w=0, show_score=False):
        img = draw_full_red()
        draw = ImageDraw.Draw(img)
        draw.text(
            (LEFT_MARGIN, 560),
            "sca-triage pairwise decomposition on the same data:",
            fill=DIM_COLOR,
            font=FONT_MED,
        )
        if bar_w > 0:
            draw.rectangle(
                [LEFT_MARGIN, BAR_Y_PASS, LEFT_MARGIN + bar_w, BAR_Y_PASS + BAR_HEIGHT],
                fill=GREEN,
            )
        if show_score:
            draw.text((LEFT_MARGIN + bar_w + 20, BAR_Y_PASS - 4), "0.58", fill=GREEN, font=FONT_LARGE)
            draw.text((LEFT_MARGIN + bar_w + 110, BAR_Y_PASS - 4), "PASS", fill=GREEN, font=FONT_LARGE)
        return img

    yield draw_with_pass_label(), frames_for_duration(1.0)

    # Scene 6: Animate tiny green bar (0.3s)
    small_bar_w = max(8, int(0.58 / 62.49 * MAX_BAR_WIDTH))
    bar_frames_small = frames_for_duration(0.3)
    for i in range(1, bar_frames_small + 1):
        frac = i / bar_frames_small
        bw = int(small_bar_w * frac)
        yield draw_with_pass_label(bar_w=bw, show_score=False), 1

    # Scene 7: Show score on green bar (3s)
    yield draw_with_pass_label(bar_w=small_bar_w, show_score=True), frames_for_duration(3.0)

    # Scene 8: Tagline (3s)
    img = draw_with_pass_label(bar_w=small_bar_w, show_score=True)
    draw = ImageDraw.Draw(img)
    draw.text((LEFT_MARGIN, 780), "Same encryption. Same hardware. Same test.", fill=DIM_COLOR, font=FONT_MED)
    draw.text((LEFT_MARGIN, 820), "The only thing we changed: the order of the measurements.", fill=DIM_COLOR, font=FONT_MED)
    yield img, frames_for_duration(3.0)

    # Scene 9: Closing line (3s)
    draw.text(
        (LEFT_MARGIN, 920),
        "The failure was never real.",
        fill=MAGENTA,
        font=FONT_LARGE,
    )
    draw.text(
        (LEFT_MARGIN, 980),
        "github.com/asdfghjkltygh/m-series-pqc-timing-leak",
        fill=DIM_COLOR,
        font=FONT_SMALL,
    )
    yield img, frames_for_duration(4.0)


def main():
    output_path = os.path.expanduser("~/Downloads/demo_highlight.mp4")

    print(f"Rendering video at {WIDTH}x{HEIGHT} @ {FPS}fps...")

    # Write raw frames to a temp file, then encode with ffmpeg
    with tempfile.NamedTemporaryFile(suffix=".rgb", delete=False) as tmp:
        tmp_path = tmp.name
        total_frames = 0
        for img, count in generate_frames():
            raw = img.tobytes()
            for _ in range(count):
                tmp.write(raw)
                total_frames += 1

    print(f"Rendered {total_frames} frames, encoding with ffmpeg...")

    ffmpeg_cmd = [
        "ffmpeg",
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", tmp_path,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_path,
    ]

    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    os.unlink(tmp_path)

    if result.returncode != 0:
        print(f"ffmpeg error: {result.stderr}")
        return

    duration = total_frames / FPS
    print(f"Done: {duration:.1f}s video")
    print(f"Saved to: {output_path}")


if __name__ == "__main__":
    main()
