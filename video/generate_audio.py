import base64, json, math, os, struct, subprocess, urllib.request, urllib.error, wave

def _load_dotenv_key():
    env_p = r"c:\Users\HP LAPTOP\Documents\NVIDIA\.env"
    if os.path.exists(env_p):
        with open(env_p, "r", encoding="utf-8") as ef:
            for line in ef:
                if line.strip().startswith("ELEVENLABS_API_KEY="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return ""

KEY = os.environ.get("ELEVENLABS_API_KEY") or _load_dotenv_key()
FFMPEG = r"C:\Users\HP LAPTOP\Documents\Eliza-keeper\node_modules\ffmpeg-static\ffmpeg.exe"
if not os.path.exists(FFMPEG):
    FFMPEG = r"C:\Users\HP LAPTOP\.vscode\extensions\kilocode.kilo-code-7.8.18-win32-x64\bin\ffmpeg.exe"

AUDIO_DIR = r"c:\Users\HP LAPTOP\Documents\NVIDIA\video\assets\audio"
SFX_DIR = os.path.join(AUDIO_DIR, "sfx")
os.makedirs(SFX_DIR, exist_ok=True)

# Crisp, plain-English 5-act script (~55s)
SCRIPT_PARAGRAPHS = [
    "Give a hundred real coding bugs to a giant AI model alone. You pay fifteen times more, and seventy out of a hundred still fail the moment a library updates its code.",
    "Why? Because bugs fail in two very different ways. Either a brand-new API changed after training, or the math logic itself is hard. Searching the web on every task pollutes pure math.",
    "Meet Mjolnir. Every task runs first on fast NVIDIA Nemotron Nano on Nebius, checked by a locked, un-cheatable unit test. Missing a new API? Tavily pulls live docs in three stages. Hard logic bug? Skip search and step up to Super or Ultra.",
    "Testing the app takes one click. Open the live Workbench, pick any broken task, and hit Run. Watch the locked test catch the exact error, route the fix, and print a verified git diff and cost receipt.",
    "Ten out of ten live tasks solved, at seventy percent lower cost. Fast first, grounded on new APIs, and smart on deep logic. Mjolnir."
]

FULL_SCRIPT = "\n\n".join(SCRIPT_PARAGRAPHS)

SFX_SPECS = {
    "pop_grid": ("Soft clean tactile UI pop ripple, minimal Apple keynote subtle clicks", 1.2),
    "fail_drop": ("Deep muted cinematic sub bass drop with subtle power down, clean minimal studio", 1.3),
    "whip_whoosh": ("Crisp airy fast camera whoosh transition, clean minimal motion design", 0.8),
    "lock_snap": ("Precision metallic lock click, compact crisp tactile latch snap", 0.7),
    "tavily_scan": ("Three quick ascending warm glass harmonic chimes, clean minimal UI telemetry", 1.2),
    "mouse_click": ("Crisp clean tactile laptop trackpad click, dry studio foley", 0.5),
    "victory_swell": ("Warm uplifting minimalist electronic chord bloom with soft sub impact, Apple keynote", 2.8),
}


def generate_voiceover():
    vo_mp3 = os.path.join(AUDIO_DIR, "voiceover.mp3")
    vo_json = os.path.join(AUDIO_DIR, "voiceover_raw_align.json")

    # Try Brian (nPczCjzI2devNBz1zQrb) first — modern, clear, grounded narrator; fallback George (JBFqnCBsd6RMkjVDRZzb)
    voices_to_try = ["nPczCjzI2devNBz1zQrb", "JBFqnCBsd6RMkjVDRZzb"]
    if not (os.path.exists(vo_mp3) and os.path.exists(vo_json)):
        for vid in voices_to_try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{vid}/with-timestamps"
            payload = {
                "text": FULL_SCRIPT,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.62,
                    "similarity_boost": 0.82,
                    "style": 0.22,
                    "use_speaker_boost": True,
                    "speed": 1.03,
                },
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"xi-api-key": KEY, "Content-Type": "application/json"},
                method="POST",
            )
            try:
                resp = urllib.request.urlopen(req, timeout=90)
                data = json.loads(resp.read().decode("utf-8"))
                audio_bytes = base64.b64decode(data["audio_base64"])
                with open(vo_mp3, "wb") as f:
                    f.write(audio_bytes)
                with open(vo_json, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "voice_id": vid,
                            "script": FULL_SCRIPT,
                            "alignment": data.get("alignment"),
                            "normalized_alignment": data.get("normalized_alignment"),
                        },
                        f,
                        indent=2,
                    )
                print(f"[OK] Generated voiceover with voice {vid} ({len(audio_bytes)} bytes)")
                break
            except urllib.error.HTTPError as e:
                print(f"[WARN] Voice {vid} failed {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
    else:
        print("[CACHE] Using existing voiceover.mp3 + alignment")

    with open(vo_json, "r", encoding="utf-8") as f:
        raw = json.load(f)

    align = raw.get("alignment") or raw.get("normalized_alignment")
    chars = align["characters"]
    starts = align["character_start_times_seconds"]
    ends = align["character_end_times_seconds"]

    # Group characters into words with exact start/end seconds
    words = []
    cur_chars = []
    w_start = None
    w_end = None
    for ch, s, e in zip(chars, starts, ends):
        if ch.strip() == "":
            if cur_chars:
                words.append({"word": "".join(cur_chars), "start": round(w_start, 4), "end": round(w_end, 4)})
                cur_chars = []
                w_start = None
        else:
            if w_start is None:
                w_start = s
            w_end = e
            cur_chars.append(ch)
    if cur_chars:
        words.append({"word": "".join(cur_chars), "start": round(w_start, 4), "end": round(w_end, 4)})

    for idx, w in enumerate(words):
        w["index"] = idx

    # Build balanced subtitle phrases (max 6 words or max 38 chars, breaking cleanly on punctuation or pauses > 0.22s)
    phrases = []
    cur = []
    for i, w in enumerate(words):
        cur.append(w)
        txt_len = sum(len(x["word"]) + 1 for x in cur)
        ends_punct = w["word"].endswith((".", "?", "!", ",", "—", ":"))
        long_gap = (i + 1 < len(words)) and (words[i + 1]["start"] - w["end"] > 0.22)
        if len(cur) >= 6 or txt_len >= 38 or (ends_punct and len(cur) >= 3) or long_gap or i == len(words) - 1:
            phrases.append(
                {
                    "id": len(phrases),
                    "start": cur[0]["start"],
                    "end": cur[-1]["end"],
                    "text": " ".join(x["word"] for x in cur),
                    "words": cur,
                }
            )
            cur = []

    vo_end = words[-1]["end"] if words else 55.0
    total_duration = round(vo_end + 2.4, 2)  # 0.45s intro lead + tail resolve handled below

    # Offset voiceover start by +0.45s so video opens immediately on beat 1 with 100 figures springing in!
    VO_LEAD = 0.45
    for w in words:
        w["start"] = round(w["start"] + VO_LEAD, 4)
        w["end"] = round(w["end"] + VO_LEAD, 4)
    for p in phrases:
        p["start"] = round(p["start"] + VO_LEAD, 4)
        p["end"] = round(p["end"] + VO_LEAD, 4)
    total_duration = round(words[-1]["end"] + 2.2, 2)

    # Locate exact cue timestamps by matching spoken word sequences!
    def find_word_time(target_substr, min_idx=0):
        t_low = target_substr.lower()
        for w in words[min_idx:]:
            clean = w["word"].lower().strip(".,?!:;—-")
            if clean == t_low or t_low in clean:
                return w["start"], w["index"]
        return 0.0, min_idx

    cues = {}
    t0, idx = find_word_time("fifteen", 0)
    cues["cost_15x"] = t0
    t0, idx = find_word_time("seventy", idx)
    cues["seventy_fail"] = t0
    t0, idx = find_word_time("why", idx)
    cues["act2_why"] = t0
    t0, idx = find_word_time("either", idx)
    cues["fork_api"] = t0
    t0, idx = find_word_time("math", idx)
    cues["fork_math"] = t0
    t0, idx = find_word_time("searching", idx)
    cues["web_pollute"] = t0
    t0, idx = find_word_time("meet", idx)
    cues["act3_mjolnir"] = t0
    t0, idx = find_word_time("locked", idx)
    cues["sandbox_lock"] = t0
    t0, idx = find_word_time("missing", idx)
    cues["tavily_3stage"] = t0
    t0, idx = find_word_time("hard", idx)
    cues["escalate_super"] = t0
    t0, idx = find_word_time("testing", idx)
    cues["act4_testing"] = t0
    t0, idx = find_word_time("workbench", idx)
    cues["open_workbench"] = t0
    t0, idx = find_word_time("run", idx)
    cues["click_run"] = t0
    t0, idx = find_word_time("watch", idx)
    cues["watch_trace"] = t0
    t0, idx = find_word_time("diff", idx)
    cues["diff_receipt"] = t0
    t0, idx = find_word_time("ten", idx)
    cues["act5_ten_of_ten"] = t0
    t0, idx = find_word_time("seventy", idx)
    cues["cost_minus_70"] = t0
    t0, idx = find_word_time("fast", idx)
    cues["summary_pillars"] = t0
    t0, idx = find_word_time("mjolnir", idx)
    cues["final_mjolnir"] = t0

    meta = {
        "vo_lead": VO_LEAD,
        "total_duration": total_duration,
        "word_count": len(words),
        "phrase_count": len(phrases),
        "cues": cues,
        "phrases": phrases,
        "words": words,
    }
    out_meta = os.path.join(AUDIO_DIR, "voiceover_data.json")
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print("[OK] Parsed word timings:", len(words), "words,", len(phrases), "phrases, total_duration=", total_duration)
    print("Cues:", json.dumps(cues, indent=2))
    return meta


def generate_sfx():
    for name, (prompt, dur) in SFX_SPECS.items():
        out_p = os.path.join(SFX_DIR, f"{name}.mp3")
        if os.path.exists(out_p) and os.path.getsize(out_p) > 1000:
            print(f"[CACHE] SFX {name}.mp3")
            continue
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/sound-generation",
            data=json.dumps({"text": prompt, "duration_seconds": dur, "prompt_influence": 0.45}).encode("utf-8"),
            headers={"xi-api-key": KEY, "Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=45)
        b = resp.read()
        with open(out_p, "wb") as f:
            f.write(b)
        print(f"[OK] Generated ElevenLabs SFX {name}.mp3 ({len(b)} bytes)")


if __name__ == "__main__":
    meta = generate_voiceover()
    generate_sfx()
