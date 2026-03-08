# OrdinaryEpic

> Upload a photo of any everyday object. Get a cinematic 50-second documentary about its secret history — generated in real time by Gemini Vision, Veo 3.1, and Gemini Live.

---

## What It Does

1. **Vision** — Gemini 2.0 Flash analyzes your photo and identifies the object
2. **Facts** — Gemini + Google Search Grounding finds 5 surprising, verified facts with citations
3. **Script** — Gemini generates a 5-scene cinematic script following the Myth-Bust-Blow arc
4. **Video** — Veo 3.1 generates 5 × 10-second clips in parallel via Vertex AI
5. **Stitch** — FFmpeg concatenates clips into one 50-second `final_video.mp4`
6. **Save** — Notion MCP saves the object, facts, script, and video link
7. **Live** — Gemini Live API opens a real-time voice conversation with the documentary narrator

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+ · FastAPI · uvicorn |
| Frontend | React 18 · Vite · Tailwind CSS |
| Vision + Facts + Script | Google Gemini 2.0 Flash (`google-genai` SDK) |
| Search Grounding | Gemini native Google Search tool |
| Video Generation | Veo 3.1 via Vertex AI |
| Video Stitching | FFmpeg |
| Voice Layer | Gemini Live API (WebSocket) |
| Storage | Notion REST API |

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- FFmpeg installed (`brew install ffmpeg` on macOS)
- Google API Key with Gemini access ([get one](https://aistudio.google.com/app/apikey))
- Google Cloud project with Vertex AI enabled and **Veo 3.1 access approved**
- Notion integration token + database ID

---

## Setup

### 1. Clone and configure

```bash
git clone <repo>
cd ordinaryepic
cp .env .env.local  # edit .env with your real keys
```

Fill in `.env`:
```env
GOOGLE_API_KEY=your_key
GOOGLE_CLOUD_PROJECT=your_project_id
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...
VEO_AVAILABLE=true   # set false for demo/fallback mode
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`

### 4. Google Cloud authentication (for Veo 3.1)

```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

---

## Demo Script (for judges / live demo)

### Instant demo — pre-cached objects

The app has 3 pre-cached demo objects that return instantly without API calls.
Name your test image file with the object name:

| File name | Object |
|---|---|
| `stapler.jpg` | Stapler |
| `coffee_cup.jpg` | Coffee Cup |
| `paper_clip.jpg` | Paper Clip |

Upload any of these and the pipeline will serve cached results in < 1 second.

### Live demo walkthrough

1. Open `http://localhost:5173`
2. Drag and drop `stapler.jpg` onto the upload zone
3. Watch the pipeline complete in real time:
   - Identifying object... ✓
   - Fetching surprising facts... ✓
   - Writing cinematic script... ✓
   - Generating scenes with Veo 3.1... (1/5, 2/5 ... 5/5)
   - Stitching final video... ✓
4. Video autoplays — 50 seconds of cinematic documentary
5. Below the video: click "Start voice conversation"
6. Ask: *"Why did soldiers use staplers in World War II?"*
7. Gemini Live responds in real time with voice
8. Click "Save to Notion" — opens the Notion page

### Fallback demo (no Veo access)

Set `VEO_AVAILABLE=false` in `.env`. The pipeline runs steps 1-3 and returns:
- Full object analysis JSON
- 5 verified facts with citations
- Complete 5-scene script with shot descriptions

This demonstrates the full intelligence pipeline without video generation.

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

Generate script + video from analysis results.

**Request:** `multipart/form-data`
- `object_json`: JSON string of object metadata
- `facts`: facts string

**Response:**
```json
{
  "veo_available": true,
  "script": [...],
  "video_url": "/outputs/final_video_1234567890.mp4",
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

## Narrative Arc: Myth-Bust-Blow

Every generated script follows this 5-beat structure:

| Scene | Beat | Purpose |
|---|---|---|
| 1 | `false_familiarity` | Start with the ordinary — what everyone thinks they know |
| 2 | `misconception` | Expose the common misconception |
| 3 | `tension` | Build suspense, hint at the reveal |
| 4 | `reveal` | The most surprising verified fact — most dramatic moment |
| 5 | `reframe` | Change how we see the object forever; end with one unanswered question |

---

## Project Structure

```
ordinaryepic/
├── backend/
│   ├── main.py       FastAPI app — all endpoints + CORS + demo cache
│   ├── vision.py     Gemini Vision → structured object JSON
│   ├── facts.py      Gemini + Google Search Grounding → 5 verified facts
│   ├── script.py     Gemini → 5-scene Myth-Bust-Blow script JSON
│   ├── veo.py        Veo 3.1 prompt builder + parallel video generation
│   ├── stitch.py     FFmpeg clip concatenation
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
├── .env               Environment variables (fill this in)
├── requirements.txt   Python dependencies
└── README.md
```

---

## Troubleshooting

**Veo 3.1 access denied**
Set `VEO_AVAILABLE=false` to use fallback mode. Veo access requires allowlisting via Google Cloud.

**Gemini Live WebSocket fails**
The Live API requires `v1alpha`. Ensure `google-genai>=0.8.0` is installed.

**FFmpeg not found**
Install FFmpeg: `brew install ffmpeg` (macOS) or `apt install ffmpeg` (Ubuntu)

**Notion pages not saving**
Ensure your Notion integration has been invited to the database. The database must have a `Name` (title) property, an `Object` (rich_text) property, and a `Created` (date) property.
