# Sports Equipment Tracker

Tracks issue/return of sports equipment with live availability and a
low-stock threshold warning, running as rootless Podman containers.

Two implementations are included:

1. **CLI + SQLite** (`app.py`) — a single-file, zero-dependency version
   for minimal footprint / offline use.
2. **Web UI + API + PostgreSQL** (`ui.py` + `api.py` + Postgres) — a
   three-container stack with a browser UI, for anything needing
   concurrent access or a visual demo.

## Architecture (UI + API + Postgres)

```
 browser ──▶ ui (Flask, :8080) ──HTTP──▶ api (Flask, :5000) ──SQL──▶ db (Postgres, :5432)
```

- `ui` renders the page and forms. It holds no DB connection of its own.
- `api` is the *only* container that talks to Postgres — owns all reads/writes.
- `db` is stock `postgres:16-alpine`, data persisted via a named volume (`pgdata`).
- All three run in one Podman **pod**, sharing a network namespace, so
  `ui` and `api` reach each other and Postgres via `localhost`.

This separation matters for a reason beyond tidiness: SQLite doesn't
handle concurrent writers well, so once a UI is in the picture, a real
DB server (Postgres) behind a single API owner avoids locking issues.

## Prerequisites

- [Podman](https://podman.io/) installed (`podman --version` to check)
- No other dependencies on the host — everything else runs in containers

## Repo structure

```
.
├── app.py                  # CLI version (SQLite, stdlib only)
├── Containerfile            # Image for the CLI version
├── api.py                  # API service (Flask + Postgres via pg8000)
├── Containerfile.api        # Image for the API service
├── requirements-api.txt
├── ui.py                   # UI service (Flask, talks to api over HTTP)
├── Containerfile.ui          # Image for the UI service
├── requirements-ui.txt
├── seed.sh                 # Demo data script (curl against the running UI)
└── README.md
```

## Quick start — Web UI + API + Postgres

```bash
# 1. Build the two application images
podman build -t sports-tracker-api -f Containerfile.api .
podman build -t sports-tracker-ui  -f Containerfile.ui  .

# 2. Create the pod (shares network namespace; exposes the UI port)
podman pod create --name equip-pod -p 8080:8080

# 3. Persistent volume for Postgres data
podman volume create pgdata

# 4. Start Postgres
podman run -d --pod equip-pod --name db \
  -e POSTGRES_DB=equipment \
  -e POSTGRES_USER=equip \
  -e POSTGRES_PASSWORD=equippass \
  -v pgdata:/var/lib/postgresql/data \
  docker.io/library/postgres:16-alpine

# 5. Start the API (retries DB connection on startup — safe to start before db is ready)
podman run -d --pod equip-pod --name api \
  -e PGHOST=localhost -e PGPORT=5432 \
  -e PGUSER=equip -e PGPASSWORD=equippass -e PGDATABASE=equipment \
  sports-tracker-api

# 6. Start the UI
podman run -d --pod equip-pod --name ui \
  -e API_URL=http://localhost:5000 \
  sports-tracker-ui

# 7. Confirm all three are up
podman ps --pod
```

Open **http://localhost:8080**.

### Load demo data

```bash
chmod +x seed.sh
./seed.sh
```

Adds five equipment types, issues some out (two of which cross their
threshold and show `LOW STOCK`), and records one return — a realistic
spread for a demo. See `seed.sh` for the exact commands; each one is a
plain `curl -4 -X POST` against the UI, so you can also run them
individually or adapt the values.

> **Note:** use `curl -4` (force IPv4), or `curl http://127.0.0.1:8080/...`
> directly. On some Podman/host setups, `localhost` resolves to `::1`
> first and the IPv6 listener isn't bound, which gives a
> `Connection reset by peer` error — IPv4 works fine.

### Stopping / restarting

```bash
podman pod stop equip-pod       # stop everything
podman pod start equip-pod      # start again — data in pgdata persists
podman pod rm -f equip-pod      # remove containers (volume `pgdata` survives)
```

## Quick start — CLI only (SQLite)

For a minimal, dependency-free version (one container, no Postgres):

```bash
podman build -t sports-tracker -f Containerfile .
podman volume create tracker-data

podman run --rm -v tracker-data:/app/data sports-tracker add Football --quantity 10 --threshold 3
podman run --rm -v tracker-data:/app/data sports-tracker issue Football --quantity 2 --person Rahul
podman run --rm -v tracker-data:/app/data sports-tracker return Football --quantity 1 --person Rahul
podman run --rm -v tracker-data:/app/data sports-tracker list
podman run --rm -v tracker-data:/app/data sports-tracker history
```

## API reference (api.py)

| Method | Path                          | Body / Params                       | Purpose                        |
|--------|-------------------------------|--------------------------------------|---------------------------------|
| GET    | `/equipment`                  | —                                     | List all equipment + status     |
| POST   | `/equipment`                  | `name, quantity, threshold`           | Register new equipment          |
| POST   | `/equipment/<name>/restock`   | `quantity`                            | Increase stock                  |
| POST   | `/equipment/<name>/issue`     | `quantity, person`                    | Issue + record transaction      |
| POST   | `/equipment/<name>/return`    | `quantity, person`                    | Record a return                 |
| GET    | `/history?name=&limit=`       | —                                     | Transaction log                 |

The UI's routes (`/`, `/add`, `/issue`, `/return`) are thin wrappers
that POST to these and redirect back to `/` with a flash message.

## Design notes

- **Low footprint:** `python:3.12-alpine` base images, stdlib-only CLI
  version, and pure-Python dependencies (`pg8000`, `flask`, `requests`)
  in the web version so no C build toolchain is needed in the image.
- **Persistence:** SQLite file (CLI) or Postgres data directory (web
  version) both live on named Podman volumes, so data survives
  container removal/recreation.
- **Low-stock warning:** checked server-side on every `issue` and
  reflected in `list`/the UI table — not something the client computes.
