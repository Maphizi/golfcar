"""Startet und beendet die Modus-Prozesse.

Jeder Modus läuft in einer eigenen Prozessgruppe. Beim Stop: SIGTERM an die
Gruppe, warten, dann SIGKILL. stdout/stderr des Modus landen in logs/<modus>.log.

Nahtloser Wechsel: der neue Modus wird gestartet, während der alte weiterläuft (sein Bild bleibt stehen). Der neue
bekommt das Schreibende einer Pipe als KITT_READY_FD und meldet darüber sein erstes Bild (launcher/ready.py);
erst dann (oder nach `ready_timeout` Sekunden, oder wenn der neue vorher stirbt) wird der alte beendet. Modi mit
`hold = false` in modes.toml (Emulatoren, alte Menüs) werden wie früher erst beendet bzw. halten nichts.
"""
from __future__ import annotations

import logging
import os
import select
import signal
import subprocess
import time
from pathlib import Path

from .config import expand_command

log = logging.getLogger("procman")


class ModeSpec:
    def __init__(self, name: str, cfg: dict):
        self.name = name
        self.label = cfg.get("label", name)
        self.command = expand_command(cfg["command"])
        self.cwd = expand_command([cfg["cwd"]])[0] if cfg.get("cwd") else None
        self.env = {k: os.path.expandvars(str(v)) for k, v in cfg.get("env", {}).items()}
        self.stop_timeout = float(cfg.get("stop_timeout", 5.0))
        self.enabled = bool(cfg.get("enabled", True))
        self.hold = bool(cfg.get("hold", True))        # darf beim Wechsel den Vorgänger stehen lassen / stehen bleiben


class _Run:
    """Ein laufender Modus-Prozess samt Log und Bereitschafts-Pipe."""

    def __init__(self, spec: ModeSpec, proc: subprocess.Popen, logfh, ready_fd: int | None):
        self.spec = spec
        self.proc = proc
        self.pgid = proc.pid                  # start_new_session: pgid == pid
        self.started_at = time.monotonic()
        self.logfh = logfh
        self.ready_fd = ready_fd              # Leseende; None = Modus meldet nichts
        self.ready = ready_fd is None

    def check_ready(self) -> bool:
        if self.ready:
            return True
        if self.ready_fd is None:
            return False
        try:
            r, _, _ = select.select([self.ready_fd], [], [], 0)
            if r:
                data = os.read(self.ready_fd, 64)   # Meldung, oder EOF = Kind hat die Pipe ohne Meldung geschlossen
                self.ready = bool(data)
                os.close(self.ready_fd)             # danach entscheiden nur noch Exit oder ready_timeout
                self.ready_fd = None
        except OSError:
            self.ready_fd = None
        return self.ready

    def close(self) -> None:
        if self.ready_fd is not None:
            try:
                os.close(self.ready_fd)
            except OSError:
                pass
            self.ready_fd = None
        if self.logfh:
            try:
                self.logfh.close()
            except Exception:
                pass
            self.logfh = None


