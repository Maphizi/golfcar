"""LLM-Werkzeug (Phase 6):

  python -m kitt.llm --bench                 alle [llm.bench].models vergleichen -> docs/llm_bench_phase6.md
  python -m kitt.llm --ask "KITT, wie sieht's aus?" [--model DATEI]   eine Frage an KITT
  python -m kitt.llm --chat                  interaktiver Dialog im Terminal (Strg+D beendet)
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from kitt import config as kcfg  # noqa: E402
from kitt.llm.llama_client import Kitt, LlamaServer  # noqa: E402
from launcher import config as lcfg, logsetup  # noqa: E402

log = logging.getLogger("llm.tool")
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
BANNED = ("natürlich", "gerne", "selbstverständlich", "kein problem", "als ki", "sprachmodell", "language model")
ENGLISH_HINTS = (" the ", " you ", " and ", " is ", " i'm ", " sorry")


def violations(text: str) -> list[str]:
    t = " " + text.lower() + " "
    v = []
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if len(sentences) > 3:
        v.append(f"{len(sentences)} Sätze")
    if EMOJI_RE.search(text):
        v.append("Emoji")
    for b in BANNED:
        if b in t:
            v.append(f"'{b}'")
    if sum(h in t for h in ENGLISH_HINTS) >= 2:
        v.append("Englisch?")
    if "\n-" in text or "\n*" in text or re.search(r"\n\d+\.", text):
        v.append("Liste")
    if not text.strip():
        v.append("leer")
    return v


def make_server(llm: dict, model: str, llama_dir: Path, models_dir: Path, logs_dir: Path) -> LlamaServer:
    return LlamaServer(llama_dir, models_dir / model, int(llm.get("port", 8179)), int(llm.get("threads", 4)),
                       int(llm.get("ctx", 2048)), logs_dir / "llama-server.log")


def cmd_bench(args, llm, llama_dir, models_dir, logs_dir, system_prompt) -> int:
    prompts = [l.strip() for l in open(kcfg.path(llm["bench"]["prompts"])) if l.strip()]
    if args.quick:
        prompts = prompts[:4]
    models = args.bench_models or [m["file"] for m in llm["bench"]["models"]]
    rows = []
    for m in models:
        if not (models_dir / m).exists():
            print(f"{m}: fehlt in {models_dir}, übersprungen")
            continue
        srv = make_server(llm, m, llama_dir, models_dir, logs_dir)
        try:
            load = srv.start()
            k = Kitt(srv.port, system_prompt, llm)
            k.ask("Hallo KITT.")                      # Warm-up, füllt den Prompt-Cache
            k.reset()
            results = []
            for p in prompts:
                k.reset()                             # jede Frage ohne Vorgeschichte, vergleichbar
                r = k.ask(p)
                results.append((p, r, violations(r.text)))
                print(f"   {p!r}\n      -> {r.text!r}  [TTFT {r.ttft:.2f}s, {r.tps:.1f} tok/s, {r.tokens} tok, {r.total:.2f}s]"
                      + (f"  Verstöße: {', '.join(violations(r.text))}" if violations(r.text) else ""))
            rss = srv.rss_mb()
        except Exception as exc:
            print(f"{m}: FEHLER {exc}")
            srv.stop()
            continue
        srv.stop()
        rows.append((m, load, rss, results))
        n = len(results)
        print(f"{m}: Laden {load:.1f}s, RSS {rss:.0f} MB, Ø TTFT {sum(r.ttft for _, r, _ in results)/n:.2f}s, "
              f"Ø {sum(r.tps for _, r, _ in results)/n:.1f} tok/s, Ø Antwort {sum(r.total for _, r, _ in results)/n:.2f}s, "
              f"Verstöße {sum(len(v) for *_, v in results)}")
    out = lcfg.ROOT / "docs" / "llm_bench_phase6.md"
    with open(out, "w") as fh:
        fh.write(f"# LLM-Benchmark llama.cpp ({time.strftime('%Y-%m-%d %H:%M')})\n\n")
        fh.write(f"Threads {llm.get('threads')}, ctx {llm.get('ctx')}, max_tokens {llm.get('max_tokens')}, "
                 f"temperature {llm.get('temperature')}, top_p {llm.get('top_p')}. Thinking bei Qwen3/3.5 abgeschaltet.\n\n")
        fh.write("## Übersicht\n\n| Modell | Laden | RSS | Ø TTFT | Ø tok/s | Ø Antwortzeit | Ø Tokens | Regelverstöße |\n|---|---|---|---|---|---|---|---|\n")
        for m, load, rss, results in rows:
            n = len(results)
            fh.write(f"| {m} | {load:.1f}s | {rss:.0f} MB | {sum(r.ttft for _, r, _ in results)/n:.2f}s | "
                     f"{sum(r.tps for _, r, _ in results)/n:.1f} | {sum(r.total for _, r, _ in results)/n:.2f}s | "
                     f"{sum(r.tokens for _, r, _ in results)/n:.0f} | {sum(len(v) for *_, v in results)} |\n")
        for m, load, rss, results in rows:
            fh.write(f"\n## {m}\n\n| Frage | Antwort | TTFT | tok/s | Zeit | Verstöße |\n|---|---|---|---|---|---|\n")
            for p, r, v in results:
                fh.write(f"| {p} | {r.text.replace('|', '/').replace(chr(10), ' ')} | {r.ttft:.2f}s | {r.tps:.1f} | {r.total:.2f}s | {', '.join(v)} |\n")
    print(f"Tabelle: {out}")
    return 0


def cmd_ask(args, llm, llama_dir, models_dir, logs_dir, system_prompt) -> int:
    srv = make_server(llm, args.model or llm["model"], llama_dir, models_dir, logs_dir)
    load = srv.start()
    print(f"{srv.model_path.name}: geladen in {load:.1f}s, RSS {srv.rss_mb():.0f} MB")
    k = Kitt(srv.port, system_prompt, llm)
    from kitt.context import context_block, mood_of_day
    vcfg = kcfg.load().get("voice", {})
    mood = mood_of_day(vcfg)
    if mood:
        print(f"Tagesform: {mood.get('name')}")
    k.context_provider = lambda: "\n\n".join(p for p in [mood.get("prompt", "") if mood else "", context_block() if vcfg.get("context", True) else ""] if p)
    try:
        if args.ask:
            print(f"Fahrer: {args.ask}")
            print("KITT: ", end="", flush=True)
            r = k.ask(args.ask, on_token=lambda t: print(t, end="", flush=True))
            print(f"\n   [TTFT {r.ttft:.2f}s, {r.tps:.1f} tok/s, {r.tokens} Tokens, {r.total:.2f}s]")
        else:
            print("Dialog mit KITT. Leere Zeile oder Strg+D beendet.")
            while True:
                try:
                    q = input("Fahrer: ").strip()
                except EOFError:
                    break
                if not q:
                    break
                print("KITT: ", end="", flush=True)
                r = k.ask(q, on_token=lambda t: print(t, end="", flush=True))
                print(f"\n   [TTFT {r.ttft:.2f}s, {r.tps:.1f} tok/s, {r.total:.2f}s]")
    finally:
        srv.stop()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", action="store_true")
    ap.add_argument("--bench-models", nargs="*")
    ap.add_argument("--quick", action="store_true", help="nur die ersten 4 Fragen")
    ap.add_argument("--ask")
    ap.add_argument("--chat", action="store_true")
    ap.add_argument("--model")
    ap.add_argument("--llama-dir")
    ap.add_argument("--models-dir")
    args = ap.parse_args()
    settings = lcfg.load_settings()
    logs_dir = lcfg.logs_dir(settings)
    logsetup.setup("llm", logs_dir, settings.get("logging", {}).get("level", "INFO"))
    llm = kcfg.load()["llm"]
    llama_dir = Path(args.llama_dir) if args.llama_dir else kcfg.path(llm["llama_dir"])
    models_dir = Path(args.models_dir) if args.models_dir else kcfg.path(llm["models_dir"])
    system_prompt = kcfg.path(llm["system_prompt"]).read_text().strip()
    if args.bench:
        return cmd_bench(args, llm, llama_dir, models_dir, logs_dir, system_prompt)
    if args.ask or args.chat:
        return cmd_ask(args, llm, llama_dir, models_dir, logs_dir, system_prompt)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
