# Hiking Group Chatbot – Initial Milestone

## 1. Mission & Users
- Provide hiking groups with a domain-aware copilot that can recommend routes, coordinate outings, forecast risks, prep gear, and assist in emergencies.
- Primary personas: trip planners (set agenda), participants (need clarity/logistics), safety leads (monitor conditions), and offline navigators (need GPX + landmarks).

## 2. Feature Breakdown
| Capability | Key Inputs | Deliverables |
| --- | --- | --- |
| Route recommendations | location, distance, elevation gain, rating, drive time, pet/camping/water filters | 3 ranked hikes with justification + quick stats + GPX links |
| Event coordination | preferred date/time, meetup rules, ride capacity | Trip card (time, meetup, GPX, gear, difficulty) + RSVP + carpool buckets |
| Weather & risk alerts | route geo + departure schedule | Pre-trip & en-route snapshots (temp, precip, snowpack, lightning, fire risk, sunset buffer) |
| Gear & supply planner | season, altitude, snow/mud, trip length | Dynamic packing checklist + water/calorie estimate |
| Tracks & offline helpers | uploaded GPX, map snippets | Store GPX, allow downloads, annotate critical junctions with text cues |
| Safety assistant | roster, coordinates, ranger contacts | SOS card (contacts, ranger station, AT&T/Verizon coverage notes) + “missing hiker countdown” reminders |

## 3. Architecture (proposed)
1. **Gateway/API** (FastAPI) – exposes REST + websocket for chat, handles auth, rate limits.
2. **Conversation Orchestrator** – maintains session state, prompt templates, tool calling to domain micro-services, optionally backed by Redis for short-term memory.
3. **Domain Services**:
   - Route Intelligence (query Postgres/PostGIS + scoring engine)
   - Event Planner (RSVP + carpool assignments)
   - Weather/Risk (integrates with NOAA/VisualCrossing; caches forecasts)
   - Gear Engine (rule-based + LLM refinement)
   - Safety Module (SOS cards, countdown scheduler)
4. **Data layer** – Postgres (routes, events, rosters, gear templates), S3-compatible object store for GPX/maps, Redis for ephemeral state/locks.
5. **LLM Provider** – OpenAI GPT-4o (initial) with tool-calling; local fallback via Llama.cpp later.
6. **Workers & schedulers** – Celery/Arq for async jobs (weather polling, countdown timers).
7. **Infra** – Docker Compose for local dev, separate containers for API, worker, Postgres, Redis, MinIO.

## 4. Data Contracts (draft)
- `routes`: id, name, coords (LineString), distance_km, elevation_gain_m, difficulty, drive_time_min, tags (pet_friendly, camping, water), GPX path.
- `events`: id, route_id, start_dt, meetup_point, organizer, difficulty_override, gpx_url.
- `signups`: id, event_id, user, seats_needed, driver_flag, vehicle_capacity, notes.
- `weather_snapshots`: event_id, forecast_ts, temp_c, precip_prob, lightning_risk, fire_risk, advisory_text.
- `gear_profiles`: season, altitude_band, terrain_flags, checklist_items (JSONB).
- `sos_cards`: event_id, ranger_station, emergency_numbers, last_check_in, countdown_minutes.

## 5. Initial Milestone (Week 1) Scope
1. **Project skeleton**
   - FastAPI app with `/chat`, `/routes`, `/events` endpoints (mock data responses).
   - Docker Compose stack: api, worker (placeholder), postgres, redis.
2. **Route recommendation prototype**
   - Static seed dataset (YAML/JSON) + scoring logic honoring filters (distance, gain, difficulty, drive time, tags).
   - Prompt template tying recommendations + rationale into chat response.
3. **Event card generator**
   - Domain schema for trips and RSVPs.
   - Endpoint to create “trip card” JSON + text block; auto-populate from route + inputs.
4. **Weather/risk + gear stubs**
   - Mock service that returns deterministic weather + reminders given lat/lon & time.
   - Rule-based packing checklist + hydration/calorie estimator.
5. **Safety scaffolding**
   - SOS card data model + endpoint.
   - Countdown scheduler stub (in-memory timer hook, log reminders).
6. **Testing & docs**
   - Unit tests for route scoring + gear calculator.
   - README updates: setup, docker commands, API contract, prompt conventions.

## 6. Next Milestones (preview)
- **M2 (Integrations)**: connect real weather API, import GPX parser, add storage, real RSVP persistence, Slack/Discord webhook.
- **M3 (Intelligence)**: integrate live LLM with tool calling, build offline map artifact generator, implement safety countdown worker + notifications.
- **M4 (Polish & Deploy)**: auth, role mgmt, full UI/portal, monitoring, deploy to cloud environment.

## 7. Risks & Mitigations
- Weather API limits → cache & degrade gracefully to last-known data.
- LLM hallucinations → constrain via tool outputs + guardrails.
- Data freshness (route info) → allow manual overrides + versioning.
- Offline support complexity → start with static snapshots + doc generation before vector maps.

This document defines the concrete engineering targets for the initial milestone so we can start coding immediately while keeping the long-term roadmap visible.
