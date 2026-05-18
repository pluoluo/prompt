import os
import json
import httpx
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Prompt Portal API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = os.path.join(os.path.dirname(__file__), "prompts_data.json")
PENDING_FILE = os.path.join(os.path.dirname(__file__), "pending_review.json")


def load_templates() -> List[Dict[str, Any]]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_pending(pending: List[Dict[str, Any]]) -> None:
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(pending, f, ensure_ascii=False, indent=2)


class MatchRequest(BaseModel):
    user_input: str


class SubmitRequest(BaseModel):
    title: str
    prompt: str
    category: str
    styles: List[str] = []
    scenes: List[str] = []
    description: str = ""


@app.get("/api/templates")
def get_templates(category: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    templates = load_templates()
    if category:
        templates = [t for t in templates if t.get("category") == category]
    return templates


@app.get("/api/templates/{template_id}")
def get_template(template_id: int) -> Dict[str, Any]:
    templates = load_templates()
    for t in templates:
        if t.get("id") == template_id:
            return t
    raise HTTPException(status_code=404, detail="Template not found")


@app.post("/api/match")
async def match_template(request: MatchRequest) -> Dict[str, Any]:
    from matching import match_prompt
    
    templates = load_templates()
    categories = list(set(t.get("category", "Other") for t in templates))
    
    try:
        result = await match_prompt(request.user_input, templates, categories)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/templates/submit")
def submit_template(request: SubmitRequest) -> Dict[str, str]:
    pending = []
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            pending = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    new_id = max([p.get("id", 0) for p in pending], default=0) + 1
    
    new_template = {
        "id": new_id,
        "title": request.title,
        "prompt": request.prompt,
        "category": request.category,
        "styles": request.styles,
        "scenes": request.scenes,
        "description": request.description
    }
    
    pending.append(new_template)
    save_pending(pending)
    
    return {"status": "success", "id": new_id}


@app.get("/api/categories")
def get_categories() -> List[str]:
    templates = load_templates()
    categories = sorted(set(t.get("category", "Other") for t in templates))
    return categories


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8768)
