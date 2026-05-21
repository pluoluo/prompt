import os
import json
import time
import hmac
import hashlib
import base64
import httpx
from dotenv import load_dotenv
load_dotenv()
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query, UploadFile, File as FastAPIFile, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path

app = FastAPI(title="Prompt Portal API")

# Mount local gallery images
GALLERY_IMAGES_DIR = Path(__file__).parent / "data" / "gallery_images"
GALLERY_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/gallery/images", StaticFiles(directory=str(GALLERY_IMAGES_DIR)), name="gallery_images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth ─────────────────────────────────────────────────
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "admin123")
AUTH_SECRET = os.getenv("AUTH_SECRET", os.urandom(32).hex())
TOKEN_TTL = 86400  # 24 hours

def _sign(data: str) -> str:
    return hmac.new(AUTH_SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()

def create_token(username: str) -> str:
    exp = int(time.time()) + TOKEN_TTL
    payload = f"{username}:{exp}"
    sig = _sign(payload)
    token = base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()
    return token

def verify_token(token: str) -> Optional[str]:
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.rsplit(":", 1)
        if len(parts) != 2:
            return None
        payload, sig = parts
        if not hmac.compare_digest(_sign(payload), sig):
            return None
        username, exp_str = payload.split(":", 1)
        if int(exp_str) < time.time():
            return None
        return username
    except Exception:
        return None

def require_auth(authorization: Optional[str] = Header(None)) -> str:
    if not AUTH_PASSWORD or AUTH_PASSWORD == "admin123":
        return "admin"  # No auth configured — allow all
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    username = verify_token(authorization[7:])
    if not username:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return username

class LoginRequest(BaseModel):
    username: str
    password: str

# ── Data ─────────────────────────────────────────────────
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


@app.post("/api/auth/login")
def login(request: LoginRequest) -> Dict[str, Any]:
    if request.password != AUTH_PASSWORD:
        raise HTTPException(status_code=401, detail="密码错误")
    token = create_token(request.username or "admin")
    return {"token": token, "username": request.username or "admin"}

@app.get("/api/auth/check")
def check_auth(username: str = Depends(require_auth)) -> Dict[str, str]:
    return {"username": username}


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
def update_template(template_id: int, request: UpdateRequest, username: str = Depends(require_auth)) -> Dict[str, Any]:
    templates = load_templates()
    for i, t in enumerate(templates):
        if t.get("id") == template_id:
            update_data = request.dict(exclude_unset=True)
            templates[i].update(update_data)
            save_templates(templates)
            return templates[i]
    raise HTTPException(status_code=404, detail="Template not found")


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: int, username: str = Depends(require_auth)) -> Dict[str, Any]:
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
def submit_template(request: SubmitRequest, username: str = Depends(require_auth)) -> Dict[str, Any]:
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


# ── Gallery ──────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"

