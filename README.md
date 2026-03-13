# StoryLens

> Upload a photo of any everyday object. Get a funny 8-second AI-generated video built around its most surprising fact — powered by Gemini 2.5 Flash, Veo 3.1, and Gemini Live.

---

## What It Does

1. **Vision** — Gemini 2.0 Flash analyzes your photo and identifies the object
2. **Facts** — Gemini 2.0 Flash + Google Search Grounding retrieves 5 surprising, verified facts with citations
3. **Script** — Gemini 2.5 Flash picks the funniest fact and writes a single Veo prompt for an 8-second video
4. **Video** — Veo 3.1 generates an 8-second video via Vertex AI
5. **Save** — Notion API saves the object, facts, script, and video link
6. **Live** — Gemini Live API opens a real-time voice conversation about the object's story

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI · uvicorn |
| Frontend | React 18 · Vite · Tailwind CSS |
| Vision + Facts | Gemini 2.0 Flash (`google-genai` SDK) |
| Script | Gemini 2.5 Flash (`google-genai` SDK) |
| Search Grounding | Gemini native Google Search tool |
| Video Generation | Veo 3.1 via Vertex AI |
| Voice Layer | Gemini Live API (WebSocket) |
| Storage | Notion REST API |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud project with Vertex AI + Veo 3.1 access enabled
- `gcloud` CLI installed and authenticated

---

## Setup

### 1. Clone and configure

```bash
git clone <repo>
cd StoryLens
```

Fill in `.env`:
```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your_project_id
GOOGLE_CLOUD_LOCATION=us-central1
VEO_AVAILABLE=true
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...
```

### 2. Authenticate with Google Cloud

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project your_project_id
gcloud services enable aiplatform.googleapis.com
```

### 3. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

---

## Demo Script

### Instant demo — pre-cached objects

The app has 3 pre-cached objects that return instantly without API calls.
Name your image file with the object name:

| File name | Object |
|---|---|
| `stapler.jpg` | Stapler |
| `coffee_cup.jpg` | Coffee Cup |
| `paper_clip.jpg` | Paper Clip |

### Live demo walkthrough

1. Open `http://localhost:5173`
2. Upload a photo of any everyday object
3. Watch the pipeline run:
   - Identifying object... ✓
   - Fetching surprising facts... ✓
   - Writing script + generating video (5–10 min)... ✓
4. 8-second funny video plays
5. Click "Start voice conversation" and ask questions about the object
6. Click "Save to Notion" to save the result

### Fallback mode (no Veo access)

Set `VEO_AVAILABLE=false` in `.env`. The pipeline runs steps 1–3 and returns the object analysis, 5 verified facts with citations, and the generated Veo prompt — without video generation.

---

## API Reference

### `POST /analyze`

Upload an image, get object metadata + facts.

**Request:** `multipart/form-data` with `image` field

**Response:**
```json
{
  "object": {
    "object_name": "Stapler",
    "material": "Steel and ABS plastic",
    "estimated_age": "1930s",
    "rarity_score": 2,
    "most_surprising_fact_angle": "...",
    "common_misconception": "..."
  },
  "facts": "1. ...\n2. ...",
  "cached": false
}
```

### `POST /generate`

Generate a Veo prompt + 8-second video from analysis results.

**Request:** `multipart/form-data`
- `object_json`: JSON string of object metadata
- `facts`: facts string

**Response:**
```json
{
  "veo_available": true,
  "script": {"veo_prompt": "...", "fact": "..."},
  "facts": "...",
  "video_url": "/outputs/video_1234567890.mp4",
  "message": "Video generated successfully."
}
```

### `POST /save`

Save to Notion.

### `WS /live`

WebSocket for Gemini Live voice session.

**First message from client:**
```json
{"object_name": "Stapler", "facts": "..."}
```

**Audio messages (client → server):**
```json
{"type": "audio", "data": "<base64 PCM 16kHz mono>"}
```

**Audio messages (server → client):**
```json
{"type": "audio", "data": "<base64 PCM 16kHz mono>"}
{"type": "text", "data": "transcript chunk"}
```

---

## Project Structure

```
StoryLens/
├── backend/
│   ├── main.py       FastAPI app — all endpoints + CORS + demo cache
│   ├── vision.py     Gemini Vision → structured object JSON
│   ├── facts.py      Gemini + Google Search Grounding → 5 verified facts
│   ├── script.py     Gemini 2.5 Flash → picks best fact + writes Veo prompt
│   ├── veo.py        Veo 3.1 video generation via Vertex AI
│   ├── notion.py     Notion REST API integration
│   └── live.py       Gemini Live API WebSocket handler
├── frontend/
│   ├── src/
│   │   ├── App.jsx              Main app state machine
│   │   └── components/
│   │       ├── Upload.jsx       Drag-and-drop image upload
│   │       ├── Pipeline.jsx     Real-time pipeline progress UI
│   │       ├── VideoPlayer.jsx  Custom video player
│   │       └── LiveVoice.jsx    Gemini Live voice interface
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── outputs/           Generated video files (gitignored)
├── .env               Environment variables
├── requirements.txt   Python dependencies
└── README.md
```

---

## Troubleshooting

**Vertex AI 403 error**
Run `gcloud services enable aiplatform.googleapis.com --project=your_project_id` and wait ~1 minute.

**Default credentials not found**
Run `gcloud auth application-default login` and `gcloud auth login`.

**Veo model not found / access denied**
Veo 3.1 requires allowlist approval from Google Cloud. Set `VEO_AVAILABLE=false` to run in fallback mode.

**Gemini Live WebSocket fails**
Ensure `google-genai>=0.8.0` is installed.

**Notion pages not saving**
Ensure your Notion integration has been invited to the database. The database must have `Name` (title), `Object` (rich_text), and `Created` (date) properties.
