import json, math, os, subprocess
import numpy as np

FFMPEG = r"C:\Users\HP LAPTOP\Documents\Eliza-keeper\node_modules\ffmpeg-static\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Users\HP LAPTOP\.vscode\extensions\kilocode.kilo-code-7.8.18-win32-x64\bin\ffmpeg.exe"

AUDIO_DIR = r"c:\Users\HP LAPTOP\Documents\NVIDIA\video\assets\audio"
SFX_DIR = os.path.join(AUDIO_DIR, "sfx")
SR = 44100


def decode_audio_stereo(path):
    cmd = [
        FFMPEG, "-y", "-i", path,
        "-f", "f32le", "-acodec", "pcm_f32le",
        "-ac", "2", "-ar", str(SR), "pipe:1"
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    arr = np.frombuffer(proc.stdout, dtype=np.float32).reshape(-1, 2)
    return arr.copy()


def synth_bgm(duration_s, cues):
    n = int(math.ceil(duration_s * SR))
    t = np.arange(n, dtype=np.float64) / SR
    left = np.zeros(n, dtype=np.float64)
    right = np.zeros(n, dtype=np.float64)

    bpm = 120.0
    beat_dur = 60.0 / bpm  # 0.5s
    bar_dur = beat_dur * 4.0  # 2.0s

    # Warm minimal electronic keynote progression (D minor -> Bb maj7 -> F maj9 -> C add9)
    chords = [
        [146.83, 220.00, 261.63, 329.63],  # Dm9
        [116.54, 174.61, 220.00, 293.66],  # Bbmaj7
        [174.61, 220.00, 261.63, 392.00],  # Fmaj9
        [130.81, 196.00, 246.94, 293.66],  # Cadd9
    ]
    roots = [73.42, 58.27, 87.31, 65.41]

    num_bars = int(math.ceil(duration_s / bar_dur)) + 1
    for b in range(num_bars):
        b_start = b * bar_dur
        i0 = int(b_start * SR)
        i1 = min(n, int((b_start + bar_dur + 0.15) * SR))
        if i0 >= n:
            break
        lt = t[i0:i1] - b_start
        chord = chords[b % len(chords)]
        root = roots[b % len(roots)]

        # Energy envelope across film acts
        mid_t = b_start + 1.0
        if mid_t < cues["act3_mjolnir"] - 0.3:
            energy = 0.68
        elif mid_t < cues["act5_ten_of_ten"]:
            energy = 0.92
        else:
            energy = 1.05

        env = np.minimum(1.0, lt / 0.08) * np.exp(-lt * 0.42) * energy
        # Smooth tail fade at end of bar
        rem = (bar_dur + 0.15) - lt
        env *= np.clip(rem / 0.15, 0.0, 1.0)

        # Warm stereo Rhodes pad (fundamental + gentle 2nd harmonic, slight detune L/R)
        pad_l = np.zeros_like(lt)
        pad_r = np.zeros_like(lt)
        for idx_f, freq in enumerate(chord):
            det = 1.0012 if idx_f % 2 == 0 else 0.9988
            pad_l += 0.22 * np.sin(2 * math.pi * freq * lt) + 0.05 * np.sin(2 * math.pi * (freq * 2) * lt)
            pad_r += 0.22 * np.sin(2 * math.pi * (freq * det) * lt) + 0.05 * np.sin(2 * math.pi * (freq * 2 * det) * lt)

        # Sidechain pump on every beat (0.5s)
        beat_phase = (lt % beat_dur) / beat_dur
        pump = 0.55 + 0.45 * (1.0 - np.exp(-beat_phase * 5.0))

        # Deep warm sub bass
        sub = 0.34 * np.sin(2 * math.pi * root * lt) * pump * energy

        left[i0:i1] += pad_l * env * pump + sub
        right[i0:i1] += pad_r * env * pump + sub

    # Subtle 120 BPM soft kick & crisp 16th-note studio pulse (keeps kinetic momentum, zero dead air)
    num_beats = int(duration_s / beat_dur)
    rng = np.random.default_rng(42)
    for k in range(num_beats):
        bt = k * beat_dur
        if bt > duration_s - 1.2:
            break
        k0 = int(bt * SR)
        k_len = int(0.16 * SR)
        k1 = min(n, k0 + k_len)
        kt = np.arange(k1 - k0, dtype=np.float64) / SR
        # Pitch-envelope soft kick (115Hz -> 46Hz)
        f_env = 46.0 + 70.0 * np.exp(-kt * 36.0)
        phase = 2 * math.pi * np.cumsum(f_env) / SR
        kick = 0.36 * np.sin(phase) * np.exp(-kt * 18.0)
        left[k0:k1] += kick
        right[k0:k1] += kick

        # Soft brushed 8th-note tick after Act 1 intro
        for sub_step in range(2):
            ht = bt + sub_step * (beat_dur * 0.5)
            h0 = int(ht * SR)
            h_len = int(0.035 * SR)
            h1 = min(n, h0 + h_len)
            if h1 <= h0:
                continue
            ht_arr = np.arange(h1 - h0, dtype=np.float64) / SR
            amp = 0.045 if sub_step == 1 else 0.025
            noise = rng.normal(0.0, 1.0, h1 - h0)
            # Simple high-pass via first difference
            hp = np.diff(noise, prepend=0.0)
            hat = amp * hp * np.exp(-ht_arr * 95.0)
            left[h0:h1] += hat * 0.9
            right[h0:h1] += hat * 1.1

    # Gentle master fade-out over last 1.4s
    fade_len = int(1.4 * SR)
    fade = np.linspace(1.0, 0.0, fade_len)
    left[-fade_len:] *= fade
    right[-fade_len:] *= fade

    bgm = np.stack([left, right], axis=1).astype(np.float32)
    peak = np.max(np.abs(bgm)) + 1e-6
    return bgm / peak * 0.55


def fast_moving_avg(arr, win):
    cs = np.cumsum(np.insert(arr.astype(np.float64), 0, 0.0))
    out = (cs[win:] - cs[:-win]) / float(win)
    pad_l = win // 2
    pad_r = len(arr) - len(out) - pad_l
    return np.pad(out, (pad_l, max(0, pad_r)), mode="edge").astype(np.float32)[:len(arr)]


def place_sfx_by_peak(mix, sfx_arr, event_time_s, gain=0.35):
    mono_env = np.mean(np.abs(sfx_arr), axis=1)
    # Smooth 15ms window to find perceptual peak in O(N)
    win = max(1, int(0.015 * SR))
    smooth = fast_moving_avg(mono_env, win)
    peak_idx = int(np.argmax(smooth))
    # Cap peak_idx to first 0.6s so long reverb tails don't shift attack too early
    peak_idx = min(peak_idx, int(0.45 * SR))

    norm = sfx_arr / (np.max(np.abs(sfx_arr)) + 1e-6) * gain
    start_sample = int(event_time_s * SR) - peak_idx
    s0 = max(0, start_sample)
    offset = s0 - start_sample
    e0 = min(len(mix), s0 + (len(norm) - offset))
    count = e0 - s0
    if count > 0:
        mix[s0:e0] += norm[offset:offset + count]


def main():
    with open(os.path.join(AUDIO_DIR, "voiceover_data.json"), "r", encoding="utf-8") as f:
        meta = json.load(f)

    total_dur = meta["total_duration"]
    vo_lead = meta["vo_lead"]
    cues = meta["cues"]

    n_total = int(math.ceil(total_dur * SR))
    mix = np.zeros((n_total, 2), dtype=np.float32)

    # 1. Decode voiceover & place at vo_lead
    vo = decode_audio_stereo(os.path.join(AUDIO_DIR, "voiceover.mp3"))
    vo_peak = np.max(np.abs(vo)) + 1e-6
    vo = vo / vo_peak * 0.92
    vo_start = int(vo_lead * SR)
    vo_end = min(n_total, vo_start + len(vo))

    # Build voice activity envelope for smooth sidechain ducking (50ms look-ahead, 320ms release)
    vo_full = np.zeros(n_total, dtype=np.float32)
    vo_full[vo_start:vo_end] = np.max(np.abs(vo[:vo_end - vo_start]), axis=1)
    lookahead = int(0.05 * SR)
    vo_shifted = np.pad(vo_full[lookahead:], (0, lookahead))
    win = int(0.28 * SR)
    activity = fast_moving_avg(vo_shifted, win)
    activity = np.clip(activity * 5.5, 0.0, 1.0)
    # Music sits at 0.24 during active speech (-12dB below voice) and lifts gently to 0.44 during breaths/intro/outro
    duck_gain = (0.44 - 0.21 * activity)[:, None]

    # 2. Synthesize 120 BPM musical bed & apply sidechain ducking
    bgm = synth_bgm(total_dur, cues)
    mix += bgm * duck_gain

    # 3. Layer ElevenLabs SFX peak-aligned to exact visual events (subtle & crisp under voice!)
    sfx = {name: decode_audio_stereo(os.path.join(SFX_DIR, f"{name}.mp3")) for name in [
        "pop_grid", "fail_drop", "whip_whoosh", "lock_snap", "tavily_scan", "mouse_click", "victory_swell"
    ]}

    place_sfx_by_peak(mix, sfx["pop_grid"], 0.18, gain=0.26)
    place_sfx_by_peak(mix, sfx["fail_drop"], cues["seventy_fail"] + 0.08, gain=0.30)
    place_sfx_by_peak(mix, sfx["whip_whoosh"], cues["act2_why"] - 0.06, gain=0.24)
    place_sfx_by_peak(mix, sfx["whip_whoosh"], cues["act3_mjolnir"] - 0.08, gain=0.28)
    place_sfx_by_peak(mix, sfx["lock_snap"], cues["sandbox_lock"] + 0.05, gain=0.28)
    place_sfx_by_peak(mix, sfx["tavily_scan"], cues["tavily_3stage"] + 0.15, gain=0.25)
    place_sfx_by_peak(mix, sfx["whip_whoosh"], cues["act4_testing"] - 0.08, gain=0.25)
    place_sfx_by_peak(mix, sfx["mouse_click"], cues["open_workbench"] + 0.12, gain=0.34)
    place_sfx_by_peak(mix, sfx["mouse_click"], cues["click_run"] + 0.05, gain=0.36)
    place_sfx_by_peak(mix, sfx["lock_snap"], cues["diff_receipt"] + 0.05, gain=0.24)
    place_sfx_by_peak(mix, sfx["pop_grid"], cues["act5_ten_of_ten"] + 0.05, gain=0.26)
    place_sfx_by_peak(mix, sfx["victory_swell"], cues["final_mjolnir"] + 0.05, gain=0.36)

    # 4. Add crisp voiceover on top
    mix[vo_start:vo_end] += vo[:vo_end - vo_start]

    # Soft limiter before ffmpeg loudnorm
    mix = np.tanh(mix * 1.05).astype(np.float32)

    raw_wav = os.path.join(AUDIO_DIR, "master_raw.wav")
    master_wav = os.path.join(AUDIO_DIR, "master_audio.wav")
    master_mp3 = os.path.join(AUDIO_DIR, "master_audio.mp3")

    # Write raw float32 via ffmpeg into WAV, then loudnorm to -14 LUFS
    proc = subprocess.Popen(
        [
            FFMPEG, "-y",
            "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "pipe:0",
            "-af", "loudnorm=I=-14:TP=-1.0:LRA=9",
            "-ar", "48000", master_wav
        ],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    _, stderr = proc.communicate(input=mix.tobytes())
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode("utf-8", "replace"))

    subprocess.run(
        [FFMPEG, "-y", "-i", master_wav, "-codec:a", "libmp3lame", "-b:a", "192k", master_mp3],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True
    )

    # Verify zero dead silence windows (>0.5s below -55dB)
    rms_blocks = [
        float(np.sqrt(np.mean(mix[i:i + SR // 2] ** 2)))
        for i in range(0, len(mix) - SR // 2, SR // 2)
    ]
    silent_blocks = sum(1 for r in rms_blocks if r < 0.002)
    print(f"[OK] Mastered audio saved ({total_dur:.2f}s) -> {master_wav} | Silent 0.5s windows: {silent_blocks}/{len(rms_blocks)}")


if __name__ == "__main__":
    main()
