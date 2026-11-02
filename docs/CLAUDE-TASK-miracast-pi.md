# Aufgabe für Claude Code: Miracast auf Raspberry Pi 5 einrichten

**Ziel:** Der Raspberry Pi 5 soll seinen Bildschirminhalt (RetroPie + RetroArch
mit Shadern) drahtlos auf einen Miracast-Empfänger streamen.

## Gerät

Miracast-Dongle „HD Wireless Screen Mirroring"
- SSID: `530E1F_P2P`
- Protokoll: WiFi Direct / Miracast

## Zugang zum Pi

```
SSH:  ssh -i /home/maphizi/.ssh/id_ed25519 maphizi@100.113.224.68
User: maphizi (hat sudo)
OS:   Raspberry Pi OS Debian Trixie, Kernel 6.18.50+rpt-rpi-2712
HW:   Raspberry Pi 5 Model B, 8 GB RAM, aarch64
```

## Was der Pi-Chip kann

`iw list` zeigt: **P2P-client, P2P-GO, P2P-device** → WiFi Direct wird
vom Chip unterstützt.

Aktuell verbunden:
- WLAN: Vodafone-B814 (Priorität 100, primär)
- Fallback: „S24 FE von Marc-Philip" (Priorität 10, automatisch)
- Tailscale IP: 100.113.224.68 (muss erhalten bleiben!)

## Aufgaben

### 1. miracle-wifid / miraclecast installieren

- Prüfe zuerst: `apt search miracle`
- Falls nicht als Paket vorhanden: aus Source bauen
  (GitHub: albfan/miraclecast)
- Ziel: `miracle-wifid` + `miracle-sinkctl` lauffähig als Sender

### 2. WiFi Direct P2P konfigurieren

- Pi soll sich mit `530E1F_P2P` verbinden und Framebuffer streamen
- Das normale WLAN (wlan0) muss weiterlaufen → P2P ggf. als
  virtuelles Interface (p2p-dev-wlan0 o.ä.)
- Tailscale-Verbindung darf nicht abreißen

### 3. Autostart via systemd

- Beim Boot automatisch Verbindung zum Miracast-Empfänger versuchen
- systemd-Service anlegen, aktivieren

### 4. RetroArch / RetroPie Kompatibilität

- RetroArch nutzt KMS/DRM oder HDMI-Framebuffer
- Wenn Miracast nur über X11/Framebuffer-Capture geht:
  `ffmpeg`-Screen-Grab + Miracast-Sink einrichten
- Shaders müssen weiter funktionieren (GPU-seitig auf dem Pi)

## Wichtige Einschränkungen

- **WLAN nicht unterbrechen** — Tailscale-Erreichbarkeit (100.113.224.68)
  muss zu jeder Zeit erhalten bleiben
- Wenn P2P und WLAN gleichzeitig nicht funktionieren:
  Alternative vorschlagen (z.B. zweiter USB-WLAN-Adapter für P2P)
- Hinweis an Marc: Miracast hat ~50–150 ms Latenz, bei Retro-Gaming
  möglicherweise spürbar

## Erwarteter Bericht

1. Was wurde installiert / konfiguriert
2. Ob die Verbindung zu `530E1F_P2P` hergestellt werden konnte
3. Falls nicht möglich: Erklärung + bester alternativer Weg
4. Alle Systemänderungen dokumentiert
