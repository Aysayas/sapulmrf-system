# Simulator

The simulator stands in for Rhendel's devices and for an MRF operator until the real ones exist. Its code lives in `api/app/simulator.py`; the `sim` service runs that module from the api image.

```
docker compose --profile sim run --rm sim python -m app.simulator setup    # once: sim.operator + SIM- devices
docker compose exec api python -m app.simulator backfill --days 40         # optional: 40 days of history
docker compose --profile sim up -d sim                                     # live: deliveries, readings, camera
docker compose --profile sim stop sim                                      # pause it
docker compose exec api python -m app.simulator remove                     # delete everything simulated
```

`setup` uses the test admin from `.env` (`E2E_ADMIN_USERNAME` / `E2E_ADMIN_PASSWORD`). It saves a fresh operator password and the device keys in the `sim_state` volume.

What it does besides deliveries and readings:
- **Saturday pickups** become sale requests (placeholder prices in `PRICES`, not real junkshop rates) and residual disposal requests. Finished compost is given out to purok gardens, sometimes sold.
- **Recounts** every ~9 days become inventory adjustment requests, and 3% of weights are corrected at the scale.
- **The backfill** approves (or, for some recounts, rejects) and reviews everything older than 3 days as the test admin `e2e.admin`, so it needs that account. Newer items wait in the Approvals inbox.
- **The live loop** sends a sale, disposal or recount request about every 20 minutes.

Pace: set `SIM_PACE=0.5` in `.env` to run twice as fast. The default is a delivery every 1–2 minutes and readings every 30 s.

What's tagged as simulated, so `remove` can find it:
- the user `sim.operator`, and every record and request it made (with the stock rows an admin's approval of them wrote)
- devices `SIM-…`
- puroks and storage areas named `Demo …`, made only when no real ones exist yet

Real records are never touched.
