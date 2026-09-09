# Candidate Search AI Agent

This project is a **candidate-search agent**: a conversational system that turns natural-language recruiter requests into structured search actions, runs filters/RAG against a candidate backend, and returns HTML summaries of matching profiles.

---

## High-level overview

Prompts live under `system_prompts/`. The agent currently uses **`system_promptV2.py`** (`prompt`), imported by `api.py`.

The **main agent loop** is in `api.py` (`/agent/{session_id}/ask` and `/agent/{session_id}/ask-stream`). That loop:

1. Loads session state from Redis
2. Builds a system prompt (V2 + current states + conversation)
3. Calls the LLM via `agent.py` (`Agent.call`)
4. Interprets the returned JSON `action`
5. Runs backend/util work when needed (filter, RAG, profile fetch, rollback, resize)
6. Feeds tool results back into the LLM until a **terminal** action is reached
7. Persists updated state to Redis and returns the final output (optionally as SSE)

The LLM never talks to the database directly. It only emits JSON actions. The Python loop executes those actions and decides what to send back on the next turn.

---

## What the agent does

The agent helps users:

- Search candidates with structured filters (title, company, degree, industry, etc.)
- Add semantic / work-experience requirements via resume-bullet RAG
- Rank or compare a small set of displayed candidates
- Resize the displayed window of results
- Roll back to a previous search version
- Answer clarifications, rejections, filter summaries, and light general-knowledge questions

Typical happy path:

```text
User: "Find backend engineers with cloud experience"
  → FILTER  (filters + resume_bullets)
  → backend filter + RAG + scoring
  → LLM called again with candidate profiles
  → SUMMARIZE  (overall summary + per-candidate cards as HTML)
```

---

## Prompts (`system_prompts/`)

| File | Role |
|------|------|
| `system_promptV2.py` | **Active** prompt used by the API |
| `system_promptV1.py` | Earlier version (not wired into the current API loop) |

V2 instructs the model to:

- Return **exactly one JSON object** per call
- Choose **one** supported action
- Use `SearchState`, `DisplayState`, conversation history, and in-loop tool results as context
- Prefer a concrete action over `CLARIFY` when intent is clear
- Put user-facing content in an `html` field for terminal replies

On every request, `api.py` appends live session data to that prompt:

- Current `SearchState`
- Current `ResultState`
- Current `DisplayState`
- Recent conversation history (up to 100 messages)

Within a single user turn, `Agent` also keeps an in-memory loop history (`current_loop_history`) so multi-step sequences (e.g. FILTER → SUMMARIZE) share context for that turn.

---

## Core loop (`api.py` + `agent.py`)

### Session bootstrap

`get_or_create_session(session_id, user_message)` loads or initializes Redis state, appends the user message to conversation history, and returns:

`(search_state, result_state, display_state, conversation, current_version)`

### LLM call

`Agent.call(message)` sends:

- system prompt (V2 + session snapshot)
- current loop messages

and expects a JSON object with an `action` field.

### Terminal vs non-terminal actions

The loop continues until the action is terminal (or max iterations, currently 6):

**Terminal** (stop loop, return to client):

- `SUMMARIZE`
- `CLARIFY`
- `REJECT`
- `ROLLBACK_OUT_OF_SCOPE`
- `RANK_COMPARE_DENIED`
- `GENERAL-KNOWLEDGE`

**Non-terminal** (backend work, then call LLM again):

- `FILTER`
- `ROLLBACK`
- `RANK`
- `COMPARE`
- `RESIZE`

After the loop, `update_redis_states(...)` persists any new search/result/display state and appends an assistant conversation entry.

Streaming variant (`ask-stream`) yields SSE progress events during non-terminal steps, then a final event with the output payload.

---

## State models (`models.py`)

### `Chunk` / `ChunkWithKeyword`

RAG hits from work-experience search:

- `content_id`, `distance`, `content`
- `work_experience_id`, `personal_id`
- `keyword` (on `ChunkWithKeyword`) — which resume-bullet query produced the chunk

### `SearchState`

The active search criteria for a session version:

| Field | Meaning |
|-------|---------|
| `session_id` | Session id |
| `filters` | Structured filters (ids, name, titles, companies, etc.) |
| `resume_bullets` | Semantic experience keywords (AND’d together) |
| `keyword_weight` | Optional weights for those keywords (default 1.0) |

