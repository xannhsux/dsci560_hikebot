# HikeBot – Hiking Group Chatbot

Initial milestone delivers a FastAPI skeleton that will grow into a planning and safety copilot for hiking crews.

## Project Layout
```
hikebot/
├─ backend/
│  ├─ app.py              # FastAPI entrypoint + endpoints
│  ├─ db.py               # Temporary in-memory data helpers
│  ├─ models.py           # Pydantic schemas shared across routes
│  ├─ seed_routes.py      # Loads Trailforks export (or fallback fixtures)
│  ├─ fetch_trailforks_routes.py  # CLI to sync Trailforks data locally
│  ├─ data/
│  │  └─ trailforks_routes.json   # Generated seed file (gitignored)
│  ├─ requirements.txt    # Python dependencies
│  └─ .env.example        # Sample configuration for local dev
├─ docker-compose.yml     # API + Postgres + Redis stack
└─ README.md
```

## Getting Started
1. **Copy env vars**  
   `cp backend/.env.example backend/.env` (edit values as needed).
2. **Launch services**  
   `docker compose up --build` – this installs Python deps inside the container and starts `uvicorn`.
3. **Hit the API**  
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

The backend currently relies on in-memory fixtures; Postgres/Redis containers are placeholders for the upcoming persistence and job layers planned in Milestone 2.

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
