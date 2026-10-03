"""Startet und beendet genau einen Modus-Prozess zur Zeit.

Jeder Modus läuft in einer eigenen Prozessgruppe. Beim Stop: SIGTERM an die
Gruppe, warten, dann SIGKILL. stdout/stderr des Modus landen in logs/<modus>.log.
"""
from __future__ import annotations

import logging
import os
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


class ProcessManager:
    def __init__(self, modes_cfg: dict, logs_dir: Path):
        self.modes = {name: ModeSpec(name, cfg) for name, cfg in modes_cfg.get("modes", {}).items()}
        self.logs_dir = logs_dir
        self.current: ModeSpec | None = None
        self.proc: subprocess.Popen | None = None
        self.started_at: float = 0.0
        self._logfh = None

    # -- Abfragen --------------------------------------------------------
    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def poll(self) -> int | None:
        """Exit-Code, falls der aktuelle Modus beendet ist, sonst None."""
        if self.proc is None:
            return None
        return self.proc.poll()

    # -- Start / Stop ----------------------------------------------------
    def start(self, name: str, extra_env: dict | None = None) -> bool:
        spec = self.modes.get(name)
        if spec is None:
            log.error("Unbekannter Modus: %s", name)
            return False
        if not spec.enabled:
            log.warning("Modus %s ist deaktiviert", name)
            return False
        if self.is_running():
            self.stop()
        env = os.environ.copy()
        env.update(spec.env)
        if extra_env:
            env.update(extra_env)
        env["KITT_MODE"] = name
        self._logfh = open(self.logs_dir / f"{name}.log", "ab", buffering=0)
        self._logfh.write(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} start {spec.command}\n".encode())
        try:
            self.proc = subprocess.Popen(
                spec.command,
                cwd=spec.cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=self._logfh,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # eigene Prozessgruppe -> sauber killbar
            )
        except (OSError, FileNotFoundError) as exc:
            log.error("Start von %s fehlgeschlagen: %s", name, exc)
            self._close_log()
            self.proc = None
            self.current = None
            return False
        self.current = spec
        self.started_at = time.monotonic()
        log.info("Modus gestartet: %s (pid %d)", name, self.proc.pid)
        return True

    def stop(self) -> int | None:
        if self.proc is None:
            return None
        spec = self.current
        proc = self.proc
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
        log.info("Modus beendet: %s (exit %s, Laufzeit %.0fs)", spec.name, code, time.monotonic() - self.started_at)
        self._close_log()
        self.proc = None
        self.current = None
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

    def _close_log(self) -> None:
        if self._logfh:
            try:
                self._logfh.close()
            except Exception:
                pass
            self._logfh = None
