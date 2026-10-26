# We connect and deploy our four-device system

We use two **classic ESP32 development boards with onboard USB-to-UART bridges** (for example ESP32-WROOM-32 DevKit boards), a Windows gateway PC, and a separate operator PC. ESP32-C3/S3 native USB configurations are outside this initial hardware target.

## 1. Our hardware and wiring

We need two ESP32 development boards, two suitable USB cables, a Windows PC with Wi-Fi/hotspot support, and a second PC with a browser. The cable to A must carry data; a charge-only cable will not create a COM port.

| Connection | What we physically connect | Why |
|---|---|---|
| ESP32 A to gateway | Board's USB connector to a gateway USB port using a data cable | Power plus the required wired USB serial link |
| ESP32 B during flashing | Board's USB connector to a PC USB port using a data cable | Flashing and reading its Wi-Fi IP address |
| ESP32 B during operation | Keep its USB attached for power, or use a suitable USB supply | Production messages use Wi-Fi, not this USB connection |
| Operator PC to gateway network | Connect to gateway hotspot | Browser HTTP commands and WebSocket status |

We need **no GPIO jumper wires, breadboard, sensor, resistor, or connection between the two ESP32s**. A's onboard USB bridge already connects to ESP32 UART0 (GPIO1 TX and GPIO3 RX). We leave those pins free. USB supplies the boards through their onboard power circuits; we do not inject 5 V into a GPIO or 3V3 pin.

```text
Windows gateway USB ── data cable ── ESP32 A USB
Windows/USB supply  ── USB cable  ── ESP32 B USB (power / flash)

ESP32 B )) 2.4 GHz Wi-Fi (( Windows gateway hotspot
Operator PC )) Wi-Fi    (( Windows gateway hotspot
```

## 2. We identify the COM ports

1. We open Windows Device Manager → Ports (COM & LPT).
2. We plug in A and note the newly appearing port. We label the board and record its COM number.
3. We repeat for B. CP210x and CH340 bridges may require the board manufacturer's USB driver.
4. We can also run `python -m serial.tools.list_ports -v` from our virtual environment after installing dependencies.

We do not assume `COM3` belongs to A: the configuration value is a placeholder. Bluetooth serial ports are not our boards.

## 3. We prepare ESP-IDF through VS Code

The Espressif IDF extension was found installed on the initial development PC; an installed extension does not prove the ESP-IDF SDK/toolchain is configured.

