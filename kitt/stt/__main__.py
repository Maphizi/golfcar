"""STT-Werkzeug (Phase 5):

  python -m kitt.stt --wav datei.wav [...]      Dateien mit dem konfigurierten Modell transkribieren
  python -m kitt.stt --bench                    alle [stt.bench].models vergleichen, Tabelle nach docs/
  python -m kitt.stt --mic [--seconds N]        Mikrofon + VAD + whisper live, Transkripte ausgeben
  python -m kitt.stt --vad-test datei.wav       nur VAD über eine Datei laufen lassen

  --model NAME   überschreibt [stt].model, --whisper-dir/--models-dir überschreiben die Pfade.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np  # noqa: E402

from kitt import config as kcfg  # noqa: E402
from kitt.audio_utils import read_wav  # noqa: E402
from kitt.stt.listener import Listener  # noqa: E402
from kitt.stt.vad import CHUNK, RATE, load_vad  # noqa: E402
from kitt.stt.whisper_client import WhisperServer, transcribe  # noqa: E402
from launcher import config as lcfg, logsetup  # noqa: E402

log = logging.getLogger("stt.tool")


def make_server(stt: dict, model: str, whisper_dir: Path, models_dir: Path, logs_dir: Path) -> WhisperServer:
    return WhisperServer(whisper_dir, models_dir / model, int(stt.get("port", 8178)), stt.get("language", "de"),
                         int(stt.get("threads", 4)), int(stt.get("audio_ctx", 0)), int(stt.get("beam_size", 1)),
                         int(stt.get("best_of", 1)), logs_dir / "whisper-server.log")


def cmd_wav(args, stt, whisper_dir, models_dir, logs_dir) -> int:
    srv = make_server(stt, args.model or stt["model"], whisper_dir, models_dir, logs_dir)
    load = srv.start()
    print(f"Modell {srv.model_path.name}: geladen in {load:.1f}s, RSS {srv.rss_mb():.0f} MB")
    try:
        for f in args.wav:
            pcm = read_wav(f, RATE)
            text, dt = transcribe(pcm, srv.port, stt.get("prompt", ""))
            print(f"{Path(f).name}: {len(pcm)/RATE:.1f}s Audio, {dt:.2f}s -> {text!r}")
    finally:
        srv.stop()
    return 0


def cmd_bench(args, stt, whisper_dir, models_dir, logs_dir) -> int:
    wavs = args.wav or sorted(str(p) for p in (lcfg.ROOT / "kitt" / "stt" / "testdata").glob("*.wav"))
    if not wavs:
        print("Keine Test-WAVs (kitt/stt/testdata/*.wav oder --wav)")
        return 2
    models = args.bench_models or stt.get("bench", {}).get("models", [stt["model"]])
    rows = []
    for m in models:
        if not (models_dir / m).exists():
            print(f"{m}: fehlt in {models_dir}, übersprungen")
            continue
        srv = make_server(stt, m, whisper_dir, models_dir, logs_dir)
        try:
            load = srv.start()
            first = read_wav(wavs[0], RATE)
            transcribe(first, srv.port, stt.get("prompt", ""))          # Warm-up
            results = []
            for f in wavs:
                pcm = read_wav(f, RATE)
                best = None
                for _ in range(2):
                    text, dt = transcribe(pcm, srv.port, stt.get("prompt", ""))
                    best = dt if best is None else min(best, dt)
                results.append((Path(f).name, len(pcm) / RATE, best, text))
            rss = srv.rss_mb()
        except Exception as exc:
            print(f"{m}: FEHLER {exc}")
            srv.stop()
            continue
        srv.stop()
        rows.append((m, load, rss, results))
        print(f"{m}: Laden {load:.1f}s, RSS {rss:.0f} MB")
        for name, dur, dt, text in results:
            print(f"   {name}: {dur:.1f}s Audio -> {dt:.2f}s (RTF {dt/dur:.2f})  {text!r}")
    out = lcfg.ROOT / "docs" / "stt_bench_phase5.md"
    with open(out, "w") as fh:
        fh.write(f"# STT-Benchmark whisper.cpp ({time.strftime('%Y-%m-%d %H:%M')})\n\n")
        fh.write(f"Threads {stt.get('threads')}, audio_ctx {stt.get('audio_ctx')}, beam {stt.get('beam_size')}, "
                 f"best_of {stt.get('best_of')}, Sprache {stt.get('language')}. Latenz = bestes von 2 Durchläufen nach Warm-up.\n\n")
        fh.write("| Modell | Laden | RSS | Datei | Audio | Latenz | RTF | Text |\n|---|---|---|---|---|---|---|---|\n")
        for m, load, rss, results in rows:
            for name, dur, dt, text in results:
                fh.write(f"| {m} | {load:.1f}s | {rss:.0f} MB | {name} | {dur:.1f}s | {dt:.2f}s | {dt/dur:.2f} | {text} |\n")
    print(f"Tabelle: {out}")
    return 0


def cmd_vad_test(args, vad_cfg) -> int:
    vad = load_vad(vad_cfg, kcfg.path(vad_cfg.get("model", "")))
    pcm = read_wav(args.vad_test, RATE)
    events = []
    lst = Listener(vad_cfg, vad, lambda a: events.append(("utterance", len(a) / RATE)),
                   lambda s: events.append(("state", s)), rate_in=RATE)
    probs = []
    lst.on_level = probs.append
    t0 = time.monotonic()
    for i in range(0, len(pcm), CHUNK * 8):
        lst.feed(pcm[i:i + CHUNK * 8])
    lst.feed(np.zeros(RATE, dtype=np.float32))     # 1 s Stille, damit die Äußerung abschließt
    dt = time.monotonic() - t0
    print(f"VAD {vad.name}: {len(probs)} Chunks in {dt*1000:.0f} ms ({dt/len(probs)*1000:.2f} ms/Chunk), "
          f"max p={max(probs):.2f}, Chunks über start_threshold: {sum(p >= lst.start_threshold for p in probs)}")
    print("Ereignisse:", events)
    return 0


def cmd_mic(args, stt, vad_cfg, whisper_dir, models_dir, logs_dir) -> int:
    from visualizers.engine.audio_capture import AudioCapture
    audio_cfg = lcfg._load("audio.toml")
    srv = make_server(stt, args.model or stt["model"], whisper_dir, models_dir, logs_dir)
    srv.start()
    vad = load_vad(vad_cfg, kcfg.path(vad_cfg.get("model", "")))

    def on_utt(pcm):
        text, dt = transcribe(pcm, srv.port, stt.get("prompt", ""))
        print(f"[{time.strftime('%H:%M:%S')}] {len(pcm)/RATE:.1f}s Audio -> {dt:.2f}s: {text!r}", flush=True)

    lst = Listener(vad_cfg, vad, on_utt, lambda s: print(f"  state: {s}", flush=True), rate_in=int(audio_cfg["capture"]["sample_rate"]))
    cap = AudioCapture(audio_cfg)
    cap.subscribers.append(lst.feed)
    cap.start()
    print(f"Höre zu ({vad.name}, {srv.model_path.name}). Sprich etwas. Strg+C beendet.", flush=True)
    t0 = time.monotonic()
    try:
        while not args.seconds or time.monotonic() - t0 < args.seconds:
            time.sleep(0.2)
            if cap.active_backend == "none" and time.monotonic() - t0 > 5:
                print("Keine Audioquelle (scripts/audio_check.sh)", flush=True)
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.stop()
        srv.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--wav", nargs="*", default=[])
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--bench-models", nargs="*")
    ap.add_argument("--mic", action="store_true")
    ap.add_argument("--vad-test")
    ap.add_argument("--seconds", type=float, default=0)
    ap.add_argument("--model")
    ap.add_argument("--whisper-dir")
    ap.add_argument("--models-dir")
    args = ap.parse_args()
    settings = lcfg.load_settings()
    logs_dir = lcfg.logs_dir(settings)
    logsetup.setup("stt", logs_dir, settings.get("logging", {}).get("level", "INFO"))
    cfg = kcfg.load()
    stt, vad_cfg = cfg["stt"], cfg["vad"]
    whisper_dir = Path(args.whisper_dir) if args.whisper_dir else kcfg.path(stt["whisper_dir"])
    models_dir = Path(args.models_dir) if args.models_dir else kcfg.path(stt["models_dir"])
    if args.vad_test:
        return cmd_vad_test(args, vad_cfg)
    if args.bench:
        return cmd_bench(args, stt, whisper_dir, models_dir, logs_dir)
    if args.mic:
        return cmd_mic(args, stt, vad_cfg, whisper_dir, models_dir, logs_dir)
    if args.wav:
        return cmd_wav(args, stt, whisper_dir, models_dir, logs_dir)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
