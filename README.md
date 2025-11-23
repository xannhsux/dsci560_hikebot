# HikeBot – Hiking Group Chatbot

This project delivers a FastAPI backend and Streamlit frontend to create a planning and safety copilot for hiking groups.

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
│  ├─ ui_home.py          # AI planning chat + trail search
│  ├─ ui_chat.py          # Group chat UI
│  ├─ ui_friends.py       # Friend list + add friends
│  ├─ ui_groups.py        # Create & join groups
│  ├─ ui_common.py        # Shared UI components (message bubbles, layout, etc.)
│  ├─ api.py              # Frontend → backend HTTP client
│  ├─ state.py            # Streamlit session state helpers
│  ├─ requirements.txt    # UI dependencies
│  └─ .env.example        # BACKEND_URL config for the UI container
├─ docker-compose.yml     # API + Postgres + Redis stack
└─ README.md
```

## Getting Started
1. **Copy environment variables**
   ```
   cp backend/.env.example backend/.env
   ```
   Modify values as needed.

2. **Launch services**
   ```
   docker compose up --build
   ```
   This installs dependencies inside containers, starts FastAPI, Postgres, Redis, and the Streamlit UI.

3. **Open the chatbot UI**
   Visit:
   ```
   http://localhost:8501
   ```

### API Examples
- Health check: `GET http://localhost:8000/health`
- Route recommendations:
  ```json
  {
    "max_distance_km": 15,
    "max_drive_time_min": 120,
    "need_water": true
  }
  ```
- Gear checklist: `POST /gear/checklist`
- Weather snapshot: `POST /weather/snapshot`

## Route Data Sources
HikeBot fetches routes from the Waymarked Trails API. Configure in `backend/.env`:

```
WAYMARKED_API_URL=https://hiking.waymarkedtrails.org/api/v1
WAYMARKED_THEME=hiking
WAYMARKED_LIMIT=25
WAYMARKED_BBOX=-124.3,32.5,-113.5,42.0
```

If the API cannot be reached, the backend automatically falls back to local seed data.

### Trailforks Data (Optional)
```bash
cd backend
export TRAILFORKS_API_KEY=your-key
python fetch_trailforks_routes.py --region-id 1234 --limit 50
```

## Trail Groups
Each route functions as a lightweight group chat.

- Join:
  ```
  POST /groups/join
  ```
- Leave:
  ```
  POST /groups/leave
  ```
- Members:
  ```
  GET /groups/{route_id}/members
  ```
- Chat messages:
  ```
  GET  /groups/{route_id}/messages
  POST /groups/message
  ```

## Friend System
HikeBot includes a simple friend system:

- Add friends by **friend code**
- Friend list displayed in `ui_friends.py`

Core endpoints:
```
POST /social/friends/send_request
POST /social/friends/accept
GET  /social/friends/list
GET  /social/friends/requests
```

## Groups & Group Chat
HikeBot supports custom groups and chat rooms backed by Postgres.

Main operations:
```
POST /social/groups/create
POST /social/groups/join
POST /social/groups/leave
GET  /social/groups/{group_id}/members
GET  /social/groups/my_groups
```

Group chat:
```
GET  /social/groups/{group_id}/messages
POST /social/groups/message
```

Messages include:
- sender name
- role (user/assistant)
- content
- timestamp

Rendered via `ui_chat.py`.

## AI Planning Chat
A separate personal chat experience on the home page (`ui_home.py`):

```
POST /chat
```

Used for:
- Trail suggestions
- Weather summaries
- Gear suggestions
- Safety tips

## Weather System
Weather is fetched via the Open-Meteo API (no key needed).  
Results are cached for 1 hour and include:

- temperature
- precipitation probability
- basic safety hints (rain / storm / fire-risk)

---

Future milestones will include richer group management, improved real-time chat, smarter packing checklists, and enhanced AI-assisted trip planning.
