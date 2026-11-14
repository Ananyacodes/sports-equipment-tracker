#!/usr/bin/env bash
# Runs the UI + API + Postgres stack on a user-defined Podman network.
# Containers reach each other by name (db, api) through the network's DNS;
# only the UI port is published to the host.
set -e

NET=equip-net
VOL=pgdata

podman build -t sports-tracker-api:1.0 -f Containerfile.api .
podman build -t sports-tracker-ui:1.0  -f Containerfile.ui  .

podman network exists "$NET" || podman network create "$NET"
podman volume exists  "$VOL" || podman volume create  "$VOL"

podman rm -f ui api db 2>/dev/null || true

podman run -d --name db --network "$NET" \
  -e POSTGRES_DB=equipment \
  -e POSTGRES_USER=equip \
  -e POSTGRES_PASSWORD=equippass \
  -v "$VOL":/var/lib/postgresql/data \
  docker.io/library/postgres:16-alpine

podman run -d --name api --network "$NET" \
  -e PGHOST=db -e PGPORT=5432 \
  -e PGUSER=equip -e PGPASSWORD=equippass -e PGDATABASE=equipment \
  sports-tracker-api:1.0

podman run -d --name ui --network "$NET" -p 8080:8080 \
  -e API_URL=http://api:5000 \
  sports-tracker-ui:1.0

podman ps --filter network="$NET"
echo "UI: http://127.0.0.1:8080"
