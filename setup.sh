#!/bin/bash
# ══════════════════════════════════════════════════════════════
#  FIT SPIN — Raspberry Pi Kiosk Setup
#  Run as pi user with sudo access:  sudo bash setup.sh
#  Supports: Pi OS Bullseye and Bookworm (32-bit & 64-bit)
#  Bookworm differences handled automatically:
#    - labwc autostart instead of lxsession
#    - NetworkManager instead of dhcpcd for static IP
#    - wlan0-static.service assigns IP after hostapd
#    - dnsmasq starts after wlan0-static
# ══════════════════════════════════════════════════════════════
set -e

SSID="FITSPIN-ADMIN"
PASSWORD="FitSpin2026"
AP_IP="10.0.0.1"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
PI_USER="${SUDO_USER:-pi}"
PI_HOME="/home/${PI_USER}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()    { echo -e "${YELLOW}[!]${NC} $*"; }
section() { echo -e "\n${YELLOW}══ $* ══${NC}"; }

# ── Detect OS version ─────────────────────────────────────────
if grep -q "bookworm" /etc/os-release 2>/dev/null; then
  OS_VER="bookworm"
  info "Detected: Raspberry Pi OS Bookworm"
else
  OS_VER="bullseye"
  info "Detected: Raspberry Pi OS Bullseye"
fi

section "Install packages"
apt-get update -qq
apt-get install -y hostapd dnsmasq python3-pip unclutter xdotool
info "Packages installed"

section "Install Flask"
pip3 install flask --break-system-packages 2>/dev/null \
  || pip3 install flask \
  || apt-get install -y python3-flask
info "Flask installed"

section "Configure hostapd (WiFi access point)"

# If wifi.json already exists, read saved credentials from it
# This prevents re-running setup from overwriting a password changed via the admin portal
WIFI_JSON="${APP_DIR}/data/wifi.json"
if [ -f "$WIFI_JSON" ]; then
  warn "wifi.json already exists — loading saved credentials (not overwriting)"
  SSID=$(python3 -c "import json; d=json.load(open('$WIFI_JSON')); print(d['ssid'])")
  PASSWORD=$(python3 -c "import json; d=json.load(open('$WIFI_JSON')); print(d['password'])")
  info "Loaded SSID: ${SSID}"
else
  info "No wifi.json found — using default credentials"
fi

tee /etc/hostapd/hostapd.conf > /dev/null << EOF
interface=wlan0
driver=nl80211
ssid=${SSID}
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=${PASSWORD}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

if ! grep -q 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' /etc/default/hostapd 2>/dev/null; then
  echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' >> /etc/default/hostapd
fi

systemctl unmask hostapd 2>/dev/null || true
systemctl enable hostapd
info "hostapd configured (SSID: ${SSID})"

section "Configure static IP for wlan0"

if [ "$OS_VER" = "bookworm" ]; then
  # Bookworm uses NetworkManager — tell it to leave wlan0 alone
  mkdir -p /etc/NetworkManager/conf.d
  tee /etc/NetworkManager/conf.d/unmanaged.conf > /dev/null << EOF
[keyfile]
unmanaged-devices=interface-name:wlan0
EOF
  systemctl restart NetworkManager
  info "NetworkManager configured to ignore wlan0"

  # Load rfkill module at boot
  echo 'rfkill' > /etc/modules-load.d/rfkill.conf
  info "rfkill module set to load at boot"

  # Unblock WiFi radio before NetworkManager or hostapd can touch it
  # Uses sysfs directly — works even before /dev/rfkill is available
  tee /etc/systemd/system/rfkill-unblock.service > /dev/null << EOF
[Unit]
Description=Unblock WiFi radio
Before=NetworkManager.service hostapd.service wlan0-static.service
DefaultDependencies=no
After=sysinit.target

[Service]
Type=oneshot
ExecStart=/bin/sh -c 'for f in /sys/class/rfkill/*/type; do [ "\$(cat \$f)" = "wlan" ] && echo 0 > "\${f%type}soft"; done'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable rfkill-unblock
  info "rfkill-unblock.service created"

  # Systemd service assigns the static IP after hostapd brings wlan0 up
  tee /etc/systemd/system/wlan0-static.service > /dev/null << EOF
[Unit]
Description=Static IP for wlan0 (FIT SPIN AP)
After=hostapd.service rfkill-unblock.service
Wants=hostapd.service rfkill-unblock.service

[Service]
Type=oneshot
ExecStartPre=/bin/sleep 5
ExecStart=/sbin/ip addr flush dev wlan0
ExecStart=/sbin/ip addr add ${AP_IP}/24 dev wlan0
ExecStart=/sbin/ip link set wlan0 up
RemainAfterExit=yes
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable wlan0-static
  info "wlan0-static.service created (assigns ${AP_IP})"

