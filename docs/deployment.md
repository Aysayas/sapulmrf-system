# Deployment

For the home server, once its specs are known. Run everything from the repo folder, on Linux with Docker.

**Tested on 2026-11-01** on the development laptop with a throwaway stack: HTTPS, the redirect from http, page links, secure cookies, a backup, and a restore into an empty database with matching row counts. **Not tested:** the real server, a public certificate, and `scripts/deploy.sh` end to end.

## First install
1. Copy `.env.prod.example` to `.env.prod` and set a new `DB_PASSWORD`, `SITE_ADDRESS` and `BACKUP_DIR`.
2. Run:
   ```bash
   scripts/deploy.sh <tag>
   ```
3. Create the first administrator; it asks for the details:
   ```bash
   docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod exec api python -m app.cli create-admin
   ```

## HTTPS
- **Domain (recommended, about the cost of the domain per year):** set `SITE_ADDRESS` to it. Caddy gets a free certificate. The server must be reachable on ports 80 and 443 from the internet, or the certificate needs DNS validation, which takes a Caddy plugin.
- **LAN only:** set `SITE_ADDRESS` to the server's IP. Caddy makes its own certificate, and each phone and PC must trust Caddy's root certificate, or browsers show a warning and PWA offline features won't work.

## Updating
```bash
scripts/deploy.sh <new tag>
```
It backs up, moves to the tag, migrates, restarts, and checks health.

**Rolling back:** run `scripts/deploy.sh <previous tag>` only if the update had no migration. If it did, restore the backup taken just before it (below) first, because the old code may not work with the new tables.

## Backups
- Saved nightly at 02:00 Manila time to `BACKUP_DIR`, and kept for 14 days.
- **Keep a copy off the server:** point `BACKUP_DIR` at an external drive or copy the files somewhere else. Backups on the same disk die with it.
- Backup now:
  ```bash
  docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod exec backup sh /backup.sh
  ```
- **Check them:** failures only appear in `logs backup`, so look at the backup folder's dates each week.

## Restoring
Records entered after the backup are lost.
1. Stop the writers:
   ```bash
   docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod stop api worker
   ```
2. Replace the database, using the backup's file name:
   ```bash
   docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod exec db sh -c 'dropdb -U "$POSTGRES_USER" "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" "$POSTGRES_DB"'
   ```
   ```bash
   docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner' < backups/sapulmrf_YYYY-MM-DD_HHMM.dump
   ```
3. Start again and check `/api/health`:
   ```bash
   docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod up -d
   ```

## Health
`https://<site>/api/health` shows `db` and `worker`. `worker: late` means alert checks have stopped: look at `logs worker`.

## Remote access
Use Tailscale's free tier so the server can be reached without opening router ports. Note that a public certificate through ports 80 and 443 does open them, so choose one approach with Rhendel.
