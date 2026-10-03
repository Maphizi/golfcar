"""Launcher-Kern: nimmt Actions entgegen und schaltet Modi um.

Der Kern selbst öffnet kein Fenster und braucht keine GPU. Der Home-Screen
ist ein normaler Modus, der beim Start und nach jedem anderen Modus läuft.
Stürzt ein Modus ab, geht es zurück auf Home. Stürzt Home selbst ab, wird
es mit Backoff neu gestartet.
"""
from __future__ import annotations

import json
import logging
import os
import signal
import time
from queue import Empty, Queue

from . import config, sysmon
from .actions import ACTION_TO_MODE, Action
from .input_evdev import EvdevInput
from .input_socket import SocketInput
from .process_manager import ProcessManager

log = logging.getLogger("launcher")

HOME = "home"


class Launcher:
    def __init__(self):
        self.settings = config.load_settings()
        self.logs_dir = config.logs_dir(self.settings)
        self.queue: Queue = Queue()
        self.pm = ProcessManager(config.load_modes(), self.logs_dir)
        self.inputs = []
        self.running = True
        self.dev_quit = bool(self.settings.get("launcher", {}).get("dev_emergency_exit", True))
        self.status_interval = float(self.settings.get("launcher", {}).get("status_interval", 60))
        self.state_file = config.runtime_dir() / "kitt-launcher.state"
        self._home_fail_times: list[float] = []

    # -- Setup -----------------------------------------------------------
    def start_inputs(self) -> None:
        try:
            ev = EvdevInput(config.load_keymap(), self.queue)
            ev.start()
            self.inputs.append(ev)
        except Exception as exc:  # evdev nicht verfügbar o. ä.
            log.error("evdev-Eingabe nicht verfügbar: %s", exc)
        try:
            so = SocketInput(config.socket_path(), self.queue)
            so.start()
            self.inputs.append(so)
        except Exception as exc:
            log.error("Steuer-Socket nicht verfügbar: %s", exc)

    def _write_state(self) -> None:
        state = {
            "mode": self.pm.current.name if self.pm.current else None,
            "pid": self.pm.proc.pid if self.pm.proc else None,
            "since": time.time() - (time.monotonic() - self.pm.started_at) if self.pm.current else None,
        }
        try:
            tmp = self.state_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(state))
            os.replace(tmp, self.state_file)
        except OSError:
            pass

    # -- Modi ------------------------------------------------------------
    def switch(self, mode: str) -> None:
        if self.pm.current and self.pm.current.name == mode and self.pm.is_running():
            log.info("Modus %s läuft bereits, ignoriert", mode)
            return
        if self.pm.is_running():
            self.pm.stop()
        ok = self.pm.start(mode)
        if not ok and mode != HOME:
            log.warning("Fallback auf Home")
            self.pm.start(HOME)
        self._write_state()

    def go_home(self) -> None:
        # Crash-Loop-Schutz: 3 schnelle Abstürze -> 10 s Pause
        now = time.monotonic()
        self._home_fail_times = [t for t in self._home_fail_times if now - t < 30]
        if len(self._home_fail_times) >= 3:
            log.error("Home stürzt wiederholt ab, warte 10 s")
            time.sleep(10)
            self._home_fail_times.clear()
        self.switch(HOME)

    def handle(self, action: Action) -> None:
        if action == Action.QUIT:
            if self.dev_quit:
                log.info("Emergency Exit (ESC)")
                self.running = False
            else:
                log.info("ESC ignoriert (dev_emergency_exit = false)")
            return
        if action == Action.STATUS:
            log.info("Status: mode=%s %s", self.pm.current.name if self.pm.current else None, sysmon.format_line())
            return
        mode = ACTION_TO_MODE.get(action)
        if mode:
            log.info("Action %s -> Modus %s", action.value, mode)
            self.switch(mode)

    # -- Hauptschleife ---------------------------------------------------
    def run(self) -> None:
        log.info("KITT-Cart Launcher startet (pid %d)", os.getpid())
        log.info("System: %s", sysmon.format_line())
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))
        self.start_inputs()
        self.go_home()
        last_status = time.monotonic()
        while self.running:
            try:
                action = self.queue.get(timeout=0.5)
            except Empty:
                action = None
            if action is not None:
                try:
                    self.handle(action)
                except Exception:
                    log.exception("Fehler bei Action %s", action)
            # Ist der aktuelle Modus von selbst beendet worden?
            code = self.pm.poll()
            if self.pm.current is not None and code is not None:
                name = self.pm.current.name
                runtime = time.monotonic() - self.pm.started_at
                self.pm.stop()
                if name == HOME:
                    log.warning("Home beendet (exit %s nach %.1fs), starte neu", code, runtime)
                    if runtime < 5:
                        self._home_fail_times.append(time.monotonic())
                else:
                    log.info("Modus %s beendet (exit %s), zurück zu Home", name, code)
                self.go_home()
            now = time.monotonic()
            if now - last_status >= self.status_interval:
                log.info("Status: mode=%s %s", self.pm.current.name if self.pm.current else None, sysmon.format_line())
                last_status = now
        self.shutdown()

    def shutdown(self) -> None:
        log.info("Launcher fährt herunter")
        self.pm.stop()
        for inp in self.inputs:
            try:
                inp.stop()
            except Exception:
                pass
        try:
            self.state_file.unlink(missing_ok=True)
        except OSError:
            pass
        log.info("Launcher beendet")
