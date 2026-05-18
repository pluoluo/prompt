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


def load_templates() -> List[Dict[str, Any]]:
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_templates(templates: List[Dict[str, Any]]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


class MatchRequest(BaseModel):
    user_input: str
    history: Optional[List[Dict[str, str]]] = None
    template_ref: Optional[Dict[str, Any]] = None


class SubmitRequest(BaseModel):
    title: str
    prompt: str
    category: str
    styles: List[str] = []
    scenes: List[str] = []
    description: str = ""


class UpdateRequest(BaseModel):
    title: Optional[str] = None
    prompt: Optional[str] = None
    category: Optional[str] = None
    styles: Optional[List[str]] = None
    scenes: Optional[List[str]] = None
    description: Optional[str] = None


@app.get("/api/templates")
def get_templates(category: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    templates = load_templates()
    if category:
        templates = [t for t in templates if t.get("category") == category]
    return templates


@app.get("/api/templates/{template_id}")
def get_template(template_id: int) -> Dict[str, Any]:
    templates = load_templates()
    for i, t in enumerate(templates):
        if t.get("id") == template_id:
            return t
    raise HTTPException(status_code=404, detail="Template not found")


@app.put("/api/templates/{template_id}")
def update_template(template_id: int, request: UpdateRequest) -> Dict[str, Any]:
    templates = load_templates()
    for i, t in enumerate(templates):
        if t.get("id") == template_id:
            update_data = request.dict(exclude_unset=True)
            templates[i].update(update_data)
            save_templates(templates)
            return templates[i]
    raise HTTPException(status_code=404, detail="Template not found")


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: int) -> Dict[str, Any]:
    templates = load_templates()
    for i, t in enumerate(templates):
        if t.get("id") == template_id:
            del templates[i]
            save_templates(templates)
            return {"status": "deleted", "id": template_id}
    raise HTTPException(status_code=404, detail="Template not found")


@app.post("/api/match")
async def match_template(request: MatchRequest) -> Dict[str, Any]:
    from backend.matching import match_prompt
    
    templates = load_templates()
    categories = list(set(t.get("category", "Other") for t in templates))
    
    try:
        result = await match_prompt(
            request.user_input, templates, categories,
            history=request.history,
            template_ref=request.template_ref
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/templates/submit")
def submit_template(request: SubmitRequest) -> Dict[str, Any]:
    templates = load_templates()
    new_id = max([t.get("id", 0) for t in templates], default=0) + 1

    new_template = {
        "id": new_id,
        "title": request.title,
        "prompt": request.prompt,
        "category": request.category,
        "styles": request.styles,
        "scenes": request.scenes,
        "description": request.description
    }

    templates.append(new_template)
    save_templates(templates)

    return {"status": "success", "template": new_template}


@app.get("/api/categories")
def get_categories() -> List[str]:
    templates = load_templates()
    categories = sorted(set(t.get("category", "Other") for t in templates))
    return categories


@app.get("/api/config")
def get_config() -> Dict[str, str]:
    """Return public config values to frontend."""
    return {
        "image_api_url": os.getenv("IMAGE_API_URL", "http://localhost:8766")
    }


@app.get("/api/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "prompt-portal"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8768)