class ProcessManager:
    def __init__(self, modes_cfg: dict, logs_dir: Path):
        self.modes = {name: ModeSpec(name, cfg) for name, cfg in modes_cfg.get("modes", {}).items()}
        self.ready_timeout = float(modes_cfg.get("ready_timeout", 20.0))
        self.logs_dir = logs_dir
        self._run: _Run | None = None         # aktueller Modus
        self._old: _Run | None = None         # Vorgänger, läuft noch bis der aktuelle bereit ist

    # -- Abfragen (Verträglichkeit mit dem bisherigen Zugriff auf current/proc/started_at) -----------------
    @property
    def current(self) -> ModeSpec | None:
        return self._run.spec if self._run else None

    @property
    def proc(self) -> subprocess.Popen | None:
        return self._run.proc if self._run else None

    @property
    def started_at(self) -> float:
        return self._run.started_at if self._run else 0.0

    @property
    def holding(self) -> str | None:
        """Name des Vorgängers, der noch steht, solange der aktuelle Modus lädt."""
        return self._old.spec.name if self._old else None

    def is_running(self) -> bool:
        return self._run is not None and self._run.proc.poll() is None

    def poll(self) -> int | None:
        """Exit-Code, falls der aktuelle Modus beendet ist, sonst None."""
        if self._run is None:
            return None
        return self._run.proc.poll()

    # -- Start / Stop ----------------------------------------------------
    def start(self, name: str, extra_env: dict | None = None) -> bool:
        spec = self.modes.get(name)
        if spec is None:
            log.error("Unbekannter Modus: %s", name)
            return False
        if not spec.enabled:
            log.warning("Modus %s ist deaktiviert", name)
            return False
        # Ein noch stehender Vorgänger geht jetzt; der aktuelle wird zum Vorgänger, wenn beide das Halten erlauben
        if self._old is not None:
            self._stop_run(self._old)
            self._old = None
        hold = bool(self._run is not None and self._run.proc.poll() is None and spec.hold and self._run.spec.hold)
        if self._run is not None and not hold:
            self.stop()
        env = os.environ.copy()
        env.update(spec.env)
        if extra_env:
            env.update(extra_env)
        env["KITT_MODE"] = name
        cache = Path(__file__).resolve().parents[1] / ".cache"
        env.setdefault("MESA_SHADER_CACHE_DIR", str(cache / "mesa"))      # compilierte Shader bleiben zwischen Starts erhalten
        env.setdefault("MESA_SHADER_CACHE_MAX_SIZE", "512M")
        env.setdefault("MESA_GLSL_CACHE_DIR", str(cache / "mesa"))        # älterer Name derselben Einstellung
        env.setdefault("XDG_CACHE_HOME", str(cache))
        logpath = self.logs_dir / f"{name}.log"
        try:
            if logpath.exists() and logpath.stat().st_size > 2_000_000:
                logpath.rename(logpath.with_suffix(".log.1"))     # eine Generation behalten
        except OSError:
            pass
        logfh = open(logpath, "ab", buffering=0)
        logfh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start {spec.command}\n".encode())
        ready_r = ready_w = None
        pass_fds: tuple = ()
        if spec.hold:
            ready_r, ready_w = os.pipe()
            env["KITT_READY_FD"] = str(ready_w)
            pass_fds = (ready_w,)
        try:
            proc = subprocess.Popen(
                spec.command,
                cwd=spec.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=logfh,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # eigene Prozessgruppe -> sauber killbar
                pass_fds=pass_fds,
            )
        except (OSError, FileNotFoundError) as exc:
            log.error("Start von %s fehlgeschlagen: %s", name, exc)
            logfh.close()
            for fd in (ready_r, ready_w):
                if fd is not None:
                    os.close(fd)
            if hold:                         # der Vorgänger bleibt dann einfach der aktuelle Modus
                return False
            self._run = None
            return False
        if ready_w is not None:
            os.close(ready_w)                # nur das Kind schreibt
        if hold:
            self._old = self._run
            log.info("Modus gestartet: %s (pid %d), %s bleibt stehen bis zum ersten Bild",
                     name, proc.pid, self._old.spec.name)
        else:
            log.info("Modus gestartet: %s (pid %d)", name, proc.pid)
        self._run = _Run(spec, proc, logfh, ready_r)
        return True

    def tick(self) -> None:
        """Regelmäßig aus der Hauptschleife: beendet den Vorgänger, sobald der aktuelle Modus bereit ist."""
        if self._old is None:
            return
        run = self._run
        why = None
        if run is None or run.proc.poll() is not None:
            why = "neuer Modus beendet"
        elif run.check_ready():
            why = "erstes Bild nach %.1f s" % (time.monotonic() - run.started_at)
        elif time.monotonic() - run.started_at > self.ready_timeout:
            why = "keine Bereitschaftsmeldung in %.0f s" % self.ready_timeout
        if why:
            log.info("Vorgänger %s geht (%s)", self._old.spec.name, why)
            self._stop_run(self._old)
            self._old = None

    def stop(self) -> int | None:
        if self._old is not None:
            self._stop_run(self._old)
            self._old = None
        if self._run is None:
            return None
        code = self._stop_run(self._run)
        self._run = None
        return code

    def _stop_run(self, run: _Run) -> int | None:
        spec, proc = run.spec, run.proc
        code = proc.poll()
        if code is None:
            pgid = os.getpgid(proc.pid) if self._alive(proc.pid) else None
            log.info("Beende Modus %s (pid %d) mit SIGTERM", spec.name, proc.pid)
            self._signal_group(pgid, proc, signal.SIGTERM)
            try:
                code = proc.wait(timeout=spec.stop_timeout)
            except subprocess.TimeoutExpired:
                log.warning("Modus %s reagiert nicht, SIGKILL", spec.name)
                self._signal_group(pgid, proc, signal.SIGKILL)
                try:
                    code = proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    log.error("Modus %s lässt sich nicht beenden", spec.name)
                    code = None
        log.info("Modus beendet: %s (exit %s, Laufzeit %.0fs)", spec.name, code, time.monotonic() - run.started_at)
        # Reste der Prozessgruppe (Server, Emulatoren) sicher beenden, auch wenn der Hauptprozess schon weg ist
        if run.pgid:
            try:
                os.killpg(run.pgid, signal.SIGTERM)
                time.sleep(0.3)
                os.killpg(run.pgid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            run.pgid = None
        run.close()
        return code

    # -- Hilfen ----------------------------------------------------------
    @staticmethod
    def _alive(pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    @staticmethod
    def _signal_group(pgid, proc, sig) -> None:
        try:
            if pgid is not None:
                os.killpg(pgid, sig)
            else:
                proc.send_signal(sig)
        except ProcessLookupError:
            pass