`FILTER` outputs a **full replacement** SearchState (start from current, apply user changes), not a patch.

Allowed filter fields (from the prompt):  
`ids`, `name`, `phone_number`, `email`, `highest_degree`, `industry`, `add_by`, `current_company`, `all_companies`, `current_title`, `all_titles`.

Nested filters (`all_titles`, `all_companies`, `industry`): values in the **same** inner list are OR; **separate** inner lists are AND.

### `ResultState`

Full ranked result set after filter + optional RAG:

| Field | Meaning |
|-------|---------|
| `candidate_ids` | Matching candidate ids (ranked when scored) |
| `resume_bullet_chunks` | `candidate_id → keyword → [ChunkWithKeyword]` |
| `candidate_score` | Score per candidate |
| `keyword_weight` | Weights used for scoring |

### `DisplayState`

What the UI / agent treats as “currently shown”:

| Field | Meaning |
|-------|---------|
| `total_match_count` | Size of the result set |
| `candidate_ids_sorted` | Ordered ids (same ranking as results) |
| `display_window` | `[start, end)` slice currently displayed (default `(0, 10)`, max width 20) |

Display is a view over `ResultState`. `RESIZE` changes only `display_window`.

---

## Actions (from V2 + loop behavior)

### `FILTER`

User adds/changes search requirements.

**LLM output:** `{ action, filters, resume_bullets, keyword_weight }`

**Backend:**

1. `filter_and_rank(filters)` → candidate id list from structured filters  
2. `get_rag_results(ids, resume_bullets, keyword_weight)` → chunks, scores, re-ranked ids  
3. Build new `SearchState` / `ResultState` / `DisplayState`  
4. Bump search version (unless this FILTER follows a rollback restore)  
5. `generate_display_profiles` for the first window (e.g. top 10)  
6. Call LLM again with `{ new_display_state, candidate_profiles }` → expect `SUMMARIZE`

### `ROLLBACK` / `ROLLBACK_OUT_OF_SCOPE`

User asks to restore an earlier search.

**LLM output:** `{ action: "ROLLBACK", version: N }` or out-of-scope terminal message/html.

**Backend (`ROLLBACK`):**

1. Load `agent:{session_id}:search:v{N}` from Redis  
2. Feed restored SearchState back to the LLM  
3. LLM should emit `FILTER` with those criteria unchanged  
4. Version pointer moves to `N` without creating a new version until a later real filter change

### `RANK`

Reorder currently displayed candidates by a **structured profile field** (name, company, degree, etc.). Does **not** change SearchState.

**LLM output:** `{ action: "RANK", field, profiles: [ids...] }`

**Backend:** fetch profiles via `generate_display_profiles`, call LLM again → `SUMMARIZE` (reordered).

Semantic “rank by cloud experience” is **not** RANK — use `FILTER` + `keyword_weight`.

### `COMPARE`

Compare a small subset of displayed candidates.

**LLM output:** `{ action: "COMPARE", profiles: [ids...], message }`

**Backend:** fetch profiles, call LLM again → `SUMMARIZE` comparison HTML.

### `RANK_COMPARE_DENIED`

Terminal denial when no candidates are displayed, the subset is too large, or the criterion is unsupported.

### `RESIZE`

Change `display_window` only (e.g. “show next 10”). Max window size 20; invalid windows → `REJECT`.

**Backend:** slice `candidate_ids_sorted`, fetch profiles for the new window, call LLM again → `SUMMARIZE`.

### `SUMMARIZE`

Terminal user-facing result after FILTER / RANK / COMPARE, or when summarizing current filters / chat history.

Includes `overall_summary`, optional `results[]`, and an `html` payload for the frontend.

### `CLARIFY`

Ambiguous requests, greetings, or chit-chat. Terminal. Returns `message` + `html`.

### `REJECT`

Unsupported / out-of-capability / constraint violation. Terminal.

### `GENERAL-KNOWLEDGE`

Non-search factual questions. Terminal. Returns `message` + `html`.

---

## Memory & Redis state management

State is keyed by `session_id`. Sessions TTL-refresh on use (1 day).

### Versioned search history

| Key | Value |
|-----|--------|
| `agent:{session_id}:current_version` | Active SearchState version |
| `agent:{session_id}:latest_version` | Highest version ever created |
| `agent:{session_id}:search:v{N}` | Serialized `SearchState` for version N |

