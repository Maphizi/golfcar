#!/usr/bin/env python3
"""Miracast-Sender: der Pi schickt seinen Bildschirm (labwc-Session mit Launcher, Visualizern und RetroArch) drahtlos an
einen Miracast-Empfänger (z. B. den Dongle "HD Wireless Screen Mirroring", Name 530E1F_P2P).

Weg: Wi-Fi Direct über NetworkManager (Gerät p2p-dev-wlan0, läuft NEBEN dem normalen WLAN, Vodafone und Tailscale bleiben
verbunden), dann die Miracast-Steuerung (RTSP, WFD M1-M7) mit dem Empfänger und der Videostrom als MPEG-TS über RTP:
wf-recorder greift das Bild in der Wayland-Session ab (auch RetroArch unter Xwayland, Shader inklusive, die rechnet der
Pi wie immer selbst), libx264 kodiert (der Pi 5 hat keinen Hardware-H.264-Encoder), ffmpeg schickt es an den Empfänger.

Bewusst NICHT miraclecast: dessen miracle-wifid übernimmt die WLAN-Karte exklusiv (eigener wpa_supplicant), dabei würde
die Vodafone-Verbindung und damit Tailscale abreißen; der Sender-Teil (miracle-wfdctl) ist zudem experimentell.

Schutz des WLANs: der Sender rührt wlan0 und seine Verbindungen nie an. Fällt wlan0 nach dem Aufbau der Wi-Fi-Direct-
Verbindung trotzdem aus (Chip kann die zwei Kanäle nicht gleichzeitig), baut er sofort ab, verbindet wlan0 neu, schreibt
das nach logs/miracast_status.txt und beendet sich mit Code 3 (der Dienst startet dann nicht neu).

    sudo python3 scripts/miracast.py scan [SEK]       Empfänger in der Nähe suchen (Name, MAC, Signal, Miracast-Senke?)
    sudo python3 scripts/miracast.py run              verbinden und senden, bei Abbruch neu versuchen (Dienst)
    sudo python3 scripts/miracast.py run --once [--seconds N]   ein Versuch (Test)
    sudo python3 scripts/miracast.py stop             Wi-Fi-Direct-Verbindung trennen

Einstellungen: config/settings.toml [miracast]. Läuft als root (NetworkManager), das Bild greift es als Session-Benutzer ab.
"""
from __future__ import annotations

import json
import logging
import os
import pwd
import random
import re
import shlex
import signal
import socket
import subprocess
import sys
import threading
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
STATUS = LOG_DIR / "miracast_status.txt"
NM = "org.freedesktop.NetworkManager"
P2P_IF = "org.freedesktop.NetworkManager.Device.WifiP2P"
PEER_IF = "org.freedesktop.NetworkManager.WifiP2PPeer"
DEV_IF = "org.freedesktop.NetworkManager.Device"
DEVICE_TYPE_WIFI_P2P = 30
CON_NAME = "kitt-miracast"
RTSP_PORT = 7236
# WFD-Geräteinfo des Senders: Typ Quelle, Sitzung verfügbar, Steuerport 7236, max. 200 Mbit/s
WFD_IES = "00:00:06:00:90:1c:44:00:c8"
# CEA-Auflösungen (Bit -> Breite, Höhe, Bilder/s) aus der WFD-Spezifikation
CEA = {0: (640, 480, 60), 5: (1280, 720, 30), 6: (1280, 720, 60), 7: (1920, 1080, 30), 8: (1920, 1080, 60)}
EXIT_WLAN_CONFLICT = 3

log = logging.getLogger("miracast")
DEFAULTS = {"peer": "530E1F", "wifi": "wlan0", "user": "", "width": 1280, "height": 720, "fps": 30, "kbps": 4000,
            "audio": "silent", "retry_seconds": 20, "connect_timeout": 45, "capture": ""}


def load_cfg() -> dict:
    cfg = dict(DEFAULTS)
    try:
        cfg.update(tomllib.loads((ROOT / "config" / "settings.toml").read_text()).get("miracast", {}))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        log.warning("settings.toml [miracast] nicht lesbar (%s), nehme Standardwerte", exc)
    return cfg


