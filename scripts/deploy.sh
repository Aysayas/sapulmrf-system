#!/bin/sh
# Usage: scripts/deploy.sh v1.2.0   Backs up, moves to that tag, migrates, restarts and checks health.
set -eu
tag=${1:?usage: scripts/deploy.sh <git tag>}
compose="docker compose -p sapulmrf -f docker-compose.prod.yml --env-file .env.prod"

# First install: the database isn't running yet, so there's nothing to back up.
if $compose ps --status running --services | grep -qx backup; then
  $compose exec -T backup sh /backup.sh
fi

git fetch --tags
git checkout "$tag"
$compose build
$compose up -d --wait db
$compose run --rm --no-deps api alembic upgrade head
$compose up -d --remove-orphans --wait
$compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read().decode())"
echo "Deployed $tag"
