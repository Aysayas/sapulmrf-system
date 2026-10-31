#!/bin/sh
# One database backup, then old ones removed. Runs inside the backup container (see docker-compose.prod.yml).
set -eu
stamp=$(date +%Y-%m-%d_%H%M)
# Written to a temporary name first, so a failed dump never looks like a good backup.
pg_dump -Fc -f "/backups/.sapulmrf_$stamp.tmp"
mv "/backups/.sapulmrf_$stamp.tmp" "/backups/sapulmrf_$stamp.dump"
find /backups -name 'sapulmrf_*.dump' -mtime "+${KEEP_DAYS:-14}" -delete
echo "$(date '+%F %T') backup saved: sapulmrf_$stamp.dump"