def set_status(text: str) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        STATUS.write_text(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}\n")
    except OSError:
        pass
    log.info("Status: %s", text)


def sh(cmd: list[str], timeout: float = 30.0, check: bool = False) -> subprocess.CompletedProcess:
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and res.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)}: {res.stderr.strip() or res.stdout.strip()}")
    return res


# -- NetworkManager über D-Bus (busctl ist immer da, keine Python-Pakete nötig) ----------------------------------
def bus(*args: str) -> object:
    res = sh(["busctl", "--json=short", *args], check=True)
    out = res.stdout.strip()
    return json.loads(out)["data"] if out else None


def prop(path: str, iface: str, name: str):
    return bus("get-property", NM, path, iface, name)


def p2p_device(wifi: str) -> str | None:
    """D-Bus-Pfad des Wi-Fi-Direct-Geräts zu wifi (p2p-dev-wlan0)."""
    for path in bus("call", NM, "/org/freedesktop/NetworkManager", NM, "GetDevices")[0]:
        try:
            if prop(path, DEV_IF, "DeviceType") == DEVICE_TYPE_WIFI_P2P and prop(path, DEV_IF, "Interface") == f"p2p-dev-{wifi}":
                return path
        except (RuntimeError, KeyError, ValueError):
            continue
    return None


def wfd_kind(ies: list[int]) -> str:
    """Gerätetyp aus den WFD-IEs des Partners (Unterelement 0, Bits 0-1)."""
    i = 0
    while i + 3 <= len(ies):
        sid, ln = ies[i], (ies[i + 1] << 8) | ies[i + 2]
        if sid == 0 and ln >= 2 and i + 5 <= len(ies):
            t = ((ies[i + 3] << 8) | ies[i + 4]) & 0x3
            return {0: "Quelle", 1: "Miracast-Empfänger", 2: "Zweitempfänger", 3: "Quelle+Empfänger"}[t]
        i += 3 + ln
    return "kein Miracast"


def find_peers(dev: str, seconds: float) -> list[dict]:
    try:
        bus("call", NM, dev, P2P_IF, "StartFind", "a{sv}", "1", "timeout", "i", str(int(max(seconds, 5)) + 5))
    except RuntimeError as exc:
        log.warning("Suche nicht gestartet: %s", exc)
    end = time.monotonic() + seconds
    peers: dict[str, dict] = {}
    while time.monotonic() < end:
        time.sleep(1.0)
        for p in prop(dev, P2P_IF, "Peers") or []:
            try:
                peers[p] = {"path": p, "name": prop(p, PEER_IF, "Name"), "mac": prop(p, PEER_IF, "HwAddress"),
                            "signal": prop(p, PEER_IF, "Strength"), "kind": wfd_kind(prop(p, PEER_IF, "WfdIEs") or [])}
            except RuntimeError:
                continue
    try:
        bus("call", NM, dev, P2P_IF, "StopFind")
    except RuntimeError:
        pass
    return list(peers.values())


def match_peer(peers: list[dict], want: str) -> dict | None:
    w = want.lower().replace("-", ":")
    for p in sorted(peers, key=lambda d: -int(d.get("signal") or 0)):
        if w and (w in str(p["name"]).lower() or w == str(p["mac"]).lower()):
            return p
    return None


def wlan_state(wifi: str) -> tuple[bool, str]:
    """(verbunden, Verbindungsname) des normalen WLANs."""
    res = sh(["nmcli", "-g", "GENERAL.STATE,GENERAL.CONNECTION", "device", "show", wifi])
    lines = res.stdout.strip().splitlines() + ["", ""]
    return lines[0].startswith("100"), lines[1].strip()


