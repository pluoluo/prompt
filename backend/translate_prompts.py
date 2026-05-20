"""Generate missing CN/EN translations for gallery prompts via MiniMax API."""
import json, os, re, time, asyncio, httpx
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
CASES_FILE = DATA_DIR / "gallery_data.json"
TRANS_FILE = DATA_DIR / "gallery_translations.json"

# Categories/Styles/Scenes already handled client-side via CN_LABELS
# This script only handles prompt translations

async def translate_batch(items, client, direction="to_cn"):
    """items: [{id, text}]"""
    if direction == "to_cn":
        instruction = "Translate the following AI image prompts from English to Chinese. Keep technical terms (--ar, lens names, camera specs) in English. Keep structure and formatting."
    else:
        instruction = "Translate the following AI image prompts from Chinese to English. Keep technical terms. Keep structure and formatting."

    system = f"""You are a JSON-only response bot. {instruction}
Output ONLY a JSON object mapping item indices to translated prompts: {{"0": "translated text", ...}}"""

    items_text = "\n\n---\n\n".join([f'[{i}] {item["text"][:1500]}' for i, item in enumerate(items)])

    headers = {"X-Api-Key": _minimax_key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"}
    payload = {"model": "MiniMax-M2.7", "system": system, "messages": [{"role": "user", "content": items_text}], "temperature": 0.3, "max_tokens": 8000}

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
        print(f"  No JSON found: {content[:200]}")
        return None
    try:
        return json.loads(content[json_start:json_end])
    except json.JSONDecodeError:
        print(f"  JSON parse error: {content[:300]}")
        return None


async def main():
    with open(CASES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    cases = data.get("cases", [])

    existing = {}
    if TRANS_FILE.exists():
        with open(TRANS_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    # Find cases needing EN->CN translation (EN-only prompts)
    need_cn = []
    for c in cases:
        cid = str(c["id"])
        prompt = (c.get("prompt") or "").strip()
        if not prompt:
            continue
        cn_chars = len(re.findall(r'[一-鿿]', prompt))
        # EN-only: <15% Chinese characters
        if cn_chars < len(prompt) * 0.15:
            # Check if we already have CN translation
            if cid not in existing or not existing[cid].get("prompt_cn"):
                need_cn.append({"id": cid, "text": prompt})
    print(f"Need CN translation: {len(need_cn)} prompts")

    async with httpx.AsyncClient() as client:
        for batch_start in range(0, len(need_cn), 4):
            batch = need_cn[batch_start:batch_start+4]
            print(f"  CN batch {batch_start//4+1}/{(len(need_cn)-1)//4+1}...")
            try:
                result = await translate_batch(batch, client, "to_cn")
            except Exception as e:
                print(f"  API error: {e}")
                time.sleep(5)
                continue
            if result is None:
                time.sleep(2)
                continue
            for idx_str, translated in result.items():
                try:
                    idx = int(idx_str)
                    if idx < len(batch):
                        cid = batch[idx]["id"]
                        if cid not in existing:
                            existing[cid] = {}
                        existing[cid]["prompt_cn"] = translated
                except (ValueError, IndexError):
                    pass
            with open(TRANS_FILE, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"    Progress: {len(existing)} translations")
            time.sleep(0.5)

    # Find cases needing CN->EN translation (CN-only prompts)
    need_en = []
    for c in cases:
        cid = str(c["id"])
        prompt = (c.get("prompt") or "").strip()
        if not prompt:
            continue
        cn_chars = len(re.findall(r'[一-鿿]', prompt))
        # CN-only: >70% Chinese characters
        if cn_chars >= len(prompt) * 0.7:
            if cid not in existing or not existing[cid].get("prompt_en"):
                need_en.append({"id": cid, "text": prompt})
    print(f"\nNeed EN translation: {len(need_en)} prompts")

    for batch_start in range(0, len(need_en), 5):
        batch = need_en[batch_start:batch_start+5]
        print(f"  EN batch {batch_start//5+1}/{(len(need_en)-1)//5+1}...")
        try:
            result = await translate_batch(batch, client, "to_en")
        except Exception as e:
            print(f"  API error: {e}")
            time.sleep(5)
            continue
        if result is None:
            time.sleep(2)
            continue
        for idx_str, translated in result.items():
            try:
                idx = int(idx_str)
                if idx < len(batch):
                    cid = batch[idx]["id"]
                    if cid not in existing:
                        existing[cid] = {}
                    existing[cid]["prompt_en"] = translated
            except (ValueError, IndexError):
                pass
        with open(TRANS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
        print(f"    Progress: {len(existing)} translations")
        time.sleep(0.5)

    print(f"\nDone: {len(existing)} translations total")


if __name__ == "__main__":
    asyncio.run(main())
