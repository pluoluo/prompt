"""Batch translate English prompts in prompts_data.json to Chinese using MiniMax API."""
import json
import os
import sys
import time
import re
import httpx

# Load API key
_minimax_key = os.environ.get("MINIMAX_API_KEY", "")
if not _minimax_key:
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(_env_path):
        with open(_env_path, "r") as _f:
            for _line in _f:
                if _line.strip().startswith("MINIMAX_API_KEY="):
                    _minimax_key = _line.strip().split("=", 1)[1].strip()
                    break

MINIMAX_API_URL = "https://api.minimaxi.com/anthropic/v1/messages"
DATA_FILE = os.path.join(os.path.dirname(__file__), "prompts_data.json")
BACKUP_FILE = os.path.join(os.path.dirname(__file__), "prompts_data.json.bak")

# Style/scene translation mapping
STYLE_MAP = {
    "Photography": "摄影",
    "Realistic": "写实",
    "Character": "角色",
    "Characters": "角色",
    "Illustration": "插画",
    "3D": "3D",
    "UI": "UI",
    "Poster": "海报",
    "Architecture": "建筑",
    "Brand": "品牌",
    "Charts": "图表",
    "Infographic": "信息图",
    "Classical": "古典",
    "Documents": "文档",
    "History": "历史",
    "Other Use Cases": "其他",
    "Product": "产品",
    "Products": "产品",
    "Scenes": "场景",
}

SCENE_MAP = {
    "Commerce": "商业",
    "Creative": "创意",
    "Education": "教育",
    "Fashion": "时尚",
    "Food": "美食",
    "History": "历史",
    "Social": "社交",
    "Story": "叙事",
    "Tech": "科技",
    "Travel": "旅行",
}

TITLE_MAP = {
    "Transparent Labs Hydrate 健身补剂 Campaign": "Transparent Labs Hydrate 运动补剂广告大片",
    "NOIR 街头服饰 Campaign": "NOIR 街头品牌广告大片",
}


def has_chinese(s):
    """Check if a string has significant Chinese content."""
    cn = len(re.findall(r'[一-鿿㐀-䶿]', s))
    return cn >= len(s) * 0.15


def needs_translation(t):
    """Check if template prompt needs translation."""
    prompt = t.get("prompt", "")
    if not prompt:
        return False
    return not has_chinese(prompt)


async def translate_batch(templates_batch, client):
    """Translate a batch of prompts using MiniMax API."""
    items = []
    for idx, t in enumerate(templates_batch):
        items.append(f'<item id="{idx}">\n{t["prompt"]}\n</item>')

    system = """You are a JSON-only response bot. You MUST output valid JSON and NOTHING ELSE.

Translate the following AI image generation prompts from English to Chinese.
Rules:
- Translate descriptive content to natural Chinese
- Keep technical parameters in English (aspect ratios like "16:9", camera specs, "--ar", "--v", etc.)
- Keep brand names, product names, and proper nouns in original language
- Keep markdown/image formatting syntax unchanged
- Preserve the original structure, line breaks, and paragraph organization
- Keep any code-like syntax or special tokens unchanged (e.g., {arguments}, [placeholders])
- Translate fashion/style terms naturally into Chinese

Output ONLY a JSON object mapping item IDs (as strings) to translated prompts:
{"0": "translated prompt 1", "1": "translated prompt 2", ...}"""

    user = f"Translate these image prompts to Chinese:\n\n" + "\n\n".join(items)

    headers = {
        "X-Api-Key": _minimax_key,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model": "MiniMax-M2.7",
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "temperature": 0.3,
        "max_tokens": 16000,
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
        print(f"  Failed to find JSON in response: {content[:200]}...")
        return None

    try:
        parsed = json.loads(content[json_start:json_end])
        return parsed
    except json.JSONDecodeError:
        print(f"  JSON parse error: {content[:300]}...")
        return None


async def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backup
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Backup saved to {BACKUP_FILE}")

    # Translate styles and scenes
    print("\n=== Translating styles and scenes ===")
    for t in data:
        t["styles"] = [STYLE_MAP.get(s, s) for s in t.get("styles", [])]
        t["scenes"] = [SCENE_MAP.get(s, s) for s in t.get("scenes", [])]

    # Translate titles
    for t in data:
        tid = str(t.get("id", ""))
        old_title = t.get("title", "")
        if old_title in TITLE_MAP:
            t["title"] = TITLE_MAP[old_title]
            print(f"  Title [{tid}]: {old_title} -> {TITLE_MAP[old_title]}")

    # Find templates needing prompt translation
    to_translate = [(i, t) for i, t in enumerate(data) if needs_translation(t)]
    print(f"\n=== Translating {len(to_translate)} prompts ===")

    if not to_translate:
        print("Nothing to translate!")
        return

    batch_size = 5
    translated_count = 0

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(to_translate), batch_size):
            batch = to_translate[batch_start : batch_start + batch_size]
            batch_templates = [t for _, t in batch]
            batch_indices = [i for i, _ in batch]

            print(f"\nBatch {batch_start // batch_size + 1}/{(len(to_translate) - 1) // batch_size + 1}: "
                  f"translating {len(batch)} prompts [{batch_start}-{batch_start + len(batch) - 1}]...")

            try:
                result = await translate_batch(batch_templates, client)
            except Exception as e:
                print(f"  API error: {e}")
                time.sleep(5)
                continue

            if result is None:
                print("  Skipping batch due to parse error")
                time.sleep(2)
                continue

            # Apply translations
            for idx_str, translated in result.items():
                try:
                    idx = int(idx_str)
                    if idx < len(batch):
                        original_idx = batch_indices[idx]
                        old_prompt = data[original_idx]["prompt"]
                        data[original_idx]["prompt"] = translated
                        translated_count += 1
                        print(f"  [{data[original_idx]['id']}] {data[original_idx]['title']}: ✓")
                except (ValueError, IndexError) as e:
                    print(f"  Bad index {idx_str}: {e}")

            # Save progress after each batch
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  Progress saved ({translated_count}/{len(to_translate)})")

            time.sleep(1)  # Rate limiting

    # Final save
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Verify
    remaining = sum(1 for t in data if needs_translation(t))
    print(f"\n=== Done: {translated_count} translated, {remaining} remaining ===")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
