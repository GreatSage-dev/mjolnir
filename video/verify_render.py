import os, subprocess, sys
import numpy as np

FFMPEG = r"C:\Users\HP LAPTOP\Documents\Eliza-keeper\node_modules\ffmpeg-static\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Users\HP LAPTOP\.vscode\extensions\kilocode.kilo-code-7.8.18-win32-x64\bin\ffmpeg.exe"

MP4 = r"c:\Users\HP LAPTOP\Documents\NVIDIA\artifacts\mjolnir_launch_film.mp4"


def main():
    assert os.path.exists(MP4), f"Missing MP4: {MP4}"
    size_mb = os.path.getsize(MP4) / (1024 * 1024)
    assert size_mb > 3.0, f"MP4 unexpectedly small: {size_mb:.2f} MB"

    # Probe streams via ffmpeg -i
    probe = subprocess.run([FFMPEG, "-i", MP4], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    info = probe.stderr.decode("utf-8", "replace")
    assert "1920x1080" in info, f"Expected 1920x1080 in stream info:\n{info}"
    assert "60 fps" in info or "60 tbr" in info, f"Expected 60fps in stream info:\n{info}"
    assert "Audio: aac" in info, f"Expected AAC audio stream:\n{info}"

    # Sample 4fps downscaled raw RGB frames across entire video to verify continuous motion & zero black frames
    raw_cmd = [
        FFMPEG, "-v", "error", "-i", MP4,
        "-vf", "fps=4,scale=160:90",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"
    ]
    raw_proc = subprocess.run(raw_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    frames = np.frombuffer(raw_proc.stdout, dtype=np.uint8).reshape(-1, 90, 160, 3)
    n_f = len(frames)
    assert n_f >= 240, f"Expected >=240 sampled frames (~60s @ 4fps), got {n_f}"

    # Verify zero all-black frames
    means = frames.mean(axis=(1, 2, 3))
    min_brightness = float(means.min())
    assert min_brightness > 8.0, f"Detected unexpected black frame (min brightness={min_brightness:.2f})"

    # Verify zero long static freezes (>1.5s = 6 consecutive identical frames @ 4fps)
    diffs = np.abs(frames[1:].astype(np.float32) - frames[:-1].astype(np.float32)).mean(axis=(1, 2, 3))
    frozen_streak = 0
    max_frozen_streak = 0
    for d in diffs:
        if d < 0.02:
            frozen_streak += 1
            max_frozen_streak = max(max_frozen_streak, frozen_streak)
        else:
            frozen_streak = 0

    assert max_frozen_streak < 6, f"Detected static hold > 1.5s (max_frozen_streak={max_frozen_streak})"

    print(f"[VERIFIED] {MP4}")
    print(f"  Size: {size_mb:.2f} MB | Sampled frames: {n_f} (~{n_f/4:.1f}s) | Min brightness: {min_brightness:.1f} | Max static streak: {max_frozen_streak} frames (@4fps)")


if __name__ == "__main__":
    main()