def p2p_up(cfg: dict, peer: dict) -> tuple[str, str]:
    """Wi-Fi-Direct-Verbindung zum Empfänger aufbauen. Liefert (IP-Interface, eigene IP)."""
    dev_if = f"p2p-dev-{cfg['wifi']}"
    exists = sh(["nmcli", "-g", "connection.id", "connection", "show", CON_NAME]).returncode == 0
    props = ["wifi-p2p.peer", peer["mac"], "wifi-p2p.wfd-ies", WFD_IES, "connection.autoconnect", "no",
             "ipv4.method", "auto", "ipv6.method", "disabled", "connection.interface-name", dev_if]
    if exists:
        sh(["nmcli", "connection", "modify", CON_NAME, *props], check=True)
    else:
        sh(["nmcli", "connection", "add", "type", "wifi-p2p", "con-name", CON_NAME, "ifname", dev_if, *props], check=True)
    sh(["nmcli", "--wait", str(int(cfg["connect_timeout"])), "connection", "up", CON_NAME],
       timeout=float(cfg["connect_timeout"]) + 15.0, check=True)
    ipif = sh(["nmcli", "-g", "GENERAL.IP-IFACE", "device", "show", dev_if]).stdout.strip()
    addr = ""
    for _ in range(20):
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", sh(["ip", "-4", "-o", "addr", "show", "dev", ipif]).stdout) if ipif else None
        if m:
            addr = m.group(1)
            break
        time.sleep(1.0)
    if not addr:
        raise RuntimeError(f"keine IP auf {ipif or '?'}")
    return ipif, addr


def p2p_down() -> None:
    sh(["nmcli", "connection", "down", CON_NAME], timeout=20.0)


# -- Bildquelle -----------------------------------------------------------------------------------------------------
def session_env(cfg: dict) -> tuple[str, dict]:
    """Benutzer der labwc-Session und seine Umgebung (XDG_RUNTIME_DIR, WAYLAND_DISPLAY)."""
    user = cfg.get("user") or os.environ.get("KITT_USER") or os.environ.get("SUDO_USER") or ""
    if not user:
        user = pwd.getpwuid(1000).pw_name
    uid = pwd.getpwnam(user).pw_uid
    run = f"/run/user/{uid}"
    sock = next((p.name for p in sorted(Path(run).glob("wayland-*")) if p.is_socket()), "wayland-0") if Path(run).exists() else "wayland-0"
    return user, {"XDG_RUNTIME_DIR": run, "WAYLAND_DISPLAY": sock}


