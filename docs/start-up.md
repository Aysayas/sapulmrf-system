# Start-up: the website and the kiosk

The order to start everything for a day of use or a demo. The website runs in Docker on the laptop. The kiosk talks to it through the camera bridge (`kiosk_bridge.py`), which also runs on the laptop.

```
Docker (db, api, web, worker)  ◄── HTTP 8001 ──  kiosk_bridge.py (USB camera, YOLO)  ── Wi-Fi TCP 5000 ──►  ESP32 kiosk
        ▲                                                       ▲
 browser 127.0.0.1:5174                              finds the kiosk by its UDP 5001 beacon
```

## 1. The website (Docker)
1. Start **Docker Desktop** and wait for "Engine running".
2. In PowerShell:
   ```
   cd C:\dev\sapulmrf
   docker compose up -d --wait web
   start http://127.0.0.1:5174
   ```
   `--wait` returns once the database, API and website are healthy (about 30 s; a few minutes the first time).
3. Check the API: http://127.0.0.1:8001/health should show `"status":"ok"`.
4. After pulling new code, run `docker compose exec api alembic upgrade head` once.

First-time setup (the `.env` file and your admin account) is in the [README](../README.md#run-locally).

## 2. The kiosk
1. Turn the kiosk on. It joins the Wi-Fi in `config.h` (the laptop must be on the **same** 2.4 GHz network, today `Converge_2.4GHz_274fG7`).
2. The welcome screen shows the network and the kiosk's IP. **The IP can change** after a restart (it was .8, then .5); that's fine as long as the bridge isn't given a fixed IP.

## 3. The camera bridge
In a **separate PowerShell window** you leave open:
```
cd C:\dev\sapulmrf-kiosk\sapulmrf-kiosk\pc_bridge
$env:SAPULMRF_API = "http://127.0.0.1:8001"
py kiosk_bridge.py --model best.pt --cam 0
```
- `SAPULMRF_KEY` (the kiosk's device key from Settings › IoT devices) is read from your Windows user environment. If the bridge prints `SAPULMRF_KEY missing!`, set it once with `setx SAPULMRF_KEY "mrfk_..."` and open a new window.
- **Don't add the IP.** Without it the bridge listens for the kiosk's beacon and finds it at whatever address it has. Only add one if it says "Looking for the kiosk" forever.
- Connected when the kiosk's welcome screen shows the camera PC as connected, and the status dot is green.
- `--cam 0` is the first USB camera; try `--cam 1` if the picture is the laptop's own webcam.
- Add `--dev` only for screenshots and testing (step 5).

## 4. Use it
- **Residents:** drop-offs on the kiosk show a `D-` code on the receipt and appear in the website's Intake.
- **Operators:** on the kiosk, **Staff** → your name → your kiosk PIN (set on the website under Profile › Kiosk PIN). Lock, or 5 minutes idle, signs out.
- **Admin:** reviews sales, give-aways, recounts and fixes on the website afterwards (OK or Reverse).

## 5. Dev control (testing only)
With `--dev`, the bridge listens on http://127.0.0.1:8091 (this laptop only):

| URL | Does |
|---|---|
| `/signin?user_id=<id>&pin=<pin>` | Signs an operator in, like the PIN pad |
| `/goto?screen=sellform` | Shows a screen (`en` / `tl` switch the language) |
| `/shot?label=name` | Saves a screenshot to `pc_bridge/kiosk_shots/` |
| `/op?json={...}` | Runs an operator task as if the kiosk sent it |

`/goto` needs `DEV_TOOLS 1` in the kiosk's `config.h`.

## Without the website: the fake API
To test the kiosk with no Docker, the kiosk repo has a fake SapulMRF, `pc_bridge/fake_api.py`. It answers the bridge with demo data held in memory (Operator 1 PIN 1234, Operator 2 PIN 5678); nothing reaches this website.
1. Free port 8001: `docker compose stop api` (or run the fake with `--port 8011`).
2. Window 1: `cd C:\dev\sapulmrf-kiosk\sapulmrf-kiosk\pc_bridge; py fake_api.py`
3. Window 2: `$env:SAPULMRF_API="http://127.0.0.1:8001"; $env:SAPULMRF_KEY="fake"; py kiosk_bridge.py --model best.pt --cam 0 --dev`
4. Afterwards: Ctrl+C both, then `docker compose start api`.

Full guide, including load-cell testing: `C:\dev\sapulmrf-kiosk\sapulmrf-kiosk\docs\running.md`.

## Stop
- Bridge: Ctrl+C in its window.
- Website: `cd C:\dev\sapulmrf; docker compose --profile sim --profile ai down`. Data is kept.

## When it doesn't work
| What you see | Fix |
|---|---|
| `failed to connect to the docker API` | Docker Desktop isn't running. Start it, then step 1 again |
| Website shows "Something went wrong" | `docker compose restart api`; `docker compose logs api` shows the error |
| Bridge keeps saying "Can't reach kiosk at 192.168.x.x" | It was started with an old IP. Ctrl+C and start it again **without** the IP |
| Bridge says "Looking for the kiosk" forever | Laptop and kiosk are on different networks, or Windows Firewall blocks Python (allow it on **private** networks) |
| Kiosk ends up on its own `SapulMRF-Kiosk` hotspot | It didn't find the Wi-Fi. Check the router is on and 2.4 GHz; restart the kiosk |
| Kiosk receipts show `K-` codes | The API was down; the bridge keeps them in `outbox/` and sends them when the API is back |
| Operator PIN says "no answer" | The bridge isn't running or the API is down |
| The bridge window closed by itself | The laptop ran low on memory. Close other heavy apps (games, the AI model) and start it again |
| Two bridges running (port 8091 in use, camera busy) | Close the older window, or `Get-Process py, python` and stop the old one |