@app.get("/api/gallery")
def get_gallery():
    """
    Return all gallery cases from local cached data.
    """
    gallery_file = DATA_DIR / "gallery_data.json"
    if not gallery_file.exists():
        return {
            "source": "https://github.com/freestylefly/awesome-gpt-image-2",
            "total": 0,
            "cases": [],
            "error": "Gallery data not found. Click 'Sync' to fetch."
        }
    with open(gallery_file, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/gallery/translations")
def get_gallery_translations():
    """
    Return Chinese translations for gallery cases.
    Maps caseId -> {title, category, prompt}.
    """
    translations_file = DATA_DIR / "gallery_translations.json"
    if not translations_file.exists():
        return {}
    with open(translations_file, encoding="utf-8") as f:
        return json.load(f)


NEW_REPO_RAW = "https://raw.githubusercontent.com/freestylefly/awesome-gpt-image-2/main"


@app.post("/api/gallery/sync")
async def sync_gallery(username: str = Depends(require_auth)):
    """
    Sync gallery data from the upstream GitHub repo (freestylefly/awesome-gpt-image-2).
    Fetches cases.json and downloads images.
    """
    from datetime import datetime, timezone

    async with httpx.AsyncClient(timeout=120.0) as client:
        # 1. Fetch cases.json
        cases_url = f"{NEW_REPO_RAW}/data/cases.json"
        cases_res = await client.get(cases_url)
        if cases_res.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to fetch cases.json: HTTP {cases_res.status_code}")
        data = cases_res.json()
        cases = data.get("cases", [])

        # 2. Load existing local data to know which IDs we already have
        gallery_path = DATA_DIR / "gallery_data.json"
        old_ids = set()
        if gallery_path.exists():
            with open(gallery_path, encoding="utf-8") as f:
                old_data = json.load(f)
            old_ids = {c["id"] for c in old_data.get("cases", []) if "id" in c}

        # 3. Download images only for new cases
        images_dir = GALLERY_IMAGES_DIR
        images_dir.mkdir(parents=True, exist_ok=True)
        downloaded = 0
        new_cases = []
        for case in cases:
            case_id = case.get("id")
            if not case_id:
                continue
            if case_id in old_ids:
                continue  # Skip existing cases
            new_cases.append(case)
            # Download image for new case
            image_path = case.get("image", f"/images/case{case_id}.jpg")
            ext = image_path.rsplit(".", 1)[-1] if "." in image_path else "jpg"
            img_path = images_dir / f"case{case_id}.{ext}"
            if img_path.exists():
                continue
            try:
                img_url = f"{NEW_REPO_RAW}/data/images/case{case_id}.{ext}"
                img_res = await client.get(img_url, timeout=30.0)
                if img_res.status_code == 200:
                    img_path.write_bytes(img_res.content)
                    downloaded += 1
                else:
                    # Fallback: try jpg
                    img_url2 = f"{NEW_REPO_RAW}/data/images/case{case_id}.jpg"
                    img_res2 = await client.get(img_url2, timeout=30.0)
                    if img_res2.status_code == 200:
                        (images_dir / f"case{case_id}.jpg").write_bytes(img_res2.content)
                        downloaded += 1
            except Exception:
                continue

        # 4. Merge: keep existing cases + add new ones
        old_cases = old_data.get("cases", []) if gallery_path.exists() else []

        merged = old_cases + new_cases

        result = {
            "source": "https://github.com/freestylefly/awesome-gpt-image-2",
            "total": len(merged),
            "categories": data.get("categories", []),
            "styles": data.get("styles", []),
            "scenes": data.get("scenes", []),
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "cases": merged,
        }

        with open(gallery_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "total": len(merged),
        "added": len(new_cases),
        "removed": 0,
        "images_downloaded": downloaded,
        "last_synced": result["last_synced"],
    }


@app.post("/api/gallery/upload")
async def upload_gallery_image(file: UploadFile = FastAPIFile(...)):
    """
    Upload an image for a gallery case. Saves to gallery_images/uploads/.
    Returns the relative URL path to the uploaded image.
    """
    import uuid
    upload_dir = GALLERY_IMAGES_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = upload_dir / safe_name
    content = await file.read()
    file_path.write_bytes(content)
    return {
        "ok": True,
        "url": f"/api/gallery/images/uploads/{safe_name}",
        "filename": safe_name,
    }


@app.put("/api/gallery/cases/{case_id}")
def update_gallery_case(case_id: int, request: UpdateRequest, username: str = Depends(require_auth)):
    """Update a gallery case and persist to gallery_data.json."""
    gallery_file = DATA_DIR / "gallery_data.json"
    if not gallery_file.exists():
        raise HTTPException(status_code=404, detail="Gallery data not found")
    with open(gallery_file, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])
    for i, c in enumerate(cases):
        if c.get("id") == case_id:
            update_data = request.dict(exclude_unset=True)
            cases[i].update(update_data)
            data["cases"] = cases
            with open(gallery_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return cases[i]
    raise HTTPException(status_code=404, detail="Case not found")


@app.delete("/api/gallery/cases/{case_id}")
def delete_gallery_case(case_id: int, username: str = Depends(require_auth)):
    """Delete a gallery case and persist."""
    gallery_file = DATA_DIR / "gallery_data.json"
    if not gallery_file.exists():
        raise HTTPException(status_code=404, detail="Gallery data not found")
    with open(gallery_file, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])
    for i, c in enumerate(cases):
        if c.get("id") == case_id:
            del cases[i]
            data["cases"] = cases
            with open(gallery_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"status": "deleted", "id": case_id}
    raise HTTPException(status_code=404, detail="Case not found")


@app.post("/api/gallery/cases")
def add_gallery_case(request: SubmitRequest, username: str = Depends(require_auth)):
    """Add a new gallery case, reusing vacant IDs when possible."""
    gallery_file = DATA_DIR / "gallery_data.json"
    if not gallery_file.exists():
        raise HTTPException(status_code=404, detail="Gallery data not found")
    with open(gallery_file, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])
    existing_ids = sorted([c.get("id", 0) for c in cases])
    # Find first vacant ID
    new_id = 1
    for eid in existing_ids:
        if eid == new_id:
            new_id += 1
        elif eid > new_id:
            break
    new_case = {
        "id": new_id,
        "title": request.title,
        "prompt": request.prompt,
        "category": request.category,
        "styles": request.styles,
        "scenes": request.scenes,
        "description": request.description,
        "image": f"/images/case{new_id}.jpg",
        "imageAlt": request.title,
        "sourceLabel": "",
        "sourceUrl": "",
        "githubUrl": "",
    }
    cases.append(new_case)
    data["cases"] = cases
    with open(gallery_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"status": "created", "case": new_case}


@app.get("/api/gallery/translations")
def get_gallery_translations():
    """Return pre-generated Chinese translations for gallery cases."""
    trans_file = DATA_DIR / "gallery_translations.json"
    if trans_file.exists():
        with open(trans_file, encoding="utf-8") as f:
            return json.load(f)
    return {}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8768)
