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

from . import config, sysmon, theme, wled, pxn_led
from .joystick import JoystickBridge
from .actions import ACTION_TO_MODE, Action
from .input_evdev import EvdevInput
from .dpad_remap import DPadRemap
from .volume_knob import VolumeKnob
from .music_knob import MusicKnob
from .input_socket import SocketInput
from .process_manager import ProcessManager

log = logging.getLogger("launcher")
TALK_MODES = ("hal",)          # Modi, die die Sprechtaste (Action talk) verstehen

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
        self.announce_enabled = bool(self.settings.get("launcher", {}).get("announce", True))
        self.boot_seconds = float(self.settings.get("launcher", {}).get("boot_seconds", 0))
        att = self.settings.get("attract", {})
        self.attract_enabled = bool(att.get("enabled", True))
        self.attract_idle = float(att.get("idle_minutes", 5.0)) * 60.0
        self.attract_every = float(att.get("every_seconds", 180.0))
        self.attract_on = False
        self.attract_next = 0.0
        self.attract_recent: list[str] = []
        self.last_input = time.monotonic()
        self.led_back_at: float | None = None
        self.led_back_mode = HOME

    def announce(self, group: str) -> None:
        """Vorgerenderte Ansage abspielen (nicht-blockierend, scheitert leise)."""
        if not self.announce_enabled:
            return
        try:
            from kitt import announce
            target = ""
            try:
                target = config._load("audio.toml").get("output", {}).get("target", "")
            except Exception:
                pass
            announce.play(group, target)
        except Exception as exc:
            log.debug("Ansage %s: %s", group, exc)

    # -- Setup -----------------------------------------------------------
    def prefetch_models(self) -> None:
        """Modelldateien einmal lesen, damit sie im RAM-Cache liegen (F5 lädt dann in Sekunden statt Minuten).
        Läuft mit niedrigster IO-Priorität im Hintergrund und stört die anderen Modi nicht."""
        if not self.settings.get("launcher", {}).get("prefetch_models", True):
            return
        try:
            from kitt import config as kcfg
            k = kcfg.load()
            files = [kcfg.path(k["stt"]["models_dir"]) / k["stt"]["model"],
                     kcfg.path(k["llm"]["models_dir"]) / k["llm"]["model"],
                     kcfg.path(k["vad"]["model"]),
                     kcfg.path(k["tts"]["voices_dir"]) / (k["tts"]["voice"] + ".onnx")]
        except Exception as exc:
            log.warning("Prefetch: Konfiguration nicht lesbar: %s", exc)
            return
        files = [str(f) for f in files if f.exists()]
        if not files:
            return
        import shutil
        import subprocess
        cmd = (["ionice", "-c", "3"] if shutil.which("ionice") else []) + ["nice", "-n", "19", "cat"] + files
        log.info("Prefetch: %d Modelldateien in den Cache lesen", len(files))

        def run():
            t0 = time.monotonic()
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                log.info("Prefetch fertig nach %.0fs", time.monotonic() - t0)
            except Exception as exc:
                log.warning("Prefetch fehlgeschlagen: %s", exc)

        import threading
        threading.Thread(target=run, name="prefetch", daemon=True).start()

    def start_inputs(self) -> None:
        try:
            dp = DPadRemap(self.settings.get("buttons", {}))
            dp.start()
            self.inputs.append(dp)
            self.dpad = dp
        except Exception as exc:
            log.warning("D-Pad Remapper nicht gestartet: %s", exc)
        try:
            ev = EvdevInput(config.load_keymap(), self.queue)
            ev.start()
            self.inputs.append(ev)
        except Exception as exc:  # evdev nicht verfügbar o. ä.
            log.error("evdev-Eingabe nicht verfügbar: %s", exc)
        try:
            vol_cfg = self.settings.get("volume", {})
            if vol_cfg.get("enabled", True):
                vk = VolumeKnob(vol_cfg)
                vk.start()
                self.inputs.append(vk)
        except Exception as exc:
            log.warning("Lautstärkeknopf nicht gestartet: %s", exc)
        try:
            mus_cfg = self.settings.get("music", {})
            if mus_cfg.get("knob_enabled", True):
                mk = MusicKnob(mus_cfg)
                mk.start()
                self.inputs.append(mk)
        except Exception as exc:
            log.warning("Musikknopf nicht gestartet: %s", exc)
        try:
            jb = JoystickBridge()
            jb.start()
            self.inputs.append(jb)
        except Exception as exc:
            log.warning("JoystickBridge nicht gestartet: %s", exc)
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
    def effective_mode(self, mode: str) -> str:
        """Themen können Modi ersetzen (themes.toml: modes = { viz_psychedelic = "trip" })."""
        repl = theme.current().get("modes", {})
        if isinstance(repl, dict) and repl.get(mode) in self.pm.modes:
            return str(repl[mode])
        return mode

    def switch(self, mode: str) -> str:
        """Startet den Modus (bzw. seinen Ersatz im aktuellen Thema) und gibt den tatsächlichen Modusnamen zurück."""
        eff = self.effective_mode(mode)
        if eff != mode:
            log.info("Thema %s: Modus %s -> %s", theme.current_name() or "standard", mode, eff)
        mode = eff
        if self.pm.current and self.pm.current.name == mode and self.pm.is_running():
            log.info("Modus %s läuft bereits, ignoriert", mode)
            return mode
        if self.pm.is_running():
            self.pm.stop()
        ok = self.pm.start(mode, {"KITT_THEME": theme.current_name()})
        if not ok and mode != HOME:
            log.warning("Fallback auf Home")
            self.pm.start(HOME)
        self._write_state()
        try:
            col = None
            if mode == HOME:                       # Taxistand leuchtet in der Farbe des gewählten Themas
                col = [int(c * 255) for c in theme.current().get("color_a", [1.0, 0.75, 0.0])]
            wled.apply_mode_async(mode, col)
            if mode == HOME and col:
                pxn_led.set_color_async(*col)       # Tasten in der Themenfarbe
            else:
                pxn_led.apply_mode_async(mode)
        except Exception as exc:
            log.debug("WLED-Fehler: %s", exc)
        return mode

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
        if action in (Action.HORN, Action.FX):
            from launcher import sfx
            sfx.play("horn" if action == Action.HORN else "fx")
            cur = self.pm.current.name if self.pm.current else HOME
            try:
                wled.apply_mode_async(action.value)                       # kurzer LED-Blitz, danach zurück zum Modusprofil
                pxn_led.set_color_async(255, 255, 255)
            except Exception as exc:
                log.debug("LED-Fehler: %s", exc)
            self.led_back_at = time.monotonic() + (1.5 if action == Action.HORN else 1.0)
            self.led_back_mode = cur
            return
        if action == Action.TALK:
            cur = self.pm.current.name if self.pm.current and self.pm.is_running() else None
            if cur in TALK_MODES and getattr(self, "dpad", None):
                log.info("Sprechtaste -> %s (F15)", cur)
                self.dpad.inject_talk()
            else:
                log.info("Sprechtaste ignoriert: läuft %s, Sprechmodus nur bei %s", cur, ", ".join(TALK_MODES))
            return
        mode = ACTION_TO_MODE.get(action)
        if mode:
            log.info("Action %s -> Modus %s", action.value, mode)
            eff = self.effective_mode(mode)
            already = self.pm.current and self.pm.current.name == eff and self.pm.is_running()
            self.switch(mode)
            if not already:
                self.announce(eff)             # Ansage des tatsächlich gestarteten Modus in der Themenstimme

    # -- Vorführmodus ----------------------------------------------------
    ATTRACT_BASE = ("viz_psychedelic", "blackhole", "hal", "slots", "campfire", "error")

    def _idle_seconds(self) -> float:
        last = self.last_input
        dp = getattr(self, "dpad", None)
        if dp is not None:
            last = max(last, getattr(dp, "last_event", 0.0))
        return time.monotonic() - last

    def _attract_tick(self) -> None:
        """Nach idle_minutes ohne Eingabe wechselt der Launcher alle every_seconds durch die Modi des Themas
        (Tasten 2-7, nie derselbe zweimal hintereinander); jede Eingabe beendet den Vorführmodus."""
        if not self.attract_enabled:
            return
        now = time.monotonic()
        cur = self.pm.current.name if self.pm.current else None
        if cur in ("boot", "gaming", None):
            return
        if not self.attract_on:
            if self._idle_seconds() < self.attract_idle:
                return
            self.attract_on = True
            self.attract_next = now
            log.info("Vorführmodus an: %.0f min keine Eingabe", self.attract_idle / 60.0)
        if now < self.attract_next:
            return
        self.attract_next = now + self.attract_every
        if self.attract_on and self._idle_seconds() < self.attract_idle:   # Eingabe über das Board (Knüppel usw.)
            self.attract_on = False
            log.info("Vorführmodus aus (Board)")
            return
        pool = [m for m in self.ATTRACT_BASE if self.effective_mode(m) != cur and m not in self.attract_recent[-2:]]
        if not pool:
            return
        import random
        mode = random.choice(pool)
        self.attract_recent.append(mode)
        del self.attract_recent[:-4]
        log.info("Vorführmodus: -> %s", mode)
        eff = self.switch(mode)
        self.announce(eff)

    # -- Hauptschleife ---------------------------------------------------
    def run(self) -> None:
        log.info("KITT-Cart Launcher startet (pid %d)", os.getpid())
        log.info("System: %s", sysmon.format_line())
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))
        self.start_inputs()
        if self.boot_seconds > 0 and "boot" in self.pm.modes:
            self.switch("boot")            # Startbildschirm: endet beim ersten Tastendruck, danach automatisch Home (Board-Tasten wechseln direkt)
            self.announce("boot")
        else:
            self.go_home()
        self.prefetch_models()
        last_status = time.monotonic()
        while self.running:
            try:
                action = self.queue.get(timeout=0.5)
            except Empty:
                action = None
            if action is not None:
                self.last_input = time.monotonic()
                if self.attract_on:
                    self.attract_on = False
                    log.info("Vorführmodus aus (Eingabe)")
                try:
                    self.handle(action)
                except Exception:
                    log.exception("Fehler bei Action %s", action)
            self._attract_tick()
            if self.led_back_at is not None and time.monotonic() >= self.led_back_at:
                self.led_back_at = None
                try:
                    wled.apply_mode_async(self.led_back_mode)
                    pxn_led.apply_mode_async(self.led_back_mode)
                except Exception as exc:
                    log.debug("LED-Fehler: %s", exc)
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
