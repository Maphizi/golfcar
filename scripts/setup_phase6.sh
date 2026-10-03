#!/usr/bin/env bash
# Phase 6: llama.cpp bauen und die Qwen-Kandidaten aus config/kitt.toml [llm.bench] laden.
# Idempotent. Dauer auf dem Pi 5: Build ca. 10–15 min, Downloads ca. 5 GB (je nach Kandidaten).
#   scripts/setup_phase6.sh            alles
#   scripts/setup_phase6.sh --no-download   nur bauen
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LDIR="$ROOT/vendor/llama.cpp"
MDIR="$ROOT/models"
mkdir -p "$MDIR" vendor logs
say() { printf '\n[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

say "apt-Pakete"
sudo apt-get install -y -qq cmake build-essential git curl 2>&1 | tail -1

say "llama.cpp"
if [ -d "$LDIR/.git" ]; then
  git -C "$LDIR" pull --ff-only 2>&1 | tail -1
else
  git clone --depth=1 https://github.com/ggml-org/llama.cpp.git "$LDIR"
fi
git -C "$LDIR" log -1 --format='Commit: %h %cd' --date=short
if [ ! -x "$LDIR/build/bin/llama-server" ]; then
  # CPU-Build mit NEON/dotprod/i8mm (Cortex-A76). Kein curl-Support nötig, Downloads macht dieses Skript.
  cmake -S "$LDIR" -B "$LDIR/build" -DCMAKE_BUILD_TYPE=Release -DGGML_NATIVE=ON -DLLAMA_CURL=OFF \
        -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=ON > logs/llama_cmake.log 2>&1 \
    && cmake --build "$LDIR/build" -j4 --config Release --target llama-server llama-bench llama-cli > logs/llama_build.log 2>&1 \
    || { echo "Build fehlgeschlagen, siehe logs/llama_build.log"; tail -20 logs/llama_build.log; exit 1; }
fi
ls -1 "$LDIR/build/bin/" | grep -E "^llama-(server|bench|cli)$" | sed 's/^/  /'

if [ "${1:-}" = "--no-download" ]; then say "fertig (ohne Downloads)"; exit 0; fi

say "Modelle laut config/kitt.toml [llm.bench]"
python3 - "$MDIR" <<'PY'
import subprocess, sys, tomllib, pathlib
mdir = pathlib.Path(sys.argv[1])
cfg = tomllib.load(open("config/kitt.toml", "rb"))
fail = 0
for m in cfg["llm"]["bench"]["models"]:
    dst = mdir / m["file"]
    if dst.exists() and dst.stat().st_size > 1_000_000:
        print(f"  {m['file']} vorhanden ({dst.stat().st_size/1e9:.2f} GB)"); continue
    print(f"  lade {m['file']} ...", flush=True)
    part = dst.with_suffix(dst.suffix + ".part")
    r = subprocess.run(["curl", "-sS", "-L", "-f", "-C", "-", "--retry", "3", "-o", str(part), m["url"]])
    if r.returncode == 0 and part.exists() and part.stat().st_size > 1_000_000:
        part.rename(dst); print(f"  ok ({dst.stat().st_size/1e9:.2f} GB)")
    else:
        print(f"  FEHLER bei {m['file']} (curl exit {r.returncode}) – URL prüfen: {m['url']}"); fail += 1
sys.exit(1 if fail else 0)
PY
rc=$?
df -h / | tail -1 | awk '{print "Frei auf /: "$4}'
[ $rc -eq 0 ] && say "fertig. Benchmark:  scripts/llm_bench.sh" || say "fertig mit Fehlern (fehlende Modelle werden im Benchmark übersprungen)"
