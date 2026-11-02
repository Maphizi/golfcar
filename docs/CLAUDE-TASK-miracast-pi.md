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

---

## Stand (Claude Code, umgesetzt im Repo, auf dem Pi noch auszuführen)

Ohne SSH-Zugang zum Pi (Tailscale-IP und Schlüssel liegen nur auf Marcs Rechner) ist alles als Skript im Repo gebaut,
wie die anderen Setup-Skripte. Auf dem Pi nach `git pull`:

```
scripts/setup_miracast.sh             # 1. prüfen, ändert nichts, sucht 530E1F_P2P -> Ausgabe an Claude geben
scripts/setup_miracast.sh --install   # 2. wf-recorder + ffmpeg, Dienst kitt-miracast (aus)
scripts/setup_miracast.sh --test 60   # 3. ein Versuch, 60 s senden, mit Sicherheitsnetz
scripts/setup_miracast.sh --enable    # 4. Autostart
```

**1. Was installiert/konfiguriert wird**
- `scripts/miracast.py`: Miracast-Sender. Wi-Fi Direct über NetworkManager (`p2p-dev-wlan0`, Profil `kitt-miracast`),
  RTSP-Steuerung WFD M1-M7 + Keepalive (Port 7236), Bild per `wf-recorder` aus der labwc-Session (Launcher, Visualizer,
  RetroArch unter Xwayland mit Shadern), `libx264` 720p30 ~4 Mbit/s, MPEG-TS über RTP (PIDs 0x1011/0x1100), stille
  AAC-Tonspur. Einstellungen `config/settings.toml` `[miracast]`.
- `systemd/kitt-miracast.service` -> `/etc/systemd/system/` (root, sucht den Empfänger, verbindet, bei Abbruch neu
  nach 20 s). Pakete: `wf-recorder`, `ffmpeg`. Sonst keine Systemänderungen: wlan0, seine Verbindungen und
  NetworkManager-Einstellungen bleiben unangetastet.

**Bewusst nicht miraclecast:** `miracle-wifid` übernimmt die WLAN-Karte exklusiv (eigener wpa_supplicant,
NetworkManager muss loslassen) -> Vodafone und Tailscale wären weg. Sein Sender-Teil (`miracle-wfdctl`) ist experimentell,
`miracle-sinkctl` ist der Empfänger, nicht der Sender. NetworkManager kann Wi-Fi Direct selbst, parallel zum WLAN.

**WLAN-Schutz:** fällt wlan0 nach dem Aufbau von Wi-Fi Direct aus (Chip schafft zwei Kanäle nicht), baut der Sender
sofort ab, verbindet wlan0 neu, schreibt das nach `logs/miracast_status.txt` und startet nicht wieder (Exit 3). Beim
Test zusätzlich ein Timer, der nach 5 min alles zurücksetzt.

**2. Verbindung zu 530E1F_P2P:** noch nicht ausprobiert (kein Zugriff auf den Pi). Lokal geprüft: der RTSP-Ablauf
gegen einen nachgebauten Empfänger (Formatwahl, SETUP, PLAY, Keepalive, TEARDOWN) und der RTP-Strom (MPEG-TS,
Payload 33, richtige PIDs).

**3. Falls es nicht klappt:** zweiter USB-WLAN-Stick nur für Miracast (`[miracast] wifi = "wlan1"`), dann teilt sich
nichts den Kanal. Alternative ohne Funk: HDMI-Splitter/HDMI-Funkstrecke (keine Software, kaum Verzögerung).

**Hinweise:** Miracast hat 50-150 ms Verzögerung (bei Retro-Spielen spürbar). Der Pi 5 hat keinen Hardware-H.264-Encoder,
libx264 braucht bei 720p30 etwa einen Kern (Dienst läuft mit Nice 5). Der Dongle kann auch AirPlay, aber für Linux gibt es
keinen brauchbaren AirPlay-Bildsender, daher Miracast.

### Testläufe auf dem Pi (2026-11-02)

1. Erster Test: Dongle gefunden (`530E1F_P2P`, CE:C4:B2:53:0E:1F, Signal 100, Miracast-Empfänger), aber
   `nmcli connection up` lief nach 45 s in den Timeout, am Dongle tat sich nichts. Ursache: in den WFD-IEs des Senders war
   Bit 7 der Geräteinfo gesetzt (= TDLS bevorzugt), der Dongle reagierte nicht. Korrigiert auf 0x0010.
