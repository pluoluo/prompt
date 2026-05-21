"""Download all gallery case images from GitHub to local directory."""
import json
import os
import sys
from pathlib import Path
import httpx

DATA_DIR = Path(__file__).parent / "data"
IMAGES_DIR = DATA_DIR / "gallery_images"
IMAGES_DIR.mkdir(parents=True, exist_ok=True)

GITHUB_BASE = "https://raw.githubusercontent.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/main"

gallery_file = DATA_DIR / "gallery_data.json"
if not gallery_file.exists():
    print("gallery_data.json not found")
    sys.exit(1)

with open(gallery_file, encoding="utf-8") as f:
    data = json.load(f)

records = data["records"]
total = len(records)
print(f"Total records: {total}")

downloaded = 0
skipped = 0
failed = 0

def download_one(client, image_dir, retry=2):
    url = f"{GITHUB_BASE}/{image_dir}/output.jpg"
    local_dir = IMAGES_DIR / image_dir
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / "output.jpg"
    if local_path.exists():
        return "skip"
    for attempt in range(retry + 1):
        try:
            res = client.get(url, timeout=30.0)
            if res.status_code == 200:
                local_path.write_bytes(res.content)
                return "ok"
        except Exception:
            if attempt < retry:
                continue
            return "fail"
    return "fail"

with httpx.Client(timeout=httpx.Timeout(30.0), follow_redirects=True) as client:
    for i, r in enumerate(records):
        image_dir = r.get("image_dir", "")
        if not image_dir:
            continue
        result = download_one(client, image_dir)
        if result == "ok":
            downloaded += 1
        elif result == "skip":
            skipped += 1
        else:
            failed += 1
        if (i + 1) % 20 == 0 or i == total - 1:
            print(f"  Progress: {i+1}/{total} — downloaded {downloaded}, skipped {skipped}, failed {failed}")

print(f"\nDone. Downloaded: {downloaded}, Skipped (existing): {skipped}, Failed: {failed}")
