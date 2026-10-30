import base64, concurrent.futures, json, math, os, pathlib, subprocess, time
from playwright.sync_api import sync_playwright

FFMPEG = r"C:\Users\HP LAPTOP\Documents\Eliza-keeper\node_modules\ffmpeg-static\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Users\HP LAPTOP\.vscode\extensions\kilocode.kilo-code-7.8.18-win32-x64\bin\ffmpeg.exe"

VIDEO_DIR = r"c:\Users\HP LAPTOP\Documents\NVIDIA\video"
CHUNKS_DIR = os.path.join(VIDEO_DIR, "chunks")
AUDIO_WAV = os.path.join(VIDEO_DIR, "assets", "audio", "master_audio.wav")
VO_JSON = os.path.join(VIDEO_DIR, "assets", "audio", "voiceover_data.json")
OUT_MP4 = r"c:\Users\HP LAPTOP\Documents\NVIDIA\artifacts\mjolnir_launch_film.mp4"
HTML_URI = pathlib.Path(os.path.join(VIDEO_DIR, "film.html")).as_uri()

FPS = 60
WORKERS = 4
BATCH = 15


def render_chunk(args):
    worker_id, f_start, f_end = args
    os.makedirs(CHUNKS_DIR, exist_ok=True)
    chunk_mp4 = os.path.join(CHUNKS_DIR, f"chunk_{worker_id:02d}.mp4")
    done_flag = os.path.join(CHUNKS_DIR, f"chunk_{worker_id:02d}.done")
    if os.path.exists(chunk_mp4) and os.path.exists(done_flag) and os.path.getsize(chunk_mp4) > 100_000:
        print(f"  [Worker {worker_id}] Reusing completed {chunk_mp4}", flush=True)
        return chunk_mp4
    log_path = os.path.join(CHUNKS_DIR, f"ffmpeg_{worker_id:02d}.log")

    cmd = [
        FFMPEG, "-y",
        "-f", "image2pipe",
        "-vcodec", "mjpeg",
        "-framerate", str(FPS),
        "-i", "pipe:0",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "14",
        "-pix_fmt", "yuv420p",
        chunk_mp4,
    ]

    t0 = time.time()
    with open(log_path, "wb") as log_f:
        # IMPORTANT: stderr goes to file handle — NEVER subprocess.PIPE (prevents 4KB Windows pipe deadlock!)
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_f)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--enable-gpu",
                    "--ignore-gpu-blocklist",
                    "--use-angle=d3d11",
                    "--allow-file-access-from-files",
                    "--disable-web-security",
                ]
            )
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.goto(HTML_URI)
            page.wait_for_function("window.__READY === true", timeout=25000)

            total_w = f_end - f_start
            for f0 in range(f_start, f_end, BATCH):
                f1 = min(f_end, f0 + BATCH)
                times = [round(f / FPS, 6) for f in range(f0, f1)]
                # Render 1 crisp frame per timestamp; native C SIMD ffmpeg tmix blends motion blur in final pass!
                data_urls = page.evaluate(
                    """(times) => {
                        const c = document.getElementById('stage');
                        return times.map(t => {
                            window.seek(t, 1);
                            return c.toDataURL('image/jpeg', 0.92);
                        });
                    }""",
                    times
                )
                for durl in data_urls:
                    proc.stdin.write(base64.b64decode(durl.split(",", 1)[1]))

                done = f1 - f_start
                if done % 240 == 0 or f1 == f_end:
                    el = time.time() - t0
                    print(f"  [Worker {worker_id}] {done}/{total_w} ({100.0*done/total_w:5.1f}%) | {done/max(0.01,el):.1f} fps", flush=True)

            browser.close()

        proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"Worker {worker_id} ffmpeg exited {ret}")

    with open(done_flag, "w") as df:
        df.write(f"{f_start}-{f_end}")
    return chunk_mp4


def main():
    with open(VO_JSON, "r", encoding="utf-8") as f:
        vo = json.load(f)
    duration = float(vo["total_duration"])
    total_frames = int(math.ceil(duration * FPS))
    print(f"Parallel render: {total_frames} frames ({duration:.2f}s @ {FPS}fps) across {WORKERS} workers -> {OUT_MP4}", flush=True)

    os.makedirs(CHUNKS_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(OUT_MP4), exist_ok=True)

    per_worker = math.ceil(total_frames / WORKERS)
    tasks = []
    for w in range(WORKERS):
        s = w * per_worker
        e = min(total_frames, (w + 1) * per_worker)
        if s < e:
            tasks.append((w, s, e))

    t0 = time.time()
    with concurrent.futures.ProcessPoolExecutor(max_workers=WORKERS) as ex:
        chunk_files = list(ex.map(render_chunk, tasks))

    print(f"All {len(chunk_files)} chunks rendered in {time.time() - t0:.1f}s. Applying ffmpeg tmix motion blur + muxing -14 LUFS master audio...", flush=True)

    concat_txt = os.path.join(CHUNKS_DIR, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for cf in chunk_files:
            safe_p = cf.replace("\\", "/")
            f.write(f"file '{safe_p}'\n")

    final_log = os.path.join(CHUNKS_DIR, "ffmpeg_final.log")
    final_cmd = [
        FFMPEG, "-y",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-i", AUDIO_WAV,
        "-vf", "tmix=frames=3:weights='1 2 1'",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "17",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        OUT_MP4,
    ]
    with open(final_log, "wb") as lf:
        subprocess.run(final_cmd, stdout=subprocess.DEVNULL, stderr=lf, check=True)

    size_mb = os.path.getsize(OUT_MP4) / (1024 * 1024)
    print(f"[DONE] Rendered {OUT_MP4} ({size_mb:.2f} MB) total wall time: {time.time() - t0:.1f}s", flush=True)


if __name__ == "__main__":
    main()