else
  # Bullseye uses dhcpcd
  DHCPCD=/etc/dhcpcd.conf
  if ! grep -q "# FITSPIN" "$DHCPCD" 2>/dev/null; then
    tee -a "$DHCPCD" > /dev/null << EOF

# FITSPIN — static AP address
interface wlan0
    static ip_address=${AP_IP}/24
    nohook wpa_supplicant
EOF
  fi
  info "dhcpcd static IP configured: ${AP_IP}"
fi

section "Configure dnsmasq (DHCP + DNS)"

[ -f /etc/dnsmasq.conf ] && [ ! -f /etc/dnsmasq.conf.bak ] \
  && mv /etc/dnsmasq.conf /etc/dnsmasq.conf.bak

tee /etc/dnsmasq.conf > /dev/null << EOF
interface=wlan0
bind-interfaces
dhcp-range=10.0.0.10,10.0.0.50,255.255.255.0,24h
address=/#/${AP_IP}
EOF

if [ "$OS_VER" = "bookworm" ]; then
  # dnsmasq must wait for wlan0-static to assign the IP before starting
  mkdir -p /etc/systemd/system/dnsmasq.service.d
  tee /etc/systemd/system/dnsmasq.service.d/override.conf > /dev/null << EOF
[Unit]
After=wlan0-static.service
Wants=wlan0-static.service
EOF
  systemctl daemon-reload
  info "dnsmasq override: starts after wlan0-static"
fi

systemctl enable dnsmasq
info "dnsmasq configured (DHCP: 10.0.0.10-50)"

section "Create Flask systemd service"

tee /etc/systemd/system/fitslot.service > /dev/null << EOF
[Unit]
Description=FIT SPIN Kiosk Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${APP_DIR}
ExecStart=/usr/bin/python3 ${APP_DIR}/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable fitslot
info "fitslot.service installed and enabled"

section "Configure kiosk autostart"

if [ "$OS_VER" = "bookworm" ]; then
  # Bookworm uses labwc (Wayland) — different autostart format and location
  AUTOSTART_DIR="${PI_HOME}/.config/labwc"
  mkdir -p "$AUTOSTART_DIR"
  tee "$AUTOSTART_DIR/autostart" > /dev/null << EOF
xset s off &
xset -dpms &
xset s noblank &
unclutter -idle 0.1 -root &
chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --disable-features=TranslateUI http://localhost/ &
EOF
  info "labwc autostart configured (Bookworm)"

else
  # Bullseye uses lxsession
  AUTOSTART_DIR="${PI_HOME}/.config/lxsession/LXDE-pi"
  mkdir -p "$AUTOSTART_DIR"
  tee "$AUTOSTART_DIR/autostart" > /dev/null << EOF
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 0.1 -root
@chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state --disable-features=TranslateUI http://localhost/
EOF
  info "lxsession autostart configured (Bullseye)"
fi

# Ensure pi user owns their config files even when script runs as root
chown -R "${PI_USER}:${PI_USER}" "${PI_HOME}/.config"

section "Dismiss SSH security warning"
rm -f /etc/xdg/autostart/piwiz.desktop
info "piwiz.desktop removed"

section "Save WiFi config for admin portal"
mkdir -p "${APP_DIR}/data"
# Only write wifi.json if it doesn't already exist
if [ ! -f "${APP_DIR}/data/wifi.json" ]; then
  tee "${APP_DIR}/data/wifi.json" > /dev/null << EOF
{
  "ssid": "${SSID}",
  "password": "${PASSWORD}",
  "ip": "${AP_IP}"
}
EOF
  info "wifi.json created with default credentials"
else
  info "wifi.json already exists — not overwriting"
fi

section "Summary"
echo ""
echo -e "  ${GREEN}OS detected:${NC}    ${OS_VER}"
echo -e "  ${GREEN}Pi user:${NC}        ${PI_USER}"
echo -e "  ${GREEN}App directory:${NC}  ${APP_DIR}"
echo -e "  ${GREEN}WiFi SSID:${NC}      ${SSID}"
echo -e "  ${GREEN}WiFi password:${NC}  ${PASSWORD}"
echo -e "  ${GREEN}Admin portal:${NC}   http://${AP_IP}/admin"
echo ""
warn "IMPORTANT: Set your WiFi country code before rebooting or the radio will be blocked:"
echo -e "  ${YELLOW}sudo raspi-config${NC}  →  Localisation Options → WLAN Country"
echo ""
warn "Then reboot to start everything:"
echo -e "  ${YELLOW}sudo reboot${NC}"
echo ""
echo -e "  After reboot connect to WiFi '${SSID}'"
echo -e "  then open ${GREEN}http://${AP_IP}/admin${NC} to manage exercises."
echo ""
