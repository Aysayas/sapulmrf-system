# Device contract (draft for Rhendel)

What the API accepts today. Replaces the two contract lines in `docs/roadmap.md`. **Open questions are at the end.**

## All devices
- Plain HTTP(S) to the API, with the key from Settings › Devices in an `X-Device-Key` header. The key is shown once.
- Post a reading or heartbeat at least every 60 s. A device silent for 2 minutes shows as offline.
- **With a synced clock:** send `read_at`, but only once NTP or an RTC has set the time since this boot. A wrong early time gets stored as old history.
- **Without one:** leave `read_at` out, and don't buffer or retry. Send the next fresh reading instead, because a retry without `read_at` stores a second row.

## Retry rules (devices sending `read_at`)
| Response | Meaning | What the device does |
|---|---|---|
| 2xx | Accepted | Drop it from the buffer |
| 5xx, timeout, no network | Not known to be stored | Keep it and retry with the same `read_at`, waiting 5 s, 10 s, 20 s, up to 5 min, plus a random 0 to 5 s |
| 401, 403 | Bad key, or a non-camera posting to the camera route | Stop and show a fault; retrying won't help |
| 422 saying `read_at` is in the future | The device's clock is ahead | Resend without `read_at` and show a fault |
| Any other 422 | The reading is invalid | Drop it and log it; retrying won't help |

**Buffer:** RAM is enough, so a reboot may lose readings. Cap it (about the last 500, dropping the oldest), and send the backlog oldest first, one at a time.

## `POST /devices/readings`
**Weighing station:** `{"kg": 12.4, "stable": true, "read_at": "2026-11-01T08:30:00+08:00"}`

**Compost sensor:** `{"temp_c": 55.2, "moisture_pct": 52.0, "read_at": "2026-11-01T08:30:00+08:00"}`

- `read_at` is optional and must include a timezone. A time more than 5 minutes ahead of the server gets 422.
- **Resending is safe when `read_at` is sent:** a compost sensor's reading is stored once per device and time. Scale readings aren't kept as history; only the latest is held.
- **Late readings:** an older reading is kept in the batch's history, but it won't replace the newer reading shown on screen.
- **Scale weights:** a delivery recorded as `scale` needs a `stable` reading from the last 10 minutes, or the operator records it as manual.
- **Every reading counts as a heartbeat.**

Response: `{"device": "SCALE-1", "stored_on": "B-12"}`. `stored_on` is the batch, or null for a scale or a sensor with no active batch.

## `POST /devices/cv-suggestions`
`{"label": "Plastic", "confidence": 0.91, "model_version": "v1", "image_url": "https://..."}`

- `label` must match an active material name, or the API returns 422.
- `image_url` must be an http or https address, or empty.

## `POST /devices/deliveries`
The resident kiosk records a drop-off. Only a weighing station's key is accepted (others get 403).

`{"source_area": "Purok 3", "category": "Recyclable", "weight_kg": 4.25, "weighed_by": "scale", "client_key": "6f1c2e0a-..."}`

- `source_area` and `category` are names, matched without regard to capitals. An unknown or inactive one gets 422.
- `client_key` is required, 8 to 36 characters; a UUID is best. **Resending is safe:** the same `client_key` returns the first drop-off's code and stores nothing new. Keep unsent drop-offs and retry them with the same key, using the retry rules above.
- **`scale` weights:** the station must have posted a `stable` reading in the last 10 minutes, and `weight_kg` must equal that reading. Otherwise 422; send `manual` if the weight was typed in.
- The delivery is stored with this device and no user, and the activity log names the device.
- **The kiosk is one device.** Register it once as a weighing station (e.g. `KIOSK-01`), even though it also runs the camera. Its laptop makes every call with that key.
- **Optional camera result:** `"cv": {"category": "Recyclable", "counts": {"recyclable": 3, "residual": 1, "bio": 0}, "confidence": 0.82}`. It's kept beside the category the resident confirmed, so the two can be compared later.
- **Optional `"photo"`:** the snapshot as a base64 JPEG, about 2 MB at most. Admins and operators see it at `GET /deliveries/{id}/photo`. A resend keeps the first photo. Bad base64, or a file that isn't a JPEG, gets 422.
- **Optional `"materials"`:** `[{"label": "Plastic", "confidence": 0.86}]`, at most 10. The kiosk camera is also the sorting-area camera, so each material becomes a pending suggestion in Operations › Sorting with this drop-off's photo, for the operator to confirm.
  - Labels are matched to active materials without regard to capitals. An unknown label is skipped, and never fails the drop-off.
  - A resend adds no new suggestions.

Response (201): `{"code": "D-0042", "actions": {"buzz": 1}}`.
- Show the code on the receipt, and beep `buzz` times.
- A receipt made while offline needs its own prefix (e.g. `K-0007`), so it never looks like a server code.

## `GET /devices/kiosk-state` (kiosk laptop, every ~5 s)
Weighing-station key only. Each call also counts as a heartbeat.

`{"today": {"kg": 128.4, "drops": 17}, "alerts": [{"kind": "storage", "title": "…", "details": "…"}], "actuators": {"light": "red", "buzz": 0}}`

- `alerts` lists the newest open alerts, up to 5.
- `light` is decided here, not on the kiosk:
  - `red` when any storage area is over capacity
  - `amber` for any other open alert
  - `green` otherwise

## `GET /devices/kiosk-recent`
Weighing-station key only. Returns this kiosk's latest 6 drop-offs, ready for its operator table:
`[{"code": "D-0042", "time": "9:41 AM", "purok": "Purok 3", "cat": "Recyclable", "kg": "4.2 kg"}]`

## `WS /devices/kiosk-live` (live camera for the website)
The kiosk's laptop opens a WebSocket with the weighing station's `X-Device-Key`. A bad key is refused (close code 1008).
- **SapulMRF sends** `{"viewers": n}` on connect and whenever the number of people watching changes. Send frames only while `n > 0`.
- **The laptop sends:**
  - each frame as one **binary** message: a JPEG, at most 2 MB, at the camera's resolution
  - then a **text** message `{"det": {…the detection…}, "w": 1280, "h": 720}`

  A frame that isn't a JPEG, or is too big, closes the socket (code 1009).
- A new connection from the same device replaces the old one. Frames are kept in memory only, and nothing is recorded.
- **Admins and operators watch** at `GET /devices/{id}/live.mjpg`, an MJPEG stream that an `<img>` plays. `GET /devices/live` lists the feeds with fps, size, viewers and the latest detection. A feed counts as live while frames arrive at least every 3 s.

## Open questions for Rhendel
1. **Camera images:** where do photos live? The roadmap planned `image_id` and `taken_at`; the API takes `image_url` and has no `taken_at`. A photo must be reachable from the operator's browser.
2. **Camera retries:** resending a suggestion creates a second one, since it has no ID yet. Can the camera send a unique ID per item?
3. **Which delivery a suggestion belongs to:** suggestions aren't linked to a delivery. Does the workflow need that?
4. **Device clocks:** will devices have NTP or an RTC? Without one they can't send `read_at`, so offline readings can't be backdated.
5. **Transport:** HTTP is assumed. MQTT would need another service, so please say if the hardware requires it.
6. **Server:** CPU, RAM, OS, and whether it's reachable from the barangay hall.
