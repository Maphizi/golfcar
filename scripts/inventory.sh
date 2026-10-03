#!/usr/bin/env bash
# KITT Golfcart – Phase 1 Inventur
# Nur lesend. Installiert nichts, ändert nichts.
# Aufruf auf dem Pi:  bash ~/golfcar/scripts/inventory.sh | tee /tmp/inventory.txt

section() { printf '\n== %s ==\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

section "Modell / Board"
cat /proc/device-tree/model 2>/dev/null; echo
cat /proc/cpuinfo | grep -E "Revision|Serial|model name|Hardware" | sort -u
nproc; echo "Cores: $(nproc)"

section "RAM / Swap"
free -h

section "OS / Kernel / Architektur"
cat /etc/os-release | grep -E "^(PRETTY_NAME|VERSION_ID|VERSION_CODENAME)="
uname -srm
getconf LONG_BIT; echo "Userland: $(getconf LONG_BIT)-bit"
dpkg --print-architecture 2>/dev/null
[ -f /boot/firmware/config.txt ] && { echo "--- /boot/firmware/config.txt (relevante Zeilen) ---"; grep -vE '^\s*(#|$)' /boot/firmware/config.txt; }

section "Session / Display-Server"
echo "XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-<leer>}"
echo "WAYLAND_DISPLAY=${WAYLAND_DISPLAY:-<leer>}  DISPLAY=${DISPLAY:-<leer>}"
loginctl list-sessions --no-legend 2>/dev/null | while read -r id uid user seat tty rest; do
  echo "Session $id user=$user seat=$seat tty=$tty type=$(loginctl show-session "$id" -p Type --value 2>/dev/null)"
done
systemctl get-default 2>/dev/null
pgrep -a -f 'labwc|wayfire|Xorg|Xwayland|lightdm|gdm|sddm|lxsession|wf-panel|pcmanfm' 2>/dev/null | cut -c1-120
cat /etc/lightdm/lightdm.conf 2>/dev/null | grep -E "autologin|session" | grep -v '^#'

section "GPU / DRM / OpenGL"
ls -l /dev/dri/ 2>/dev/null
for c in /sys/class/drm/card*-*; do
  [ -e "$c/status" ] && echo "$(basename "$c"): $(cat "$c/status") $(cat "$c/enabled" 2>/dev/null)"
done
have glxinfo && glxinfo -B 2>/dev/null | grep -E "OpenGL (renderer|version|ES profile version)|Device|Accelerated" || echo "glxinfo nicht installiert (mesa-utils)"
have eglinfo && eglinfo 2>/dev/null | grep -E "EGL version|OpenGL ES profile version" | sort -u | head -5 || echo "eglinfo nicht installiert"
have vulkaninfo && vulkaninfo --summary 2>/dev/null | grep -E "deviceName|apiVersion" | head -3

section "Display / Auflösung / Refresh"
have wlr-randr && wlr-randr 2>/dev/null
have xrandr && [ -n "$DISPLAY" ] && xrandr --current 2>/dev/null | grep -E " connected|\*"
have kmsprint && kmsprint 2>/dev/null | grep -E "Connector|Crtc|mode" | head -20
for m in /sys/class/drm/card*-*/modes; do echo "$m: $(head -1 "$m" 2>/dev/null)"; done
have tvservice && tvservice -s 2>/dev/null
have vcgencmd && vcgencmd get_config hdmi_group 2>/dev/null

section "Speicher / Datenträger"
df -h / /boot/firmware 2>/dev/null
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,MODEL 2>/dev/null
cat /sys/block/mmcblk0/device/name 2>/dev/null && echo "(SD-Karte erkannt)"
ls /dev/nvme* 2>/dev/null && echo "(NVMe erkannt)"

section "Audio: Backend"
pgrep -a pipewire 2>/dev/null; pgrep -a wireplumber 2>/dev/null; pgrep -a pulseaudio 2>/dev/null
have pactl && pactl info 2>/dev/null | grep -E "Server Name|Default Sink|Default Source|Sample Spec"
systemctl --user is-active pipewire pipewire-pulse wireplumber 2>/dev/null | paste -sd' ' | sed 's/^/pipewire pipewire-pulse wireplumber: /'

section "Audio: ALSA-Geräte"
have aplay && { echo "--- Ausgabe ---"; aplay -l 2>&1; }
have arecord && { echo "--- Aufnahme ---"; arecord -l 2>&1; }
cat /proc/asound/cards 2>/dev/null

section "Audio: PipeWire-Knoten"
have wpctl && wpctl status 2>/dev/null | sed -n '/Audio/,/Video/p' | head -60
have pw-cli && pw-cli info 0 2>/dev/null | grep -E "default.clock.rate|default.clock.quantum"

section "USB-Geräte (Mikrofon, Controller, Buttonbox)"
have lsusb && lsusb
ls -l /dev/input/by-id/ 2>/dev/null

section "Temperatur / Takt / Throttling"
have vcgencmd && { vcgencmd measure_temp; vcgencmd measure_clock arm; vcgencmd get_throttled; vcgencmd measure_volts core; }
cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null | awk '{printf "thermal_zone0: %.1f°C\n", $1/1000}'

section "Python"
python3 --version
python3 -c "import sys; print(sys.executable)"
for m in numpy sounddevice pyaudio pygame moderngl glfw OpenGL evdev pynput; do
  python3 -c "import $m; print('$m', getattr($m,'__version__','ok'))" 2>/dev/null || echo "$m: nicht installiert"
done
have pip3 && pip3 --version
ls -d /usr/lib/python3*/EXTERNALLY-MANAGED 2>/dev/null && echo "(PEP 668: venv nötig)"

section "Relevante Pakete (installiert?)"
for p in retropie-setup emulationstation retroarch libsdl2-2.0-0 libsdl2-dev libgles2 libgl1-mesa-dri libegl1 mesa-utils \
         pipewire pipewire-alsa pipewire-pulse wireplumber pulseaudio alsa-utils portaudio19-dev libportaudio2 \
         python3-venv python3-pip python3-numpy python3-evdev python3-pygame python3-opengl \
         cmake build-essential git ffmpeg sox espeak-ng unclutter wlr-randr wtype xdotool; do
  s=$(dpkg-query -W -f='${Status} ${Version}' "$p" 2>/dev/null)
  case "$s" in *"install ok installed"*) echo "  [x] $p ${s##* }";; *) echo "  [ ] $p";; esac
done

section "Vorhandene Tools / Binaries"
for b in cmake gcc g++ make git ffmpeg sox whisper-cli whisper llama-cli llama-server piper espeak-ng emulationstation retroarch unclutter; do
  have "$b" && echo "  [x] $b -> $(command -v $b)" || echo "  [ ] $b"
done
ls -d ~/RetroPie ~/RetroPie-Setup /opt/retropie 2>/dev/null

section "Netzwerk / Tailscale"
hostname; hostname -I 2>/dev/null
have tailscale && tailscale status 2>/dev/null | head -5

section "Uptime / Last"
uptime

section "Benutzer / Gruppen"
id
echo "Autologin-User laut raspi-config: $(grep -rhoE 'autologin-user=.*' /etc/lightdm/lightdm.conf /etc/systemd/system/getty@tty1.service.d/*.conf 2>/dev/null | head -1)"

echo; echo "== Inventur abgeschlossen =="