New successful FILTERs (not rollback restores) increment `latest_version` and write a new `search:v{N}`.

### Non-versioned “latest” snapshots

| Key | Value |
|-----|--------|
| `agent:{session_id}:result` | Latest `ResultState` |
| `agent:{session_id}:display` | Latest `DisplayState` |
| `agent:{session_id}:conversation` | List of `{ role, message, version }` |

Conversation stores the SearchState **version active at that message**, enabling rollback resolution from chat context. Only the last ~100 messages are injected into the prompt.

### Write path

`update_redis_states`:

- Optionally overwrites result/display
- Updates `latest_version` / `current_version` pointers
- Appends an assistant conversation row
- Writes `search:v{current}` only when `new_search_state` exists **and** `current_version == latest_version` (skips writing a “new” search blob on pure rollback pointer moves)

### In-turn memory

`Agent.current_loop_history` holds the multi-step dialogue for the **current request only** (user tool payloads + model JSON). It is not the Redis conversation log.

---

## How data is passed around

```text
Browser
  → POST /agent/{session_id}/ask[-stream]  { query }
  → get_or_create_session (Redis)
  → system prompt = V2 + Search/Result/Display + conversation
  → Agent.call(user_message | tool_result_dict)
       ← JSON action
  → utils / external APIs (filter, RAG, profiles)
  → next Agent.call with structured tool result
  → ... until terminal action
  → update_redis_states
  → JSON or SSE { type: progress|final, output }
  → frontend renders output.html
```

Important shapes:

- **Into the model (system):** states + conversation  
- **Into the model (loop user turns):** either the raw user string or JSON tool results such as:
  - `{ new_display_state, candidate_profiles }` after FILTER / RESIZE  
  - `{ candidate_profiles }` after RANK / COMPARE  
  - `{ rollback_search_state }` after ROLLBACK  
- **Out of the model:** one action JSON object  
- **Out to the client:** terminal `output` (often including `html`)

`candidate_profiles` from `generate_display_profiles` look like:

```text
[
  {
    "basic_info": { ...profile fields... },
    "relevant_chunks": { keyword: [chunk dicts...] }
  },
  ...
]
```

ordered to match the requested id list.

---

## Utility functions (`utils/`)

### `get_or_create_session.py`

- Creates empty Search/Result/Display at version `0` for new sessions  
- Or loads current versioned search + latest result/display  
- Appends the user message to Redis conversation  
- Refreshes TTLs  
- Returns states + conversation + `current_version`

### `update_redis_states.py`

Persists end-of-turn state changes and assistant conversation notes (see Memory section).

### `filter_and_rank.py`

Executes structured filters against `http://localhost:8080/agents/filter`.

- Maps Python filter names to API DTO fields  
- Intersects simple filters  
- Expands nested lists (`industry`, `all_companies`, `all_titles`) as AND-of-OR groups via multiple API calls  
- Handles `current_company` / `current_title` vs `all_*` via status flags  
- Returns a flat `list[int]` of candidate ids (no semantic ranking yet)

### `rag_results.py`

Runs semantic work-experience search against `http://localhost:8080/agents/rag/work-experiences`.

- For each `resume_bullet` keyword, queries RAG restricted to current ids  
- Keeps top chunks per keyword per candidate  
- Scores candidates from chunk distances × `keyword_weight`  
- Re-ranks ids by score  
- If there are no resume bullets, returns the filtered ids unchanged

### `get_candidate_info.py`

Fetches basic profile records for a list of ids from  
`http://localhost:8080/agents/candidate-basic-info`.

### `generate_display_profiles.py`

Joins `get_candidate_info` with RAG chunks into ordered display payloads for the LLM (and ultimately summarization).

---

## External dependencies

The agent loop assumes a local candidate service on port **8080** for:

- Filtering  
- Work-experience RAG  
- Basic candidate info  

Redis (via `REDIS_URL`) stores all session memory. OpenAI (via env vars in `agent.py`) powers each `Agent.call`.

---

## Frontend (brief)

The `frontend/` app is a chat UI that posts to `ask-stream`, shows a loading spinner while waiting, and renders the final `html` from the agent output. Session id and chat HTML are kept in `localStorage` for reload continuity; Redis remains the source of truth for search versions and agent memory.
