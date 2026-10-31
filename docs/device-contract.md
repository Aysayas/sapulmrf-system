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

## Open questions for Rhendel
1. **Camera images:** where do photos live? The roadmap planned `image_id` and `taken_at`; the API takes `image_url` and has no `taken_at`. A photo must be reachable from the operator's browser.
2. **Camera retries:** resending a suggestion creates a second one, since it has no ID yet. Can the camera send a unique ID per item?
3. **Which delivery a suggestion belongs to:** suggestions aren't linked to a delivery. Does the workflow need that?
4. **Device clocks:** will devices have NTP or an RTC? Without one they can't send `read_at`, so offline readings can't be backdated.
5. **Transport:** HTTP is assumed. MQTT would need another service, so please say if the hardware requires it.
6. **Server:** CPU, RAM, OS, and whether it's reachable from the barangay hall.
