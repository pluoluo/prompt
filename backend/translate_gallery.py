"""Batch translate gallery cases to Chinese using MiniMax LLM."""
import json
import os
import sys
import time
import asyncio
from pathlib import Path
import httpx

DATA_DIR = Path(__file__).parent / "data"
GALLERY_FILE = DATA_DIR / "gallery_data.json"
OUTPUT_FILE = DATA_DIR / "gallery_translations.json"

# Load API key from .env
env_file = Path(__file__).parent / ".env"
api_key = ""
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if line.strip().startswith("MINIMAX_API_KEY="):
                api_key = line.strip().split("=", 1)[1].strip()
                break

if not api_key:
    print("ERROR: MINIMAX_API_KEY not found in .env")
    sys.exit(1)

API_URL = "https://api.minimaxi.com/anthropic/v1/messages"
BATCH_SIZE = 3

CATEGORY_MAP = {
    "Portrait & Photography Cases": "人像摄影",
    "UI & Social Media Mockup Cases": "UI界面",
    "Poster & Illustration Cases": "海报插画",
    "Character Design Cases": "角色设计",
    "Ad Creative Cases": "广告创意",
    "E-commerce Cases": "电商图像",
    "Comparison & Community Examples": "对比示例",
    "Other": "其他",
}

CN_STYLE_POOL = [
    "写实摄影", "人像摄影", "电影感", "胶片颗粒", "黑白", "插画", "数字艺术",
    "油画", "水彩", "动漫", "漫画", "3D渲染", "CGI", "像素风", "矢量图",
    "线稿", "素描", "简约", "极简", "复古", "未来主义", "科幻", "赛博朋克",
    "霓虹灯", "散景", "剪影", "微距", "广角", "鱼眼", "航拍",
    "棚拍光", "自然光", "逆光", "柔光", "暖色调", "冷色调", "柔和", "鲜艳",
    "粉彩", "单色", "平面拍摄", "特写", "全景", "双重曝光", "运动模糊",
    "长曝光", "移轴", "产品摄影", "时尚摄影", "街头摄影", "纪实摄影",
    "超写实", "磨砂质感", "高对比度", "低饱和度",
]


def load_gallery():
    with open(GALLERY_FILE, encoding="utf-8") as f:
        return json.load(f)["records"]


def load_existing_translations():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_translations(trans):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(trans, f, ensure_ascii=False, indent=2)


def build_prompt(batch):
    cases_text = []
    for i, c in enumerate(batch):
        prompt = c.get("prompt", "")
        if len(prompt) > 800:
            prompt = prompt[:800] + "..."
        cases_text.append(
            f"Case {i+1}:\n"
            f"  id: {c['image_dir']}\n"
            f"  title: {c['title']}\n"
            f"  category: {c['category']}\n"
            f"  prompt: {prompt}\n"
        )

    style_options = ", ".join(CN_STYLE_POOL)
    cat_values = list(CATEGORY_MAP.values())

    return f"""Translate these image generation cases to Simplified Chinese.

For each case provide:
1. title: Chinese title (max 15 chars)
2. category: pick one from {json.dumps(cat_values, ensure_ascii=False)}
3. prompt: Full Chinese translation preserving ALL photographic detail, camera specs, lighting, character traits. Use natural Chinese photography terminology.
4. styles: 3-5 Chinese tags from this pool: [{style_options}]. Add 1-2 custom if needed. Comma-separated.

{''.join(cases_text)}

Return ONLY valid JSON (no markdown):
{{"results": [{{"id": "...", "title": "...", "category": "...", "prompt": "...", "styles": "tag1, tag2"}}, ...]}}"""


async def translate_batch(client, batch):
    prompt = build_prompt(batch)
    payload = {
        "model": "MiniMax-M2.5",
        "max_tokens": 16000,
        "temperature": 0.3,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": api_key,
        "anthropic-version": "2023-06-01",
    }

    for attempt in range(3):
        try:
            resp = await client.post(API_URL, json=payload, headers=headers, timeout=180.0)
            if resp.status_code == 200:
                data = resp.json()
                content = data.get("content", [{}])[0].get("text", "")
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                return json.loads(content.strip())
            elif resp.status_code == 429:
                wait = (attempt + 1) * 15
                print(f"  Rate limited, waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"  API error {resp.status_code}: {resp.text[:200]}")
                await asyncio.sleep(5)
        except Exception as e:
            print(f"  Error: {e}")
            await asyncio.sleep(5)
    return None


async def main():
    records = load_gallery()
    existing = load_existing_translations()
    total = len(records)
    print(f"Total cases: {total}")
    print(f"Already translated: {len(existing)}")

    todo = [r for r in records if r["image_dir"] not in existing]
    print(f"To translate: {len(todo)}")

    if not todo:
        print("All done!")
        return

    translated = 0
    batch_start = 0
    total_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE

    async with httpx.AsyncClient() as client:
        while batch_start < len(todo):
            batch = todo[batch_start:batch_start + BATCH_SIZE]
            batch_num = batch_start // BATCH_SIZE + 1
            print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} cases)...", flush=True)

            result = await translate_batch(client, batch)
            if result and "results" in result:
                for r in result["results"]:
                    case_id = r.get("id", "")
                    if case_id:
                        existing[case_id] = {
                            "title": r.get("title", ""),
                            "category": r.get("category", "其他"),
                            "categoryShort": r.get("category", "其他"),
                            "prompt": r.get("prompt", ""),
                            "styles": r.get("styles", ""),
                        }
                        translated += 1
                save_translations(existing)
                print(f"  OK — {translated}/{len(todo)} done, {len(existing)} total", flush=True)
            else:
                print(f"  FAIL — retrying in next pass", flush=True)

            batch_start += BATCH_SIZE
            await asyncio.sleep(3)

    save_translations(existing)
    print(f"\nDone! {len(existing)} translations saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
