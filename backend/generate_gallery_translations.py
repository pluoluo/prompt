"""Generate Chinese translations for gallery cases using MiniMax API."""
import json
import os
import time
import re
import httpx
from pathlib import Path

_minimax_key = os.environ.get("MINIMAX_API_KEY", "")
if not _minimax_key:
    _env_path = Path(__file__).parent.parent / ".env"
    if _env_path.exists():
        with open(_env_path) as f:
            for line in f:
                if line.strip().startswith("MINIMAX_API_KEY="):
                    _minimax_key = line.strip().split("=", 1)[1].strip()
                    break

MINIMAX_API_URL = "https://api.minimaxi.com/anthropic/v1/messages"
DATA_DIR = Path(__file__).parent / "data"
GALLERY_FILE = DATA_DIR / "gallery_data.json"
TRANSLATIONS_FILE = DATA_DIR / "gallery_translations.json"

CATEGORY_MAP = {
    "Portrait & Photography Cases": "人像与摄影案例",
    "UI & Social Media Mockup Cases": "UI与社交媒体案例",
    "Poster & Illustration Cases": "海报与插画案例",
    "Character Design Cases": "角色设计案例",
    "Ad Creative Cases": "广告创意案例",
    "E-commerce Cases": "电商案例",
    "Comparison & Community Examples": "对比与社区案例",
}


async def translate_batch(items, client):
    """items: list of {caseId, title, prompt}"""
    batch_text = []
    for i, item in enumerate(items):
        batch_text.append(f'<item id="{i}">\nTitle: {item["title"]}\nPrompt: {item["prompt"][:500]}\n</item>')

    system = """You are a JSON-only response bot. You MUST output valid JSON and NOTHING ELSE.

Translate the following AI image generation case titles and prompts from English to Chinese.
Rules:
- Translate titles naturally into Chinese
- For prompts: translate descriptive content to natural Chinese, keep technical terms in English (aspect ratios, camera specs, "--ar", etc.)
- Keep brand names and proper nouns in original language
- Keep markdown/special tokens unchanged
- Truncated prompts (ending with "...") should be translated accordingly

Output ONLY a JSON object mapping item IDs (as strings) to objects with "title" and "prompt":
{"0": {"title": "中文标题", "prompt": "中文提示词"}, ...}"""

    headers = {
        "X-Api-Key": _minimax_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": "MiniMax-M2.7",
        "system": system,
        "messages": [{"role": "user", "content": "Translate:\n\n" + "\n\n".join(batch_text)}],
        "temperature": 0.3,
        "max_tokens": 12000,
    }

    response = await client.post(MINIMAX_API_URL, headers=headers, json=payload, timeout=180.0)
    response.raise_for_status()
    result = response.json()

    content = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            content = block.get("text", "")
            break

    json_start = content.find("{")
    json_end = content.rfind("}") + 1
    if json_start == -1 or json_end == -1:
        print(f"  Failed to find JSON: {content[:200]}...")
        return None

    try:
        return json.loads(content[json_start:json_end])
    except json.JSONDecodeError:
        print(f"  JSON parse error: {content[:300]}...")
        return None


async def main():
    with open(GALLERY_FILE, encoding="utf-8") as f:
        gallery = json.load(f)

    records = gallery.get("records", gallery)

    # Load existing translations
    existing = {}
    if TRANSLATIONS_FILE.exists():
        with open(TRANSLATIONS_FILE, encoding="utf-8") as f:
            existing = json.load(f)
    print(f"Existing translations: {len(existing)}")

    # Find cases needing translation
    to_translate = []
    for r in records:
        case_id = r.get("image_dir", "")
        if not case_id:
            continue
        if case_id not in existing:
            prompt = (r.get("prompt") or "").strip()
            if not prompt:
                continue
            to_translate.append({
                "caseId": case_id,
                "title": r.get("title", ""),
                "prompt": prompt,
                "category": r.get("category", ""),
            })

    print(f"Need to translate: {len(to_translate)}/{len(records)} cases")

    if not to_translate:
        print("All done!")
        return

    batch_size = 4
    translated_count = len(existing)

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(to_translate), batch_size):
            batch = to_translate[batch_start:batch_start + batch_size]
            print(f"\nBatch {batch_start // batch_size + 1}/{(len(to_translate) - 1) // batch_size + 1}: "
                  f"{len(batch)} cases...")

            try:
                result = await translate_batch(batch, client)
            except Exception as e:
                print(f"  API error: {e}")
                time.sleep(5)
                continue

            if result is None:
                print("  Skipping batch due to parse error")
                time.sleep(2)
                continue

            for idx_str, trans in result.items():
                try:
                    idx = int(idx_str)
                    if idx < len(batch):
                        case_id = batch[idx]["caseId"]
                        cat = batch[idx].get("category", "")
                        existing[case_id] = {
                            "title": trans.get("title", batch[idx]["title"]),
                            "category": CATEGORY_MAP.get(cat, cat),
                            "categoryShort": CATEGORY_MAP.get(cat, cat),
                            "prompt": trans.get("prompt", batch[idx]["prompt"]),
                        }
                        translated_count += 1
                        print(f"  [{case_id}] {batch[idx]['title'][:40]} -> {trans.get('title', '')[:30]}")
                except (ValueError, IndexError) as e:
                    print(f"  Bad index {idx_str}: {e}")

            # Save progress
            with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"  Progress saved ({translated_count}/{len(records)})")

            time.sleep(0.5)

    # Final save
    with open(TRANSLATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n=== Done: {len(existing)} translations ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
