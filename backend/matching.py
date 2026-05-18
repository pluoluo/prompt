import os
import json
import httpx
from typing import List, Dict, Any


MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_API_URL = "https://api.minimaxi.com/anthropic/v1/messages"

CATEGORIES = [
    "Photography & Realism",
    "UI & Interfaces",
    "Posters & Typography",
    "Illustration & Art",
    "Architecture & Spaces",
    "Characters & People",
    "Products & E-commerce",
    "Infographics",
    "Other"
]


async def match_prompt(
    user_input: str,
    templates: List[Dict[str, Any]],
    categories: List[str]
) -> Dict[str, Any]:
    """
    Match user input to templates using MiniMax LLM.
    Returns: {
        matched_templates: [...],
        optimized_prompt: str,
        reason: str
    }
    """
    if not MINIMAX_API_KEY:
        return _fallback_match(user_input, templates, categories)
    
    category_summary = "\n".join([f"- {c}" for c in categories])
    
    template_summaries = []
    for i, t in enumerate(templates[:50]):
        summary = f"[{i}] {t.get('title', '')} | Category: {t.get('category', '')} | Styles: {', '.join(t.get('styles', []))} | Scenes: {', '.join(t.get('scenes', []))}"
        template_summaries.append(summary)
    
    template_list = "\n".join(template_summaries)
    
    system_prompt = """You are an expert at matching user requests to image prompt templates.
Given a user's request in Chinese or English, you must:
1. First identify the top 2-3 most matching templates from the list
2. Explain why they match
3. Generate an optimized English prompt based on the best match

Return your response in JSON format:
{
    "matched_indices": [0, 1, 2],
    "reason": "explanation in Chinese",
    "optimized_prompt": "the optimized English prompt"
}

Be precise and creative. The optimized prompt should combine the best elements from the matched templates while贴合用户的需求."""
    
    user_prompt = f"""用户需求: {user_input}

可用分类:
{category_summary}

模板列表(前50个):
{template_list}

请根据用户需求，从上述模板列表中选择最匹配的2-3个(使用索引号0-49)，然后生成优化后的英文Prompt。"""

    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": "MiniMax-M2.7",
        "messages": [
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                MINIMAX_API_URL,
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            # Anthropic-compatible response format
            content = result.get("content", [{}])[0].get("text", "")
            
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                parsed = json.loads(json_str)
                
                matched_indices = parsed.get("matched_indices", [])
                matched_templates = [templates[i] for i in matched_indices if i < len(templates)]
                
                return {
                    "matched_templates": matched_templates,
                    "optimized_prompt": parsed.get("optimized_prompt", ""),
                    "reason": parsed.get("reason", "")
                }
    except Exception as e:
        print(f"MiniMax API error: {e}")
    
    return _fallback_match(user_input, templates, categories)


def _fallback_match(
    user_input: str,
    templates: List[Dict[str, Any]],
    categories: List[str]
) -> Dict[str, Any]:
    """Simple keyword-based fallback matching"""
    user_lower = user_input.lower()
    
    keywords_map = {
        "photography": ["photo", "写真", "摄影", "realistic", "portrait"],
        "ui": ["ui", "界面", "interface", "app", "网站"],
        "poster": ["poster", "海报", "typography", "字体"],
        "illustration": ["illustration", "插画", "art", "艺术"],
        "architecture": ["architecture", "建筑", "space", "室内"],
        "character": ["character", "角色", "人物", "people"],
        "product": ["product", "产品", "商品", "e-commerce", "电商"],
        "infographic": ["infographic", "图表", "data", "数据"],
    }
    
    matched = []
    for kw, terms in keywords_map.items():
        if any(term in user_lower for term in terms):
            for t in templates:
                cat_lower = t.get("category", "").lower()
                if kw in cat_lower or any(term in cat_lower for term in terms):
                    if t not in matched:
                        matched.append(t)
    
    if not matched:
        matched = templates[:3]
    
    return {
        "matched_templates": matched[:3],
        "optimized_prompt": user_input,
        "reason": "基于关键词匹配找到的模板"
    }