def stream_cmds(cfg: dict, sink_ip: str, rtp_port: int, audio: str) -> tuple[list[str], list[str]]:
    """wf-recorder (Bild, H.264 in MPEG-TS auf stdout) | ffmpeg (stille Tonspur dazu, RTP an den Empfänger)."""
    w, h, fps, kbps = int(cfg["width"]), int(cfg["height"]), int(cfg["fps"]), int(cfg["kbps"])
    if cfg.get("capture"):
        cap = shlex.split(str(cfg["capture"]).format(w=w, h=h, fps=fps, kbps=kbps))
    else:
        cap = ["wf-recorder", "-y", "-c", "libx264", "-r", str(fps), "-F", f"scale={w}:{h}", "-x", "yuv420p",
               "-p", "preset=ultrafast", "-p", "tune=zerolatency", "-p", "profile=baseline",
               "-p", f"x264-params=keyint={fps}:min-keyint={fps}:repeat-headers=1:vbv-maxrate={kbps}:vbv-bufsize={kbps // 4}:bitrate={kbps}",
               "-m", "mpegts", "-f", "pipe:1"]
    out = ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-fflags", "+genpts+nobuffer", "-probesize", "300k",
           "-analyzeduration", "500000", "-i", "pipe:0"]
    if audio != "none":
        out += ["-re", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac" if audio == "aac" else "pcm_bluray", "-ar", "48000", "-ac", "2"]
        if audio == "aac":
            out += ["-b:a", "96k"]
    # Miracast-PIDs wie in der WFD-Spezifikation: PCR/Video 0x1011, Audio 0x1100
    out += ["-streamid", "0:0x1011"] + (["-streamid", "1:0x1100"] if audio != "none" else [])
    out += ["-c:v", "copy", "-shortest", "-muxdelay", "0", "-muxpreload", "0", "-f", "rtp_mpegts", f"rtp://{sink_ip}:{rtp_port}?pkt_size=1328"]
    return cap, out


class Streamer:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.procs: list[subprocess.Popen] = []

    def start(self, sink_ip: str, rtp_port: int, audio: str) -> None:
        self.stop()
        user, env = session_env(self.cfg)
        cap, out = stream_cmds(self.cfg, sink_ip, rtp_port, audio)
        envs = [f"{k}={v}" for k, v in env.items()]
        cap = (["runuser", "-u", user, "--", "env", *envs] if os.geteuid() == 0 else ["env", *envs]) + cap
        log.info("Strom an %s:%d (%s): %s | %s", sink_ip, rtp_port, audio, " ".join(cap), " ".join(out))
        logf = open(LOG_DIR / "miracast_stream.log", "a")
        p1 = subprocess.Popen(cap, stdout=subprocess.PIPE, stderr=logf, start_new_session=True)
        p2 = subprocess.Popen(out, stdin=p1.stdout, stderr=logf, start_new_session=True)
        p1.stdout.close()
        self.procs = [p1, p2]

    def alive(self) -> bool:
        return bool(self.procs) and all(p.poll() is None for p in self.procs)

    def stop(self) -> None:
        for p in self.procs:
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGTERM)
                    p.wait(timeout=3)
                except (ProcessLookupError, subprocess.TimeoutExpired, PermissionError):
                    try:
                        os.killpg(p.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
        self.procs = []


# -- Miracast-Steuerung (RTSP, WFD M1-M7, Keepalive) ----------------------------------------------------------------
class Rtsp:
    """Eine RTSP-Verbindung mit dem Empfänger: Nachrichten lesen und schreiben (Anfragen und Antworten gemischt)."""

    def __init__(self, conn: socket.socket):
        self.conn = conn
        self.buf = b""
        self.cseq = 0

    def read(self, timeout: float) -> dict | None:
        self.conn.settimeout(timeout)
        while b"\r\n\r\n" not in self.buf:
            chunk = self.conn.recv(4096)
            if not chunk:
                raise ConnectionError("Empfänger hat die Verbindung geschlossen")
            self.buf += chunk
        head, rest = self.buf.split(b"\r\n\r\n", 1)
        lines = head.decode("utf-8", "replace").split("\r\n")
        hdr = {}
        for ln in lines[1:]:
            if ":" in ln:
                k, v = ln.split(":", 1)
                hdr[k.strip().lower()] = v.strip()
        n = int(hdr.get("content-length", "0") or 0)
        while len(rest) < n:
            chunk = self.conn.recv(4096)
            if not chunk:
                raise ConnectionError("Empfänger hat die Verbindung geschlossen")
            rest += chunk
        body, self.buf = rest[:n].decode("utf-8", "replace"), rest[n:]
        first = lines[0].split(" ")
        msg = {"hdr": hdr, "body": body, "line": lines[0]}
        if first[0].startswith("RTSP/"):
            msg["status"] = int(first[1]) if len(first) > 1 and first[1].isdigit() else 0
        else:
            msg["method"], msg["uri"] = first[0], first[1] if len(first) > 1 else "*"
        log.debug("<- %s %s", lines[0], body.replace("\r\n", " | ")[:200])
        return msg

    def request(self, method: str, uri: str, body: str = "", extra: dict | None = None) -> int:
        self.cseq += 1
        hdr = {"CSeq": str(self.cseq), **(extra or {})}
        if body:
            hdr.update({"Content-Type": "text/parameters", "Content-Length": str(len(body.encode()))})
        self._send(f"{method} {uri} RTSP/1.0", hdr, body)
        return self.cseq

    def reply(self, req: dict, status: str = "200 OK", extra: dict | None = None, body: str = "") -> None:
        hdr = {"CSeq": req["hdr"].get("cseq", "0"), **(extra or {})}
        if body:
            hdr.update({"Content-Type": "text/parameters", "Content-Length": str(len(body.encode()))})
        self._send(f"RTSP/1.0 {status}", hdr, body)

    def _send(self, first: str, hdr: dict, body: str) -> None:
        txt = first + "\r\n" + "".join(f"{k}: {v}\r\n" for k, v in hdr.items()) + "\r\n" + body
        log.debug("-> %s %s", first, body.replace("\r\n", " | ")[:200])
        self.conn.sendall(txt.encode())


def parse_params(body: str) -> dict:
    out = {}
    for ln in body.replace("\r\n", "\n").split("\n"):
        if ":" in ln:
            k, v = ln.split(":", 1)
            out[k.strip().lower()] = v.strip()
    return out


def choose_video(sink_formats: str, want: tuple[int, int, int]) -> tuple[int, tuple[int, int, int]]:
    """CEA-Bit wählen: die gewünschte Auflösung, wenn der Empfänger sie kann, sonst die größte bis 1080p30, sonst 640x480."""
    cea = 0x1
    try:
        f = sink_formats.split()
        cea = int(f[4], 16) if len(f) > 4 else 0x1
    except ValueError:
        pass
    order = [b for b, v in CEA.items() if v == want] + [7, 6, 5, 0]
    for b in order:
        if cea & (1 << b) and CEA[b][2] <= 60:
            return b, CEA[b]
    return 0, CEA[0]


def choose_audio(sink_audio: str, pref: str) -> str:
    """'none', 'aac' oder 'lpcm' (stille Tonspur; viele Empfänger erwarten eine)."""
    a = sink_audio.upper()
    if pref == "none" or not a or a == "NONE":
        return "none"
    return "aac" if "AAC" in a else "lpcm"


class Session:
    """Ablauf mit einem Empfänger: M1 OPTIONS, M2 (vom Empfänger), M3 GET_PARAMETER, M4 SET_PARAMETER (Format),
    M5 Auslöser SETUP, M6 SETUP und M7 PLAY vom Empfänger, dann Strom + Keepalive (M16) bis TEARDOWN/Abbruch."""

    def __init__(self, cfg: dict, conn: socket.socket, sink_ip: str, my_ip: str, stop: threading.Event, wlan_guard=None):
        self.cfg, self.r, self.sink_ip, self.my_ip, self.stop_ev = cfg, Rtsp(conn), sink_ip, my_ip, stop
        self.streamer = Streamer(cfg)
        self.wlan_guard = wlan_guard
        self.session_id = f"{random.randint(10**7, 10**8 - 1)}"
        self.rtp_port = 19000
        self.audio = "none"
        self.fmt = CEA[5]

    def _expect(self, cseq: int, timeout: float = 10.0) -> dict:
        """Auf die Antwort zu cseq warten; Anfragen des Empfängers dazwischen beantworten."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            msg = self.r.read(max(0.5, end - time.monotonic()))
            if "status" in msg:
                if int(msg["hdr"].get("cseq", -1)) == cseq:
                    if msg["status"] != 200:
                        raise RuntimeError(f"Empfänger lehnt ab: {msg['line']}")
                    return msg
                continue
            self._handle(msg)
        raise TimeoutError(f"keine Antwort auf CSeq {cseq}")

    def _handle(self, req: dict) -> str:
        m = req["method"]
        if m == "OPTIONS":
            self.r.reply(req, extra={"Public": "org.wfa.wfd1.0, SETUP, TEARDOWN, PLAY, PAUSE, GET_PARAMETER, SET_PARAMETER"})
        elif m == "SETUP":
            tr = req["hdr"].get("transport", "")
            mm = re.search(r"client_port=(\d+)", tr)
            if mm:
                self.rtp_port = int(mm.group(1))
            self.r.reply(req, extra={"Session": f"{self.session_id};timeout=30",
                                     "Transport": f"RTP/AVP/UDP;unicast;client_port={self.rtp_port};server_port=19000-19001"})
        elif m == "PLAY":
            self.r.reply(req, extra={"Session": self.session_id, "Range": "npt=now-"})
            self.streamer.start(self.sink_ip, self.rtp_port, self.audio)
            set_status(f"sendet an {self.sink_ip} ({self.fmt[0]}x{self.fmt[1]}@{self.fmt[2]}, Ton {self.audio})")
        elif m == "PAUSE":
            self.r.reply(req, extra={"Session": self.session_id})
            self.streamer.stop()
        elif m == "TEARDOWN":
            self.r.reply(req, extra={"Session": self.session_id})
            self.streamer.stop()
            return "teardown"
        else:                                                              # GET/SET_PARAMETER (Keepalive, IDR-Wunsch)
            self.r.reply(req, extra={"Session": self.session_id} if "session" in req["hdr"] else None)
        return ""

    def run(self, max_seconds: float = 0.0) -> None:
        r = self.r
        try:
            self._expect(r.request("OPTIONS", "*", extra={"Require": "org.wfa.wfd1.0"}))                       # M1
            end = time.monotonic() + 5.0                                   # M2: OPTIONS des Empfängers abwarten
            while time.monotonic() < end:
                try:
                    msg = r.read(max(0.2, end - time.monotonic()))
                except socket.timeout:
                    break
                if "method" in msg:
                    self._handle(msg)
                    if msg["method"] == "OPTIONS":
                        break
            m3 = self._expect(r.request("GET_PARAMETER", "rtsp://localhost/wfd1.0",
                                        "wfd_video_formats\r\nwfd_audio_codecs\r\nwfd_client_rtp_ports\r\n"))     # M3
            p = parse_params(m3["body"])
            log.info("Empfänger kann: Video %s | Ton %s | Ports %s", p.get("wfd_video_formats"), p.get("wfd_audio_codecs"),
                     p.get("wfd_client_rtp_ports"))
            mm = re.search(r"unicast (\d+)", p.get("wfd_client_rtp_ports", ""))
            if mm:
                self.rtp_port = int(mm.group(1))
            bit, self.fmt = choose_video(p.get("wfd_video_formats", ""),
                                         (int(self.cfg["width"]), int(self.cfg["height"]), int(self.cfg["fps"])))
            self.cfg = {**self.cfg, "width": self.fmt[0], "height": self.fmt[1], "fps": self.fmt[2]}
            self.streamer.cfg = self.cfg
            self.audio = choose_audio(p.get("wfd_audio_codecs", ""), str(self.cfg["audio"]))
            audio_line = {"none": "none", "aac": "AAC 00000001 00", "lpcm": "LPCM 00000002 00"}[self.audio]
            body = (f"wfd_video_formats: {bit << 3:02x} 00 01 01 {1 << bit:08x} 00000000 00000000 00 0000 0000 00 none none\r\n"
                    f"wfd_audio_codecs: {audio_line}\r\n"
                    f"wfd_presentation_URL: rtsp://{self.my_ip}/wfd1.0/streamid=0 none\r\n"
                    f"wfd_client_rtp_ports: RTP/AVP/UDP;unicast {self.rtp_port} 0 mode=play\r\n")
            self._expect(r.request("SET_PARAMETER", "rtsp://localhost/wfd1.0", body))                           # M4
            self._expect(r.request("SET_PARAMETER", "rtsp://localhost/wfd1.0", "wfd_trigger_method: SETUP\r\n"))  # M5
            start = time.monotonic()
            next_keep = start + 20.0
            while not self.stop_ev.is_set():                                  # M6/M7 kommen hier, danach Keepalive
                if max_seconds and time.monotonic() - start > max_seconds:
                    log.info("Testzeit vorbei")
                    break
                if self.wlan_guard and not self.wlan_guard():
                    raise WlanConflict()
                if time.monotonic() >= next_keep and self.streamer.procs:
                    r.request("GET_PARAMETER", "rtsp://localhost/wfd1.0", extra={"Session": self.session_id})  # M16
                    next_keep = time.monotonic() + 20.0
                if self.streamer.procs and not self.streamer.alive():
                    raise RuntimeError("Bildstrom beendet (siehe logs/miracast_stream.log)")
                try:
                    msg = r.read(1.0)
                except socket.timeout:
                    continue
                if "method" in msg and self._handle(msg) == "teardown":
                    log.info("Empfänger beendet die Sitzung")
                    break
        finally:
            self.streamer.stop()


class WlanConflict(Exception):
    pass


def serve(cfg: dict, my_ip: str, stop: threading.Event, max_seconds: float, wlan_guard) -> None:
    """Auf den Empfänger warten (er verbindet sich mit Port 7236 des Senders) und eine Sitzung führen."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((my_ip, RTSP_PORT))
    srv.listen(1)
    srv.settimeout(1.0)
    log.info("Warte auf den Empfänger an %s:%d", my_ip, RTSP_PORT)
    end = time.monotonic() + 40.0
    try:
        while not stop.is_set():
            if time.monotonic() > end:
                raise TimeoutError("Empfänger meldet sich nicht auf Port 7236")
            if not wlan_guard():
                raise WlanConflict()
            try:
                conn, (ip, _) = srv.accept()
            except socket.timeout:
                continue
            log.info("Empfänger verbunden: %s", ip)
            with conn:
                Session(cfg, conn, ip, my_ip, stop, wlan_guard).run(max_seconds)
            return
    finally:
        srv.close()


def run(cfg: dict, once: bool, max_seconds: float) -> int:
    stop = threading.Event()
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda *_: stop.set())
    wifi = str(cfg["wifi"])
    while not stop.is_set():
        dev = p2p_device(wifi)
        if not dev:
            set_status(f"kein Wi-Fi-Direct-Gerät p2p-dev-{wifi} (NetworkManager zu alt oder Chip ohne P2P)")
            return 2
        was_up, wlan_con = wlan_state(wifi)
        log.info("WLAN %s: %s", wifi, f"verbunden mit {wlan_con}" if was_up else "nicht verbunden")
        peer = match_peer(find_peers(dev, 12.0), str(cfg["peer"]))
        if not peer:
            set_status(f"Empfänger '{cfg['peer']}' nicht gefunden")
            if once:
                return 1
            stop.wait(float(cfg["retry_seconds"]))
            continue
        log.info("Empfänger: %s (%s, %s, Signal %s)", peer["name"], peer["mac"], peer["kind"], peer["signal"])

        def guard() -> bool:                                               # WLAN darf nicht wegfallen
            return (not was_up) or wlan_state(wifi)[0]

        try:
            set_status(f"verbinde mit {peer['name']}")
            ipif, my_ip = p2p_up(cfg, peer)
            log.info("Wi-Fi Direct steht: %s, eigene IP %s", ipif, my_ip)
            for _ in range(5):                                             # die ersten Sekunden genau hinsehen
                if not guard():
                    raise WlanConflict()
                time.sleep(1.0)
            serve(cfg, my_ip, stop, max_seconds, guard)
            set_status("Sitzung beendet")
        except WlanConflict:
            p2p_down()
            sh(["nmcli", "device", "connect", wifi], timeout=40.0)
            set_status(f"ABGEBROCHEN: {wifi} hat die Verbindung verloren, sobald Wi-Fi Direct lief. Der Chip schafft "
                       "beides nicht gleichzeitig -> zweiter USB-WLAN-Stick für Miracast ([miracast] wifi = \"wlan1\").")
            return EXIT_WLAN_CONFLICT
        except (RuntimeError, TimeoutError, ConnectionError, OSError, subprocess.TimeoutExpired) as exc:
            set_status(f"Fehler: {exc}")
        finally:
            p2p_down()
        if once:
            return 0
        stop.wait(float(cfg["retry_seconds"]))
    return 0


