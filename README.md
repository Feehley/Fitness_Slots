# 🎰 FIT SPIN — Fitness Slot Machine Kiosk

A touchscreen workout randomizer built for **Raspberry Pi**. Spin 5 independent reels — each representing a different exercise category — and let the machine decide your workout. Fully offline, boots directly to kiosk mode, and managed through a built-in WiFi admin portal.

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Hardware Requirements](#hardware-requirements)
- [Recommended Pi Image](#recommended-pi-image)
- [File Structure](#file-structure)
- [Quick Start](#quick-start)
- [Setup Script (What It Does)](#setup-script-what-it-does)
- [Admin Portal](#admin-portal)
- [CSV Format](#csv-format)
- [Using Images in Exercises](#using-images-in-exercises)
- [Default Exercise Columns](#default-exercise-columns)
- [WiFi Access Point](#wifi-access-point)
- [Kiosk Controls](#kiosk-controls)
- [Manual Setup (Without the Script)](#manual-setup-without-the-script)
- [Customization](#customization)
- [Troubleshooting](#troubleshooting)
- [Architecture](#architecture)

---

## Overview

FIT SPIN runs as a self-contained kiosk on a Raspberry Pi with a touchscreen. When powered on, it boots straight into a full-screen slot machine interface. Customers press one button — SPIN — and get a random exercise from each of 5 configurable columns (e.g. Warm Up, Upper Body, Lower Body, Core, Cardio).

The Pi broadcasts its own WiFi network. Staff connect to that network from any phone or laptop and open a browser to access the admin portal, where they can update exercises, rename columns, and upload new CSVs — all without touching the Pi or rebooting.

```
Customer experience:
  Power on → Kiosk loads → Press SPIN → See workout

Staff experience:
  Connect to "FITSPIN-ADMIN" WiFi → Open http://10.0.0.1/admin → Edit exercises
```

---

## Features

- **5 independent spinning reels** — one per exercise category
- **Fully offline** — no internet connection required at any point
- **Boots to kiosk** — Chromium launches full-screen on startup
- **Built-in WiFi AP** — Pi hosts its own network for admin access
- **Admin portal** — manage all 5 columns from any device's browser
- **Per-column CSV upload/download** — bulk load exercises instantly
- **Inline exercise editing** — add or delete exercises one at a time
- **Emoji or image support** — use emoji characters or hosted image URLs
- **Jackpot detection** — special animation when all 5 reels match
- **Persistent storage** — exercise data survives reboots (saved to disk)
- **Responsive layout** — adapts to 480p, 600p, 720p, and 1080p screens
- **Touch-optimized** — large spin button, no hover-only interactions

---

## Hardware Requirements

| Component | Recommendation |
|-----------|----------------|
| Pi model | Raspberry Pi 3B+, 4B (2GB+), or Zero 2 W |
| Storage | 8GB+ microSD (Class 10 or better) |
| Touchscreen | Any DSI or HDMI touchscreen (7"+ recommended) |
| Power | Official Pi power supply for your model |
| Case | Optional — anything with touchscreen cutout |

> **Pi Zero 2 W** works but expect slightly slower boot times. Pi 4 is the smoothest experience.

---

## Recommended Pi Image

**Raspberry Pi OS (Legacy, 32-bit) — Bullseye — Desktop** is the safest choice, but **Bookworm is also fully supported** — `setup.sh` detects the OS version automatically and applies the correct configuration for each.

| | Bullseye | Bookworm |
|---|---|---|
| Status | ✅ Recommended | ✅ Supported |
| Networking | `dhcpcd` | `NetworkManager` + `wlan0-static.service` |
| Compositor | `lxsession` | `labwc` (Wayland) |
| Autostart location | `~/.config/lxsession/LXDE-pi/autostart` | `~/.config/labwc/autostart` |

**Regardless of version:**
- **Not Lite** — needs a desktop environment for Chromium kiosk mode
- **Not Full** — the extra apps (LibreOffice, games) waste space
- **Not 64-bit** — unnecessary for this use case; 32-bit has better touchscreen driver compatibility

### Where to download

https://www.raspberrypi.com/software/operating-systems/

- **Bullseye:** Scroll to **"Raspberry Pi OS (Legacy)"** → **Desktop** row → **32-bit**
- **Bookworm:** Scroll to **"Raspberry Pi OS"** → **Desktop** row → **32-bit**

### Flashing with Raspberry Pi Imager

Use the ⚙️ settings (gear icon) before writing:

| Setting | Value |
|---------|-------|
| Hostname | `fitspin` |
| Enable SSH | Yes (allows deploying files remotely) |
| Username | `pi` |
| Password | Your choice |
| Configure WiFi | **Leave blank** — `wlan0` must be free for the AP |

---

## File Structure

```
fitslot/
├── server.py           — Flask web server (API + file serving)
├── setup.sh            — One-shot Pi configuration script
├── exercises.csv       — Example CSV for reference
├── static/
│   ├── index.html      — Kiosk slot machine (served at /)
│   └── admin.html      — Admin portal (served at /admin)
└── data/               — Created automatically on first run
    ├── exercises.json  — Live exercise data (all 5 columns)
    └── wifi.json       — WiFi AP credentials
```

---

## Quick Start

### 1. Flash your SD card

Use Raspberry Pi Imager with the image and settings described above.

### 2. Copy files to the Pi

Via SSH (replace `fitspin.local` with the Pi's IP if mDNS isn't working):

```bash
scp -r fitslot/ pi@fitspin.local:/home/pi/fitslot
```

Or copy to the SD card's home folder directly before first boot.

### 3. Run setup

SSH into the Pi and run:

```bash
cd /home/pi/fitslot
sudo bash setup.sh
```

The script detects whether you're on Bullseye or Bookworm and configures everything accordingly. Takes 2–5 minutes.

### 4. Set WiFi country code

**This step is required** — the Pi blocks the WiFi radio until a country is set for regulatory compliance. Skipping this causes rf-kill errors and no network on boot.

```bash
sudo raspi-config
```

Navigate to: **Localisation Options → WLAN Country → select your country**

Exit raspi-config, then reboot:

```bash
sudo reboot
```

### 4. Verify

After the Pi restarts:

- The touchscreen should show the FIT SPIN kiosk
- A WiFi network named `FITSPIN-ADMIN` should be visible
- Connect to it (password: `FitSpin2024`) and open `http://10.0.0.1/admin`

---

## Setup Script (What It Does)

`setup.sh` detects your OS version and automates every configuration step:

| Step | Bullseye | Bookworm |
|------|----------|----------|
| Package install | `hostapd`, `dnsmasq`, `flask`, `unclutter` | Same |
| Static IP | Appends to `/etc/dhcpcd.conf` | Creates `wlan0-static.service` + tells NetworkManager to ignore `wlan0` |
| Access point | Writes `/etc/hostapd/hostapd.conf` | Same |
| DHCP server | Configures `dnsmasq` | Same + override to start after `wlan0-static` |
| DNS redirect | All connected devices resolve to `10.0.0.1` | Same |
| Flask service | `fitslot.service` via systemd | Same |
| Kiosk autostart | `~/.config/lxsession/LXDE-pi/autostart` | `~/.config/labwc/autostart` |
| Screen saver | `xset s off / -dpms` | Same |
| Cursor hiding | `unclutter` | Same |
| SSH warning | Removes `piwiz.desktop` | Same |

The script is idempotent — safe to re-run if something goes wrong partway through.

---

## Admin Portal

Connect to the Pi's WiFi network, then open **`http://10.0.0.1/admin`** in any browser.

### What you can do

**For each of the 5 columns:**
- Rename the column label (click the title, type, press Enter)
- Upload a new CSV to replace all exercises in that column
- Download the current exercises as a CSV
- Add a single exercise using the inline form (emoji, name, reps)
- Delete individual exercises with the × button

**WiFi settings:**
- Change the network SSID and password
- Changes apply immediately (hostapd restarts) — reconnect with new credentials

**Global:**
- Reset all 5 columns back to factory defaults

### Accessing admin from the kiosk screen

Tap the **FIT SPIN** title **5 times quickly** — this navigates to `/admin` in the same Chromium window. Tap the **← Kiosk** button to return.

---

## CSV Format

Each column accepts its own CSV file. The only required column is the exercise name.

### Headers

| Column header | Required | Description |
|---------------|----------|-------------|
| `name` or `exercise` | ✅ Yes | Exercise name (max 40 chars) |
| `emoji` | Optional | Single emoji character (default: 💪) |
| `reps` | Optional | Reps, sets, or duration (e.g. `15 reps`, `60 sec`) |
| `image` | Optional | URL or local path to an image |

Header names are case-insensitive. Partial matches work — `exercise_name`, `REPS`, `duration` all resolve correctly.

### Example

```csv
name,emoji,reps
Squats,🦵,15 reps
Lunges,🏃,12 each leg
Box Jumps,📦,10 reps
Deadlifts,🏋️,8 reps
Calf Raises,👟,25 reps
Wall Sit,🧘,45 sec
```

### With image URLs

```csv
name,emoji,reps,image
Squats,🦵,15 reps,https://example.com/images/squats.jpg
Push-Ups,💪,20 reps,https://example.com/images/pushups.jpg
```

If an image URL fails to load, the emoji is shown as a fallback automatically.

---

## Using Images in Exercises

Images can be referenced two ways:

### 1. Remote URLs

Works immediately, requires no extra setup. The Pi must be able to reach the URL — this works for local network file servers. Public internet URLs won't work since the Pi has no upstream internet by default.

### 2. Local files

Place images inside the `static/` folder:

```
fitslot/static/images/squats.jpg
fitslot/static/images/pushups.jpg
```

Then reference them in your CSV as:

```
images/squats.jpg
```

The Flask server serves everything under `static/` automatically.

**Recommended image size:** 200×200px or square crops. JPEG or PNG both work.

---

## Default Exercise Columns

The five columns loaded on first run:

| # | Label | Color | Sample exercises |
|---|-------|-------|-----------------|
| 1 | Warm Up | Pink `#ff3cac` | Jumping Jacks, High Knees, Arm Circles… |
| 2 | Upper Body | Orange `#ff6b35` | Push-Ups, Pull-Ups, Shoulder Press… |
| 3 | Lower Body | Teal `#00f5d4` | Squats, Lunges, Box Jumps… |
| 4 | Core | Yellow `#fee440` | Plank, Bicycle Crunches, Mountain Climbers… |
| 5 | Cardio | Purple `#9b5de5` | Burpees, Jump Rope, Battle Ropes… |

Each column has 6 exercises by default. There's no maximum — load as many as you like and the reel will cycle through all of them.

---

## WiFi Access Point

The Pi operates as a standalone WiFi access point. It does **not** forward traffic to the internet — it only serves the admin portal.

| Setting | Default |
|---------|---------|
| SSID | `FITSPIN-ADMIN` |
| Password | `FitSpin2024` |
| Pi IP address | `10.0.0.1` |
| Client IP range | `10.0.0.10 – 10.0.0.50` |
| Channel | 6 (2.4GHz) |
| Admin URL | `http://10.0.0.1/admin` |

Change the SSID and password through the admin portal. The new config is applied to `hostapd` and takes effect within a few seconds.

> **Security note:** Change the default password before deploying in a public venue. The admin portal has no login — anyone connected to the WiFi can access it. Consider this when positioning the Pi.

---

## Kiosk Controls

### For customers (touchscreen)

| Action | Result |
|--------|--------|
| Tap **SPIN** button | Spins all 5 reels |
| Tap jackpot banner | Dismisses jackpot overlay |

### For staff (touchscreen)

| Action | Result |
|--------|--------|
| Tap title 5× quickly | Opens admin portal |

### Physical keyboard (if attached)

| Key | Result |
|-----|--------|
| `Space` or `Enter` | Spin |

---

## Manual Setup (Without the Script)

If you prefer to configure each step yourself:

### 1. Install packages

```bash
sudo apt-get update
sudo apt-get install -y hostapd dnsmasq python3-pip unclutter
pip3 install flask --break-system-packages
```

### 2. Static IP for wlan0

**Bullseye** — add to `/etc/dhcpcd.conf`:
```
interface wlan0
    static ip_address=10.0.0.1/24
    nohook wpa_supplicant
```

**Bookworm** — tell NetworkManager to ignore wlan0, then create a service:

```bash
# /etc/NetworkManager/conf.d/unmanaged.conf
[keyfile]
unmanaged-devices=interface-name:wlan0
```

```ini
# /etc/systemd/system/wlan0-static.service
[Unit]
Description=Static IP for wlan0
After=hostapd.service
Requires=hostapd.service

[Service]
Type=oneshot
ExecStart=/sbin/ip addr flush dev wlan0
ExecStart=/sbin/ip addr add 10.0.0.1/24 dev wlan0
ExecStart=/sbin/ip link set wlan0 up
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable wlan0-static
```

> **Note:** On some Pi hardware the WiFi radio starts soft-blocked. The `rfkill unblock wifi` line in the service handles this automatically. If you ever see `rtnetlink answers: operation not possible due to rf-kill` run `sudo rfkill unblock wifi` manually.

### 3. hostapd config

`/etc/hostapd/hostapd.conf`:

```
interface=wlan0
driver=nl80211
ssid=FITSPIN-ADMIN
hw_mode=g
channel=6
ieee80211n=1
wmm_enabled=1
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=FitSpin2024
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
```

Point to it in `/etc/default/hostapd`:

```
DAEMON_CONF="/etc/hostapd/hostapd.conf"
```

### 4. dnsmasq config

Replace `/etc/dnsmasq.conf`:

```
interface=wlan0
bind-interfaces
dhcp-range=10.0.0.10,10.0.0.50,255.255.255.0,24h
address=/#/10.0.0.1
```

**Bookworm only** — add a drop-in to ensure dnsmasq starts after the IP is assigned:

```ini
# /etc/systemd/system/dnsmasq.service.d/override.conf
[Unit]
After=wlan0-static.service
Wants=wlan0-static.service
```

### 5. systemd service

`/etc/systemd/system/fitslot.service`:

```ini
[Unit]
Description=FIT SPIN Kiosk Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/pi/fitslot
ExecStart=/usr/bin/python3 /home/pi/fitslot/server.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable fitslot
sudo systemctl start fitslot
```

### 6. Kiosk autostart

**Bullseye** — `/home/pi/.config/lxsession/LXDE-pi/autostart`:

```
@lxpanel --profile LXDE-pi
@pcmanfm --desktop --profile LXDE-pi
@xset s off
@xset -dpms
@xset s noblank
@unclutter -idle 0.1 -root
@chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state http://localhost/
```

**Bookworm** — `/home/pi/.config/labwc/autostart` (note the `&` on each line):

```
xset s off &
xset -dpms &
xset s noblank &
unclutter -idle 0.1 -root &
chromium-browser --kiosk --noerrdialogs --disable-infobars --disable-session-crashed-bubble --disable-restore-session-state http://localhost/ &
```

To confirm which compositor your Pi is using:
```bash
echo $DESKTOP_SESSION
# LXDE-pi        → Bullseye, use lxsession path
# LXDE-pi-labwc  → Bookworm, use labwc path
```

---

## Customization

### Change column count

The app is hardcoded for 5 columns. To change this, update:
- `server.py` — `DEFAULTS` list length and the `/api/column/<int:col>` route's range check
- `static/index.html` — `REEL_DELAYS` array length and the DOM build loop
- `static/admin.html` — the `for (let i = 0; i < 5; i++)` CSV input loop

### Change spin timing

In `static/index.html`:

```js
const REEL_DELAYS = [0, 200, 400, 600, 800];  // ms stagger between reels
const REEL_DUR    = 1800;                       // ms each reel spins
```

Increase `REEL_DUR` for longer drama, decrease for snappier results.

### Change the color scheme

Column colors are set in `server.py` inside the `DEFAULTS` list — one `"color"` hex value per column. Update them there and they'll flow through to both the kiosk and admin portal.

### Screen rotation

If your touchscreen is mounted rotated, add to `/boot/config.txt`:

```
# 90° clockwise
display_rotate=1

# 180°
display_rotate=2

# 270° clockwise (90° counter-clockwise)
display_rotate=3
```

---

## Troubleshooting

**Kiosk screen is blank after boot**

The Flask server may not have started yet when Chromium launched. The kiosk retries the API with exponential backoff — wait 10–15 seconds. If it stays blank, check the service:

```bash
sudo systemctl status fitslot
sudo journalctl -u fitslot -n 40
```

**WiFi radio soft-blocked / `rfkill` errors on every boot**

The most common cause is a missing WiFi country code. Run:

```bash
sudo raspi-config
```

Navigate to **Localisation Options → WLAN Country** and select your country. Reboot. This must be done once on every fresh Pi image and is the root cause of `Wi-Fi is currently blocked by rfkill` messages at boot.

**`FITSPIN-ADMIN` WiFi network not appearing**

```bash
sudo systemctl status hostapd
sudo journalctl -u hostapd -n 20
```

Common cause: another process is holding `wlan0`. Reboot and check that no `wpa_supplicant` instance is running for `wlan0`.

**Admin portal unreachable at 10.0.0.1**

Confirm you're connected to `FITSPIN-ADMIN`, not your regular WiFi. Also confirm dnsmasq is running:

```bash
sudo systemctl status dnsmasq
```

**Touchscreen not registering taps**

```bash
sudo apt-get install xserver-xorg-input-evdev
sudo reboot
```

**Exercises reset to defaults after reboot**

This only happens on the very first boot before any data file exists — correct behavior. Load your CSV via the admin portal once and it will persist in `data/exercises.json` from then on.

**`pip install flask` fails**

On Bookworm (if you're using it anyway):

```bash
pip3 install flask --break-system-packages
```

Or use a virtual environment:

```bash
python3 -m venv /home/pi/fitslot/venv
/home/pi/fitslot/venv/bin/pip install flask
# Update ExecStart in fitslot.service to use venv/bin/python3
```

**Screen goes blank / sleeps**

Confirm these lines are in your autostart file:

```
@xset s off
@xset -dpms
@xset s noblank
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│               Raspberry Pi                  │
│                                             │
│  ┌──────────┐    HTTP     ┌──────────────┐  │
│  │ Chromium │ ──────────► │  Flask       │  │
│  │  Kiosk   │ ◄────────── │  server.py   │  │
│  │ :display │  JSON API   │  :80         │  │
│  └──────────┘             └──────┬───────┘  │
│                                  │          │
│                           ┌──────▼───────┐  │
│                           │  data/       │  │
│                           │  exercises   │  │
│                           │  .json       │  │
│                           └──────────────┘  │
│                                             │
│  wlan0 ──► hostapd (AP)                     │
│            dnsmasq (DHCP + DNS)             │
│            SSID: FITSPIN-ADMIN              │
│            IP:   10.0.0.1                   │
└─────────────────────────────────────────────┘
           │
           │ WiFi
           │
    ┌──────┴──────┐
    │  Staff      │
    │  phone /    │
    │  laptop     │
    │             │
    │  browser →  │
    │  /admin     │
    └─────────────┘
```

The Flask server handles three concerns:
1. **Serving static files** — `index.html` and `admin.html` from `static/`
2. **Exercise API** — `GET /api/exercises`, `POST /api/column/<n>`, CSV upload/download, reset
3. **WiFi API** — `GET/POST /api/wifi` reads and rewrites `hostapd.conf`, restarts the service

All exercise data lives in `data/exercises.json`. The kiosk fetches it fresh on load; the admin portal reads and writes it live.

---

## License

MIT — free to use, modify, and deploy commercially.