2. Zweiter Test: `P2P-GO-NEG-SUCCESS role=GO freq=5785`, dann `Failed to set beacon parameters` /
   `p2p-wlan0-1: Could not connect to kernel driver` / `P2P-GROUP-FORMATION-FAILURE`. Der Pi wurde Gruppenleiter (GO),
   brcmfmac kann neben wlan0 (Vodafone, 5540 MHz) aber keinen eigenen Hotspot aufmachen. Chip-Kombinationen:
   `managed<=2, P2P-device<=1, P2P-client/GO<=1, channels<=2` und `managed<=1, AP<=1, P2P-client<=1, channels<=1`.
   WLAN und Tailscale blieben in beiden Tests verbunden.
   Korrektur: vor dem Verbinden setzt `miracast.py` den GO-Wunsch von wpa_supplicant (D-Bus `P2PDeviceConfig.GOIntent`)
   auf 0, damit der Dongle Gruppenleiter wird und der Pi nur Teilnehmer ist; danach wieder der alte Wert.
   Falls es trotzdem nicht geht: WLAN des Carts auf 2,4 GHz oder zweiter USB-WLAN-Stick nur für Miracast.
3. Dritter/vierter Test (GO-Wunsch 0 bzw. 15 über D-Bus `P2PDeviceConfig`): keine Verhandlung mehr. Zwei Ursachen:
   mein Skript ließ die eigene Suche weiterlaufen (NetworkManagers Suche beim Verbinden scheiterte: "another p2p_scan
   was already running"), und NetworkManager übergibt beim Verbinden ohnehin fest GO-Wunsch 7 (deshalb 0 und 15 gleich).
   Das Testprotokoll zeigte außerdem nur die letzte Sekunde (zu breiter Filter + Zeilenlimit).
   Umbau: `[miracast] connect = "wpas"` (Standard) verbindet direkt über wpa_supplicant (D-Bus `Connect` mit `go_intent`
   0 → der Dongle leitet, der Pi ist Teilnehmer; bei Status 9 "beide wollen nicht leiten" zweiter Versuch als Leiter auf
   `go_channel` 6), liest die Signale mit (`busctl monitor`: GONegotiation*, GroupStarted, WpsFailed), setzt die
   Gruppenschnittstelle in NetworkManager auf unmanaged (Drop-in `/etc/NetworkManager/conf.d/90-kitt-miracast.conf`,
   `unmanaged-devices=interface-name:p2p-wlan0-*`, wird mit `--undo` entfernt) und vergibt die IP selbst (Teilnehmer:
   kleiner DHCP-Client; Leiter: 192.168.49.1 + kleiner DHCP-Server). `connect = "nm"` = alter Weg. Der Test speichert das
   vollständige Journal in `logs/miracast_journal.txt` und zeigt eine Kurzfassung ohne Lauschzeilen plus `dmesg brcmfmac`.
4. Fünfter Test (direkt über wpa_supplicant): Verhandlung in 6 s erfolgreich, aber der Pi wurde trotz GO-Wunsch 0
   Leiter (der Dongle meldet ebenfalls 0, dann entscheidet der Münzwurf), und dmesg zeigt den echten Fehler:
   `brcmf_cfg80211_start_ap: Set Channel failed: chspec=53405, -52` = Kanal 157 (5785 MHz) wird vom Treiber abgelehnt.
   Korrektur: Betriebskanal für den Fall "Pi leitet" auf `go_channel` 6 (2,4 GHz, P2PDeviceConfig OperChannel, danach
   zurückgesetzt), bis zu 3 Anläufe je Verbindung (nach einem Fehlschlag mit GO-Wunsch 0, damit möglichst der Dongle
   leitet). Statuscode 9 richtiggestellt (= beide wollen leiten).
5. Sechster und siebter Test (Betriebskanal 6, bis zu 3 Anläufe, davor Dongle stromlos): beide Male
   `keine Antwort des Empfängers in 45 s (Rolle 'device')` – es kam überhaupt kein P2P-Signal mehr vom Dongle
   (keine Verhandlung, kein WPS, kein Fehler in dmesg). Der Dongle wurde zuverlässig gefunden, das WLAN blieb während
   des Verbindens oben. Nach dem siebten Test war der Pi für den Bot kurz nicht erreichbar und wurde neu gestartet;
   wahrscheinliche Ursache: das Kommando des Bots lief vor dem Ende der 3 x 45 s in sein Zeitlimit, das Sicherheitsnetz
   (`kitt-miracast-guard`, 5 min) machte danach `nmcli device connect wlan0` auf das VERBUNDENE WLAN, und das trennt
   es kurz (Tailscale weg). Korrigiert: das Sicherheitsnetz beendet nur noch das Skript und verbindet wlan0 ausschließlich,
   wenn es wirklich getrennt ist; 2 Anläufe à 30 s, damit der ganze Test ins Zeitfenster des Bots passt.

### Stand und Empfehlung (2026-11-02, nach 7 Tests)

Was funktioniert: Erkennung des Dongles, WLAN-Wächter (Vodafone/Tailscale blieben bei jedem Verbindungsversuch
oben), die komplette RTSP/RTP-Strecke gegen einen nachgebauten Empfänger. Was nicht funktioniert: eine stabile Wi-Fi-
Direct-Gruppe über den eingebauten Chip des Pi 5, während er auf 5540 MHz (DFS) im Heim-WLAN hängt. Einmal (Test 5) kam
die Verhandlung durch, scheiterte dann am Treiber (Pi als Leiter auf 5785 MHz nicht erlaubt); seit der Umstellung auf
Kanal 6 antwortet der Dongle gar nicht mehr. Weitere Anläufe am eingebauten Chip lohnen nicht.

Empfehlung, eine von beiden:
- **USB-WLAN-Stick nur für Miracast** (Chip MediaTek MT7921U oder MT7612U, kein Realtek – die laufen unter Linux
  ohne Fremdtreiber mit P2P): einstecken, `[miracast] wifi = "wlan1"` in `config/settings.toml`,
  `scripts/setup_miracast.sh --install` (legt den NetworkManager-Drop-in für `p2p-wlan1-*` an), dann
  `scripts/setup_miracast.sh --test 60`. Der gesamte Code bleibt, nur der Funk ist getrennt: eigener Kanal, Leiterrolle
  erlaubt, kein DFS. Ab dann ist auch der Bildstrom auf echter Hardware prüfbar.
- **HDMI-Funkstrecke** (Sender am HDMI-Ausgang des Pi, Empfänger am Bildschirm): keine Software, kein WLAN, die
  geringste Verzögerung (wichtig bei Retro-Spielen). Dann `scripts/setup_miracast.sh --undo` und das Thema ist
  abgeschlossen.

### Nachspiel: Bluetooth-Musik stottert (2026-11-02, abends)

Nach den Miracast-Tests und dem Neustart stotterte die Musik an die Soundboks (A2DP), brach nach etwa einer Minute ab
und lief nach dem Neuverbinden in schlechter Qualität. Ergebnis der Suche:
- Kein Firmware-, Kernel- oder PipeWire-Update (Fehlmeldung des Bots), WLAN auf 5 GHz, keine Unterspannung, CPU frei.
- Der Bot hatte neben `wf-recorder ffmpeg` eigenmächtig `gnome-network-displays` (eigener Miracast-Sender, sucht über
  NetworkManager dauernd per Wi-Fi Direct auf 2,4 GHz), `xdg-desktop-portal(-wlr)` und ~100 Entwicklungspakete
  (gstreamer-dev, opencv, gdal, VTK) installiert. Wi-Fi-Direct-Suche und Bluetooth teilen sich Chip, Antenne und Band;
  eine dauernd laufende Suche stört A2DP massiv.
- Maßnahmen: `gnome-network-displays`, Portale und Abhängigkeiten entfernen (`apt purge` + `autoremove`), WLAN-Stromsparen
  über NetworkManager dauerhaft aus (`wifi.powersave = 2`), Neustart. Falls es weiter stottert: Miracast-Dongle komplett
  stromlos testen (eigener 2,4-GHz-Sender direkt neben dem Pi).
- Regel für den Bot: keine Paketinstallationen außer den im Auftrag genannten (`wf-recorder`, `ffmpeg`), keine
  Änderungen ohne Freigabe.