def main() -> int:
    logging.basicConfig(level=logging.DEBUG if os.environ.get("KITT_MIRACAST_DEBUG") else logging.INFO,
                        format="%(asctime)s %(levelname)-5s %(message)s",
                        handlers=[logging.StreamHandler(sys.stdout)])
    LOG_DIR.mkdir(exist_ok=True)
    cfg = load_cfg()
    args = sys.argv[1:] or ["scan"]
    if args[0] == "scan":
        dev = p2p_device(str(cfg["wifi"]))
        if not dev:
            print(f"Kein Wi-Fi-Direct-Gerät p2p-dev-{cfg['wifi']} in NetworkManager.")
            return 2
        secs = float(args[1]) if len(args) > 1 else 15.0
        print(f"Suche {secs:.0f} s über p2p-dev-{cfg['wifi']} ...")
        peers = find_peers(dev, secs)
        for p in sorted(peers, key=lambda d: -int(d.get("signal") or 0)):
            mark = "  <- passt zu [miracast] peer" if match_peer([p], str(cfg["peer"])) else ""
            print(f"  {p['name'] or '?':28s} {p['mac']}  Signal {p['signal']:>3}  {p['kind']}{mark}")
        if not peers:
            print("  nichts gefunden (Empfänger an? Er zeigt dann den Bildschirm mit 530E1F_P2P)")
        return 0
    if args[0] == "stop":
        p2p_down()
        return 0
    if args[0] == "run":
        once = "--once" in args
        secs = float(args[args.index("--seconds") + 1]) if "--seconds" in args else 0.0
        return run(cfg, once, secs)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
