# HikeBot – Hiking Group Chatbot

Initial milestone delivers a FastAPI skeleton that will grow into a planning and safety copilot for hiking crews.

## Project Layout
```
hikebot/
├─ backend/
│  ├─ app.py              # FastAPI entrypoint + endpoints
│  ├─ db.py               # Temporary in-memory data helpers
│  ├─ models.py           # Pydantic schemas shared across routes
│  ├─ route_provider.py   # Loads routes from Waymarked Trails or seed fixtures
│  ├─ seed_routes.py      # Loads Trailforks export (or fallback fixtures)
│  ├─ fetch_trailforks_routes.py  # CLI to sync Trailforks data locally
│  ├─ data/
│  │  └─ trailforks_routes.json   # Generated seed file (gitignored)
│  ├─ waymarked_client.py # Thin wrapper around the Waymarked Trails API
│  ├─ requirements.txt    # Python dependencies
│  └─ .env.example        # Sample configuration for local dev
├─ frontend/
│  ├─ app.py              # Streamlit chat interface
│  ├─ requirements.txt    # UI dependencies
│  └─ .env.example        # BACKEND_URL config for the UI container
├─ docker-compose.yml     # API + Postgres + Redis stack
└─ README.md
```

## Getting Started
1. **Copy env vars**  
   `cp backend/.env.example backend/.env` (edit values as needed).
   
2. **Launch services**  
   `docker compose up --build` – this installs Python deps inside the containers, starts FastAPI, and brings up the Streamlit UI.
3. **Open the chatbot**  
   Visit `http://localhost:8501` for the HikeBot UI (log in/sign up to chat, view trip history, and pull weather snapshots) or use the REST API directly:
   - Health: `GET http://localhost:8000/health`  
   - Route recs: `POST http://localhost:8000/routes/recommendations`  
     ```json
     {
       "max_distance_km": 15,
       "max_drive_time_min": 120,
       "need_water": true
     }
     ```
   - Gear checklist: `POST http://localhost:8000/gear/checklist`
   - Weather: `POST http://localhost:8000/weather/snapshot`

The backend can now source live routes from the Waymarked Trails API (see below) and falls back to in-memory fixtures when no API credentials are provided. Postgres/Redis containers are placeholders for the upcoming persistence and job layers planned in Milestone 2. The Streamlit UI proxies requests to `/chat`, shows each user’s trip history in the sidebar, and handles simple signup/login (credentials live in-memory for demo purposes).

## Route Data Sources
HikeBot attempts to pull real routes from [Waymarked Trails](https://waymarkedtrails.org) at startup. Configure the integration in `backend/.env`:

```
WAYMARKED_API_URL=https://hiking.waymarkedtrails.org/api/v1
WAYMARKED_THEME=hiking
WAYMARKED_LIMIT=25
WAYMARKED_BBOX=-124.3,32.5,-113.5,42.0  # optional bounding box (lon/lat pairs)
```

- Leave `WAYMARKED_API_URL` empty to stick with the baked-in fixtures.
- Adjust the bounding box/limit if you want to constrain the download to a specific region.
- The loader logs a warning and falls back to `seed_routes` if the API cannot be reached (useful for offline dev).

Trailforks exports are still supported for deterministic testing. Run `fetch_trailforks_routes.py` and keep the resulting JSON under `backend/data/` if you prefer those fixtures.

## Trail Groups
Each route spawns a lightweight “group chat” on the backend. Call:
- `POST /groups/join` with `{ "route_id": "<id>", "username": "<user>" }` to join a trail group.
- `POST /groups/leave` with `{ "route_id": "<id>", "username": "<user>" }` to leave it.
- `GET /groups/{route_id}/members` to see who’s going.
- `GET /groups/{route_id}/messages` to pull the current group chat log.
- `POST /groups/message` with `{ "route_id": ..., "username": ..., "content": ... }` to chat with that group.

The Streamlit UI exposes these controls in the left sidebar; once a user joins a trail, the sidebar shows the current roster for that group chat.

## Weather Data
- `/weather/snapshot` now calls the Open-Meteo API via `openmeteo_requests`, so no API key is required. Latitude/longitude are taken from the selected route (or default to Los Angeles if absent), cached for an hour, and summarized into `temp_c`, precipitation probability, and simple lightning/fire risk hints.
- Weather details feed the backend’s reasoning (and HikeBot’s replies) rather than a standalone UI widget.

## Syncing Routes from Trailforks
1. Request a Trailforks API key (Pinkbike account required) and set it locally:  
   `export TRAILFORKS_API_KEY=your-key`.
2. Fetch routes for a region and store them under `backend/data/trailforks_routes.json`:  
   ```bash
   cd backend
   python fetch_trailforks_routes.py --region-id 1234 --limit 50
   ```
3. Restart the API. `seed_routes.get_seed_routes()` now prefers the freshly-exported JSON over the baked-in fixtures, so the `/routes` endpoint immediately serves real data.

> Tip: rerun the script whenever you need fresh mileage/elevation info; commit the JSON only if you want deterministic seeds for the milestone.
