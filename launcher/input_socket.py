"""Steuer-Socket: Actions per Unix-Datagram-Socket auslösen.

Dient zum Testen per SSH (scripts/kittctl) und später als Schnittstelle für
weitere Eingabequellen, die nicht als Tastatur erscheinen.
"""
from __future__ import annotations

import logging
import os
import socket
import threading
from pathlib import Path
from queue import Queue

from .actions import parse_action

log = logging.getLogger("input.socket")


class SocketInput(threading.Thread):
    def __init__(self, path: Path, queue: Queue):
        super().__init__(name="socket-input", daemon=True)
        self.path = path
        self.queue = queue
        self._stop_event = threading.Event()
        if self.path.exists():
            self.path.unlink()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self.sock.settimeout(0.5)
        log.info("Steuer-Socket: %s", self.path)

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                data = self.sock.recv(256)
            except socket.timeout:
                continue
            except OSError:
                break
            name = data.decode(errors="ignore").strip()
            action = parse_action(name)
            if action is None:
                log.warning("Unbekannte Action über Socket: %r", name)
                continue
            log.debug("socket -> %s", action.value)
            self.queue.put(action)

    def stop(self) -> None:
        self._stop_event.set()
        try:
            self.sock.close()
        finally:
            if self.path.exists():
                self.path.unlink()


def send(path: Path, action: str) -> None:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.sendto(action.encode(), str(path))
    s.close()
