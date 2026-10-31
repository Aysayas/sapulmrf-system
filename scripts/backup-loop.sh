#!/bin/sh
# Backs up every night at 02:00 Manila time. A failed backup is logged, and it tries again the next night.
while true; do
  now=$(date +%s)
  next=$(date -d "02:00" +%s)
  [ "$next" -le "$now" ] && next=$(date -d "tomorrow 02:00" +%s)
  sleep $((next - now))
  sh /backup.sh || echo "$(date '+%F %T') BACKUP FAILED"
done
