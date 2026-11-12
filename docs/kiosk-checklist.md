# Kiosk fix checklist (for Rhendel)

Fixes for the drop-off kiosk in `C:\dev\sapulmrf-kiosk` (repo commit `34a087e`). Paths are under `sapulmrf-kiosk/`. Line numbers were checked on 2026-11-12. Nothing here has been edited; these are recommendations for Rhendel to agree to first. The SapulMRF side (item 2's route) is already built: see `docs/device-contract.md`, `POST /devices/deliveries`.

## Must fix

### 1. The camera model doesn't know waste
`pc_bridge/best.pt`, `pc_bridge/kiosk_bridge.py` (`bucket()`, L78)
- [ ] Train or supply a waste model, and update the class sets in `kiosk_bridge.py` to match its class names. `best.pt` is stock YOLO11n (80 everyday COCO objects). Only "bottle" counts as recyclable, fruit counts as residual, and a hand ("person") pushes nearly every scan to "Mixed household".
- [ ] Until then, ignore `person` in `bucket()` (one line) so a hand doesn't decide the category.

### 2. Point the upload at SapulMRF's device route
`pc_bridge/kiosk_bridge.py` L65, L173–184
- [ ] Replace the `/api/intake` POST with a Bearer token by `POST {SAPULMRF_API}/devices/deliveries` with header `X-Device-Key: <weighing station key from Settings › Devices>`.
- [ ] Body: `{"source_area": "Purok 3", "category": "Recyclable", "weight_kg": 4.25, "weighed_by": "manual" | "scale", "client_key": "<uuid4>"}`. Generate `client_key` once per drop-off and reuse it on every retry. The server then stores it only once.
- [ ] Show the server's code from the 201 response `{"code": "D-0042"}` on the receipt.
- [ ] When the server can't be reached (timeout, 5xx), save the CSV row as `pending` with its `client_key`, and show an offline code with its own prefix, e.g. `K-0007`. Never make up `D-` codes (L181): they clash with the server's.
- [ ] Add a retry loop that sends `pending` rows, oldest first, and marks them sent on 2xx. On 401/403 stop and log a fault. On any other 422, mark the row `rejected` and log the reason.
- [ ] Check the purok names on the kiosk ("Purok 1"–"Purok 7", `config.h` L40) match the names in SapulMRF exactly, or uploads get 422.

### 3. Drop-offs get lost
`SapulMRF_Kiosk/SapulMRF_Kiosk.ino` (`onConfirm`, L339; `sendPacket`, L201), `pc_bridge/kiosk_bridge.py` (L184, `read_loop` L255, `on_message` L270)
- [ ] Firmware: keep "Confirm drop-off" disabled while `pcUp` is false, and show "Camera PC offline". Today the message is dropped and the receipt shows "..." forever.
- [ ] Bridge: wrap the body of `on_message` in `try/except Exception` and log the error, so one bad message can't drop the link.
- [ ] Bridge: if the CSV write fails (e.g. `PermissionError` while `kiosk_intake.csv` is open in Excel), send `{"type":"receipt","ok":false}`. The kiosk shows "Not saved, ask the operator".

### 4. Anyone on the kiosk's Wi-Fi can take it over
`SapulMRF_Kiosk.ino` (`auth` handling L640, connection L661–690), `config.h` L17, L41, `kiosk_bridge.py`
- [ ] Add a shared secret to `config.h` and the bridge's environment. The PC's first message must be `{"type":"hello","key":"…"}`, or the kiosk closes the connection.
- [ ] Don't let a new client replace a connected PC that has already said hello. Today any phone on the hotspot can connect, send `{"type":"auth","ok":true}` to open the operator screen, or send fake receipts.
- [ ] Lock the PIN pad for 30 s after 5 wrong tries.
- [ ] Move the PIN (`1234`) and hotspot password (`sapulmrf123`) out of the README and committed `config.h`, into a git-ignored `secrets.h` and env values.

## Should fix

### 7. Only accept a stable scale weight
`SapulMRF_Kiosk.ino` (`USE_HX711` block, L927+)
- [ ] With `USE_HX711` on, enable Confirm only after N readings in a row fall within ±0.05 kg.
- [ ] Post that reading to `POST /devices/readings` as `{"kg": …, "stable": true}` before the drop-off, then send the drop-off with `weighed_by: "scale"` and the **same** `weight_kg`. SapulMRF rejects a scale drop-off (422) without a stable reading from the last 10 minutes, or with a weight that differs from it.

## Done when
- [ ] With the API up, a drop-off shows a `D-` code and appears in SapulMRF Intake.
- [ ] With the API stopped, a drop-off shows a `K-` code and its CSV row is `pending`. After the API starts again, it is sent within the retry interval and appears once.
- [ ] With the CSV open in Excel, a drop-off shows "Not saved" and the link stays up.
- [ ] A second device connecting to the kiosk without the shared secret is refused.
