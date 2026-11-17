# KITT-Cart neu aufsetzen

Stand 17.11.2026. Ziel: Pi 5 plattmachen und in einem Durchlauf wieder zum Cart machen. Dauer ohne RetroPie und
Sprachassistent etwa 20 Minuten, mit allem rund zwei Stunden (das meiste davon wartet der Pi allein).

## 1. SD-Karte / SSD schreiben (am PC, Raspberry Pi Imager)

- Gerät: Raspberry Pi 5. Betriebssystem: **Raspberry Pi OS (64-bit)** mit Desktop, Basis Debian 13 "Trixie".
- Im Imager unter "Einstellungen bearbeiten":
  - Hostname `Maphizi`, Benutzer `maphizi` mit Passwort (der Benutzername steckt in Pfaden der Sitzung, bitte so lassen).
  - WLAN: `Vodafone-B814` mit Passwort, Land `DE`.
  - Zeitzone `Europe/Berlin`, Tastatur `de`.
  - Dienste: SSH an (Passwort oder Schlüssel).
- Karte einstecken, Pi starten, Ersteinrichtung abwarten. Danach am Pi oder per SSH weiter.

## 2. Repo holen

```
cd ~ && git clone <URL des Repos> golfcar && cd golfcar && git checkout <Branch>
```

Für ein privates Repo wie bisher: SSH-Schlüssel des Pi bei GitHub hinterlegen (`ssh-keygen`, dann den Inhalt von
`~/.ssh/id_ed25519.pub` als Deploy-Key eintragen) oder HTTPS mit Token.

## 3. Installation in einem Durchlauf

```
scripts/install.sh --all
```

Ohne RetroPie und Sprachassistent reicht `scripts/install.sh`. Das Skript ist idempotent: bricht etwas ab (Netz,
Stromausfall), einfach erneut starten, Fertiges wird übersprungen. Protokoll in `logs/install.log`.
Was es tut: System aktualisieren, Launcher-Pakete und Python-Umgebung, `/dev/uinput` für das D-Pad, Bluetooth-Audio
(SBC hohe Qualität, Profilsperre), Spotify Connect und AirPlay, Piper-Stimmen und Ansagen, optional whisper/llama
und RetroPie, optional Tailscale, Klänge und Bild-Cache, Autostart der Cart-Sitzung (lightdm meldet `maphizi` in der
Sitzung "KITT-Cart" an, die Pi-Leiste läuft oben mit).

## 4. Nach dem Neustart von Hand

1. `sudo reboot`. Der Cart startet mit dem Startbildschirm.
2. **Soundboks koppeln.** Box in den Kopplungsmodus, dann am Pi:
   ```
   bluetoothctl
   scan on            # warten bis "SOUNDBOKS ..." mit MAC erscheint
   pair XX:XX:XX:XX:XX:XX
   trust XX:XX:XX:XX:XX:XX
   connect XX:XX:XX:XX:XX:XX
   quit
   ```
   Prüfen: `scripts/hal_audio_check.sh` (Sink = SOUNDBOKS, Profil A2DP).
3. **LED-Controller:** Adresse in `config/wled.toml` `[controller]`, Test `scripts/wledctl.py set --col 255,0,0`,
   LED-Anzahl `scripts/wled_setup.py --leds 784 --apply`.
4. **Handy:** Spotify-App, Gerät "KITT-Cart" (Premium). iPhone: AirPlay "KITT-Cart".
5. **Tailscale** (falls installiert): `sudo tailscale up`, Link am Handy bestätigen. **Pi Connect:** `rpi-connect signin`.
6. **Buttonboard:** `scripts/input_monitor.py 10` zeigt die Codes; Belegung steht in `config/keymap.toml` und
   `config/settings.toml` `[buttons]`, beides kommt aus dem Repo mit.

## 5. Regeln, damit es so bleibt

- **Kein 2,4-GHz-Hotspot neben dem Cart**, solange Musik über Bluetooth läuft. Das Handy-Hotspot-Profil
  "S24 FE von Marc-Philip" nicht anlegen; wenn doch: `nmcli connection modify "<Name>" connection.autoconnect no`.
- **Der Discord-Bot führt nur Befehle aus.** Keine Pakete, keine Dateien unter /etc oder ~/.config, keine Autostarts
  ohne Freigabe. Nie `gnome-network-displays`, `miraclecast` oder andere Miracast-Sender.
- Updates nur über `scripts/update.sh`. Diagnose bei Bluetooth-Problemen: `scripts/bt_diag.sh` (pusht nach `origin/diag`).
