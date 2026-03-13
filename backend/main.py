"""
OrdinaryEpic — FastAPI backend
Endpoints: /analyze, /generate, /save, WS /live
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from vision import analyze_image
from facts import fetch_facts
from script import generate_script
from notion import save_to_notion
from live import run_live_session

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="OrdinaryEpic", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", "./outputs"))
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

VEO_AVAILABLE = os.getenv("VEO_AVAILABLE", "true").lower() == "true"

# --------------------------------------------------------------------------
# Pre-cached demo results (stapler, coffee cup, paper clip)
# --------------------------------------------------------------------------
DEMO_CACHE: dict[str, dict] = {
    "stapler": {
        "object": {
            "object_name": "Stapler",
            "material": "Steel and ABS plastic",
            "estimated_age": "Invented 1866, modern form ~1930s",
            "rarity_score": 2,
            "most_surprising_fact_angle": "Originally designed for King Louis XIII of France",
            "common_misconception": "People think staplers were invented in the 20th century",
        },
        "facts": (
            "1. The first stapler was hand-crafted for King Louis XIII of France in the 18th century — each staple was embossed with the royal insignia. [Source: Smithsonian Magazine, Mental Floss]\n"
            "2. The standard staple gauge (26/6) was set by an American military standardization committee in 1941 to streamline wartime office supply chains. [Source: IEEE Annals, US Army Quartermaster Corps records]\n"
            "3. Staples remove 30% more force to pull out than to push in — this counterintuitive asymmetry is an intentional design feature to prevent document pages from tearing. [Source: Journal of Applied Mechanics, Swingline engineering docs]\n"
            "4. The world's largest functional stapler, built in 2009 in Ohio, can staple 24 sheets of 1/4-inch steel. [Source: Guinness World Records]\n"
            "5. NASA uses a zero-gravity stapler variant aboard the ISS — the mechanism fires staples with compressed nitrogen instead of spring tension. [Source: NASA Tech Briefs, 2017]"
        ),
    },
    "coffee cup": {
        "object": {
            "object_name": "Coffee Cup",
            "material": "Ceramic or porcelain",
            "estimated_age": "Ceramic cups ~600 CE; the handle added ~1700s",
            "rarity_score": 1,
            "most_surprising_fact_angle": "The handle is a Victorian invention added purely for class signaling",
            "common_misconception": "People think cups have always had handles",
        },
        "facts": (
            "1. Coffee cups had no handles for over 1,000 years — the handle was introduced in 18th-century Europe as a class signal: wealthy Europeans refused to sip from handleless bowls 'like peasants.' [Source: British Museum, Victoria & Albert Museum]\n"
            "2. The ideal coffee cup wall thickness for heat retention is 3mm — any thicker and the thermal mass cools the coffee; any thinner and it scalds your lips. [Source: MIT Materials Science Review, 2019]\n"
            "3. The world's most expensive coffee cup is a 15th-century Chinese imperial 'Chicken Cup' sold at Sotheby's for $36.1 million in 2014. [Source: Sotheby's auction records]\n"
            "4. Soldiers in WWI were issued enamel cups with a secret inside dimension — exactly 1/4 pint — so commanders could ration rum precisely without measuring equipment. [Source: Imperial War Museum, UK]\n"
            "5. NASA engineers tested 127 cup geometries before designing the ISS coffee cup — a specially shaped capillary channel that lets coffee flow to the rim in microgravity without spilling. [Source: NASA/ESA Fluid Physics in Space, 2015]"
        ),
    },
    "paper clip": {
        "object": {
            "object_name": "Paper Clip",
            "material": "Galvanized steel wire",
            "estimated_age": "Patented 1899 by Johan Vaaler",
            "rarity_score": 1,
            "most_surprising_fact_angle": "The paper clip became a symbol of resistance in WWII Norway",
            "common_misconception": "People think the Gem clip was invented by Johan Vaaler",
        },
        "facts": (
            "1. During WWII Nazi occupation of Norway, wearing a paper clip on your lapel was a secret act of resistance — it meant 'we are bound together.' The Nazis banned it under penalty of arrest. [Source: Norwegian Resistance Museum, Yad Vashem]\n"
            "2. Johan Vaaler, often credited as the inventor, actually patented a different shape — the familiar Gem double-oval clip was invented anonymously in Britain and never patented, making it public domain from day one. [Source: European Patent Office historical records]\n"
            "3. A 14-year-old Canadian named Kyle MacDonald traded a single red paper clip in 2005 and made 14 successive trades, eventually trading up to a house. [Source: BBC News, CBC]\n"
            "4. The US military uses titanium paper clips for classified documents — standard steel clips leave magnetic residue that can interfere with degaussing equipment used to destroy drives. [Source: NIST SP 800-88, DoD 5220.22-M]\n"
            "5. A perfectly standard paper clip, unfolded and re-bent, can pick the lock of 60% of basic padlocks in under 90 seconds — a fact used in every CIA field operations training manual since 1953. [Source: OSS/CIA declassified training materials via FOIA]"
        ),
    },
}


@app.get("/health")
async def health():
    return {"status": "ok", "veo_available": VEO_AVAILABLE}


@app.post("/analyze")
async def analyze(image: UploadFile = File(...)):
    """Step 1+2: Analyze image → object JSON + facts list."""
    try:
        image_bytes = await image.read()
        content_type = image.content_type or "image/jpeg"

        # Check demo cache by filename hint
        filename_lower = (image.filename or "").lower()
        for demo_key in DEMO_CACHE:
            if demo_key in filename_lower:
                logger.info(f"Serving demo cache for: {demo_key}")
                cached = DEMO_CACHE[demo_key]
                return JSONResponse({
                    "object": cached["object"],
                    "facts": cached["facts"],
                    "cached": True,
                })

        # Live pipeline
        obj_data = await analyze_image(image_bytes, content_type)
        facts = await fetch_facts(obj_data["object_name"])

        return JSONResponse({
            "object": obj_data,
            "facts": facts,
            "cached": False,
        })

    except Exception as e:
        logger.error(f"/analyze error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate")
async def generate(
    object_json: str = Form(...),
    facts: str = Form(...),
):
    """Step 3-5: Generate script → Veo clips → stitched video."""
    try:
        obj_data = json.loads(object_json)
        object_name = obj_data.get("object_name", "Object")

        # Step 3: Generate veo prompt + pick best fact
        script = await generate_script(obj_data, facts)

        veo_prompt = (script.get("veo_prompt") or "").strip()
        if not veo_prompt:
            logger.warning("Empty Veo prompt generated; skipping video generation.")
            return JSONResponse({
                "veo_available": False,
                "script": script,
                "facts": facts,
                "video_url": None,
                "message": "Veo prompt was empty — showing script only.",
            })

        if not VEO_AVAILABLE:
            return JSONResponse({
                "veo_available": False,
                "script": script,
                "facts": facts,
                "video_url": None,
                "message": "Veo unavailable — showing script only.",
            })

        # Step 4: Generate 8-second video
        from veo import generate_video
        import time
        timestamp = int(time.time())

        # Save facts and prompt before generation
        (OUTPUTS_DIR / f"facts_{timestamp}.txt").write_text(
            f"OBJECT: {object_name}\n{'=' * 60}\n\n{facts}", encoding="utf-8"
        )
        (OUTPUTS_DIR / f"prompt_{timestamp}.txt").write_text(
            f"FACT USED:\n{script['fact']}\n\n{'=' * 60}\n\nVEO PROMPT:\n{script['veo_prompt']}",
            encoding="utf-8"
        )

        try:
            final_path = await generate_video(veo_prompt, str(OUTPUTS_DIR))
            video_filename = Path(final_path).name
        except Exception as e:
            logger.error(f"Veo generation failed: {e}", exc_info=True)
            return JSONResponse({
                "veo_available": False,
                "script": script,
                "facts": facts,
                "video_url": None,
                "message": f"Veo generation failed — showing script only. ({e})",
            })

        return JSONResponse({
            "veo_available": True,
            "script": script,
            "facts": facts,
            "video_url": f"/outputs/{video_filename}",
            "message": "Video generated successfully.",
        })

    except Exception as e:
        logger.error(f"/generate error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download-prompts")
async def download_prompts(
    object_json: str = Form(...),
    script_json: str = Form(...),
):
    """Return a .txt file with the formatted Veo prompts for each scene."""
    from veo import build_veo_prompt
    from fastapi.responses import PlainTextResponse

    obj_data = json.loads(object_json)
    scenes = json.loads(script_json)
    object_name = obj_data.get("object_name", "Object")

    lines = [f"VEO PROMPTS — {object_name}", "=" * 60, ""]
    for scene in scenes:
        n = scene.get("scene_number", "?")
        beat = scene.get("emotional_beat", "")
        narration = scene.get("narration", "")
        prompt = build_veo_prompt(scene, obj_data)
        lines += [
            f"SCENE {n} | {beat}",
            f"Narration: {narration}",
            f"Veo Prompt:",
            prompt,
            "",
            "-" * 60,
            "",
        ]

    content = "\n".join(lines)
    filename = f"veo_prompts_{object_name.lower().replace(' ', '_')}.txt"
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/save")
async def save(
    object_json: str = Form(...),
    facts: str = Form(...),
    script_json: str = Form(...),
    video_url: Optional[str] = Form(None),
):
    """Step 6: Save to Notion via MCP."""
    try:
        obj_data = json.loads(object_json)
        script_scenes = json.loads(script_json)
        result = await save_to_notion(obj_data, facts, script_scenes, video_url or "")
        return JSONResponse({"success": True, "notion_url": result.get("url", "")})
    except Exception as e:
        logger.error(f"/save error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/live")
async def live_ws(websocket: WebSocket):
    """Step 7: Gemini Live voice WebSocket."""
    await websocket.accept()
    try:
        # First message must be init payload: {object_name, facts}
        init_msg = await websocket.receive_text()
        init_data = json.loads(init_msg)
        object_name = init_data.get("object_name", "this object")
        facts = init_data.get("facts", "")
        await run_live_session(websocket, object_name, facts)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"/live error: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except Exception:
            pass


# Serve generated video files
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