1. We open VS Code and install/enable **Espressif IDF** if necessary.
2. We use its setup/installation workflow to install or select **ESP-IDF v5.5.1**, with the ESP32 toolchain. The exact setup entry depends on the installed extension version; we follow the [official installation guide](https://docs.espressif.com/projects/vscode-esp-idf-extension/en/latest/index.html).
3. We run **ESP-IDF: Doctor Command** to check the selected setup.
4. We open a firmware project folder as described below and use **ESP-IDF: Open ESP-IDF Terminal**. This terminal provides `idf.py`, CMake, Ninja, and the compiler environment.

We can browse everything through `mct431.code-workspace`. To avoid selecting the wrong ESP-IDF project in a multi-root workspace, the simplest flashing workflow uses a separate VS Code window for each firmware folder.

## 4. We flash ESP32 A — production

1. We open `firmware/production` as a folder in VS Code.
2. We select the installed ESP-IDF setup and target **esp32**.
3. We use **ESP-IDF: Select Port to Use** and choose A's actual COM port.
4. We open the ESP-IDF terminal in this folder and run, replacing `COM_A` with the actual port:

```powershell
idf.py set-target esp32
idf.py build
idf.py -p COM_A flash
```

We can instead use the extension's Build and Flash commands. If automatic boot entry fails, we hold BOOT while connection begins and release it when flashing starts; some boards also need an EN/reset press.

**We do not leave a serial monitor connected to A.** Its UART0 is reserved for binary ATR/SLIP application frames, and normal application console output is disabled. A monitor may display unreadable binary data and will prevent the gateway from opening the port. The gateway's serial evidence is our normal diagnostic record for A. Boot ROM text can still appear briefly after reset; the decoder ignores noise before valid frames.

## 5. We create the gateway Wi-Fi network

1. On the Windows gateway, we open Settings → Network & internet → Mobile hotspot.
2. We choose an SSID such as `MCT431-Lab`, set a password, and choose **2.4 GHz**. Classic ESP32 does not connect to a 5 GHz-only hotspot.
3. We turn on the hotspot and disable automatic hotspot shutdown if available.
4. We connect the operator PC to it.
5. We use `ipconfig` to find the hotspot adapter's IPv4 address. Windows often uses `192.168.137.1`, but we verify it instead of assuming it.

If Windows cannot provide a working hotspot with the available network adapter, we can use a small 2.4 GHz router instead, as permitted in the assignment. The gateway, B, and operator PC must share a reachable network with client isolation disabled.

## 6. We configure and flash ESP32 B — inspection

1. We open `firmware/inspection` in its own VS Code window.
2. We select **esp32**, B's COM port, and the same ESP-IDF setup.
3. In the ESP-IDF terminal we run:

```powershell
idf.py set-target esp32
idf.py menuconfig
```

4. In **MCT431 inspection network**, we enter the exact hotspot SSID and password. We save and exit. We use WPA2 or compatible WPA2/WPA3 mixed mode; open networks are not the chosen configuration.
5. We build, flash, and monitor B:

```powershell
idf.py build
idf.py -p COM_B flash monitor
```

6. We find the line `Inspection address: ...` and record B's assigned IPv4 address. We exit the monitor with **Ctrl+]** when finished.

`sdkconfig` contains the Wi-Fi credentials and is ignored by Git. We never put actual credentials in committed `sdkconfig.defaults`. If we rerun `set-target`, it may regenerate configuration; we check Wi-Fi settings again before rebuilding.

B's USB monitor can be used for diagnostic logs while its application exchanges TCP over Wi-Fi. Port **9000** is the default inspection TCP server port.

## 7. We set up the gateway

From the repository root in a normal PowerShell terminal:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
Copy-Item config/design.toml config/local.toml
```

We edit `config/local.toml`:

```toml
[communication]
serial_port = "COM7"                  # Example: replace with A's COM port
baud_rate = 115200
inspection_host = "192.168.137.42"     # Example: replace with B's logged IP
inspection_port = 9000
ack_timeout_s = 2.0
completion_grace_s = 2.0
max_attempts = 3
heartbeat_timeout_s = 4.0
reconnect_s = 1.0
```

We preserve the other sections from the copied file. We do not paste only this section as the entire configuration.

We start physical-device mode:

```powershell
.\.venv\Scripts\python.exe -m gateway --config config/local.toml
```

We open `http://localhost:8000` on the gateway. The badge must say **HARDWARE** and both stations must become online. We allow several seconds for the serial connection, Wi-Fi, and session binding.

We then open `http://<gateway-hotspot-IP>:8000` on the **separate operator PC**. If Windows Firewall blocks it, we allow this Python executable on our lab/private network. A narrowly scoped administrator rule is an optional manual step:

```powershell
New-NetFirewallRule -DisplayName "MCT431 operator UI" -Direction Inbound -Action Allow -Protocol TCP -LocalPort 8000 -Profile Private -RemoteAddress LocalSubnet
```

We ensure the lab adapter has the intended network profile. We do not disable the firewall globally. The gateway initiates TCP to B on port 9000, so the gateway does not need an inbound 9000 rule.

## 8. We run a first physical batch

1. We enter target `10`, queue `2`, production `500 ms`, inspection `1000 ms`, `N=3`, and `K=0`.
2. We press Start and watch the queue and counts.
3. With a fresh gateway session, IDs 1–10 produce three FAILs (3, 6, 9) and seven PASSes. Subsequent batches continue the part IDs; expected verdicts must use the displayed/logged IDs.
4. We check the final state is Idle with outcome `completed`, produced `10`, and accepted + rejected `10`.
5. We follow the full [test guide](TESTING.md) before claiming Milestone 1 is demonstrated.

## 9. We recover and debug

| Symptom | What we check |
|---|---|
| A offline | Correct data cable and COM port; monitor closed; correct production firmware; UART 115200 |
| B offline | 2.4 GHz SSID/password; B's current DHCP IP; both PCs on the same network; TCP 9000 reachable |
| UI works locally but not remotely | Gateway hotspot IP; operator network; Windows Firewall/network profile |
| Fault after reset/disconnect | We retain fault evidence, press Stop to acknowledge, wait for both online, then start a new batch |
| Gateway restarted | Stations may still hold the previous gateway session; they reboot after six seconds without a valid heartbeat, or we press EN/reset |
| Queue apparently smaller than capacity | Capacity counts waiting parts. One part can be in inspection and one reserved production slot is included in capacity enforcement |
| Timings near 1 ms differ from settings | Timers set the requested work duration; scheduling, transport polling, and overhead add latency |

We finish with Ctrl+C on the gateway. Pending jobs are not recovered across restart. We retain the run folder as evidence of any interrupted batch.
