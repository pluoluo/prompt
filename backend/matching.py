import os
import json
import httpx
from typing import List, Dict, Any, Optional


# Load MiniMax API key from environment or .env file
_minimax_key = os.environ.get("MINIMAX_API_KEY", "")
if not _minimax_key:
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(_env_path):
        with open(_env_path, "r") as _f:
            for _line in _f:
                if _line.strip().startswith("MINIMAX_API_KEY="):
                    _minimax_key = _line.strip().split("=", 1)[1].strip()
                    break
MINIMAX_API_KEY = _minimax_key
MINIMAX_API_URL = "https://api.minimaxi.com/anthropic/v1/messages"

CATEGORIES = [
    "摄影与写实",
    "UI与界面",
    "海报与排版",
    "插画与艺术",
    "建筑与空间",
    "角色与人物",
    "产品与电商",
    "图表与信息图",
    "品牌与Logo",
    "文档与出版",
    "历史与古典主题",
    "场景与叙事",
    "其他用例",
]


async def match_prompt(
    user_input: str,
    templates: List[Dict[str, Any]],
    categories: List[str],
    history: Optional[List[Dict[str, str]]] = None,
    template_ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Match user input to templates using MiniMax LLM. Supports multi-turn conversation and template reference."""
    if not MINIMAX_API_KEY:
        return _fallback_match(user_input, templates, categories)

    category_summary = "\n".join([f"- {c}" for c in categories])

    template_summaries = []
    for i, t in enumerate(templates[:50]):
        summary = f"[{i}] {t.get('title', '')} | Category: {t.get('category', '')} | Styles: {', '.join(t.get('styles', []))} | Scenes: {', '.join(t.get('scenes', []))}"
        template_summaries.append(summary)

    template_list = "\n".join(template_summaries)

    template_context = ""
    if template_ref:
        template_context = f"""
参考模板:
- 标题: {template_ref.get('title', '')}
- 分类: {template_ref.get('category', '')}
- Prompt: {template_ref.get('prompt', '')}
- 风格: {', '.join(template_ref.get('styles', []))}
- 场景: {', '.join(template_ref.get('scenes', []))}
- 说明: {template_ref.get('description', '')}

用户希望参考以上模板的风格和结构来生成新的Prompt，请充分理解该模板的结构特点。"""

    history_context = ""
    if history:
        history_context = "\n对话历史:\n"
        for h in history[-6:]:
            role = "用户" if h.get("role") == "user" else "AI"
            history_context += f"{role}: {h.get('content', '')}\n"

    if template_ref:
        # User chose a specific template — skip matching, just generate based on reference
        system_prompt = """You are a JSON-only response bot. You MUST output valid JSON and NOTHING ELSE — no markdown, no code fences, no extra text, no explanations outside the JSON.

你是一个AI图像提示词(Prompt)专家，遵循 GPT Image 2 的结构化提示词方法论。

用户已经选择了一个参考模板，你的任务只是：基于该参考模板的风格和结构，根据用户需求生成一个优化后的中文Prompt。
不要匹配其他模板，不要给出匹配理由。

生成中文Prompt的规范：
- 参考模板的结构特点（输出类型、层级、风格方向、光线材质处理）
- 但内容要完全针对用户的新需求
- 按层级结构写：输出类型 → 主体描述 → 构图取景 → 风格方向 → 光线与材质 → 图中文字(如有) → 适用场景
- 使用中文详细描述画面，保留英文技术术语
- 用正面具体描述代替空泛形容词

Output ONLY valid JSON in this exact format:
{"optimized_prompt": "优化后的中文提示词"}"""

        user_prompt = f"""用户需求: {user_input}
{template_context}
{history_context}

用户已选择参考以上模板。请基于该模板的风格和结构，生成一个全新的中文Prompt来满足用户需求。
不需要匹配其他模板，不需要给出理由，只需要生成一个高质量的中文Prompt。

Prompt必须遵循 GPT Image 2 的层级结构，可直接用于图像生成。"""
    else:
        system_prompt = """You are a JSON-only response bot. You MUST output valid JSON and NOTHING ELSE — no markdown, no code fences, no extra text, no explanations outside the JSON.

你是一个AI图像提示词(Prompt)专家，遵循 GPT Image 2 的结构化提示词方法论。你的任务是：
1. 如果对话历史中有之前生成的Prompt，请在此基础上根据用户新要求进行修改优化
2. 从模板列表中选出最匹配的2-3个模板
3. 用中文解释匹配理由
4. 根据用户需求（结合对话历史和参考模板），生成一个优化后的中文提示词(Prompt)

生成中文Prompt的规范（参考 GPT Image 2 结构化方法）：
- 先确定输出类型（海报/产品视觉/信息图/人像/UI板/广告素材）
- 按层级结构写：输出类型 → 主体描述 → 构图取景 → 风格方向 → 光线与材质 → 图中文字(如有) → 适用场景
- 使用中文详细描述画面，保留英文技术术语（构图比例、风格关键词、技术参数等）
- 用正面具体描述代替空泛形容词（不说"好看"，说"柔和侧光、哑光质感、浅景深"）
- 明确构图与层级：留白、文字位置、视觉焦点
- 如果用户需求涉及文字，精确写出需要出现的文字内容
- 避免歧义和矛盾描述，一条prompt聚焦一个核心场景
- 追求"可控"而非"新奇"：让提示词可复现、可编辑、可交付
- 如果是多轮对话，要根据用户新要求进行针对性修改，保持之前生成中用户认可的部分

Output ONLY valid JSON in this exact format, with no other text before or after:
{"matched_indices": [0, 1, 2], "reason": "匹配理由（中文）", "optimized_prompt": "优化后的中文提示词"}"""

        user_prompt = f"""用户需求: {user_input}
{template_context}
{history_context}
可用分类:
{category_summary}

模板列表(前50个):
{template_list}

请根据用户需求{'和对话历史中的上下文' if history else ''}，从模板列表中选择最匹配的2-3个模板(使用索引号0-49)，然后生成一个结构化的中文Prompt。

Prompt必须遵循 GPT Image 2 的层级结构：输出类型 → 主体 → 构图 → 风格 → 光线材质 → 文字(如有) → 适用场景。用正面具体描述，避免空泛词。生成的中文Prompt必须可直接用于图像生成。"""

    headers = {
        "X-Api-Key": MINIMAX_API_KEY,
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01"
    }

    messages = []
    if history:
        for h in history[-6:]:
            role = h.get("role", "user")
            content = h.get("content", "")
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_prompt})

    payload = {
        "model": "MiniMax-M2.7",
        "system": system_prompt,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1200 if template_ref else 2000
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
            
            # Anthropic-compatible response format — find first "text" block (skip "thinking" blocks)
            content = ""
            for _block in result.get("content", []):
                if _block.get("type") == "text":
                    content = _block.get("text", "")
                    break
            
            json_start = content.find("{")
            json_end = content.rfind("}") + 1
            if json_start != -1 and json_end != -1:
                json_str = content[json_start:json_end]
                parsed = json.loads(json_str)
                
                matched_indices = parsed.get("matched_indices", [])
                matched_templates = [templates[i] for i in matched_indices if i < len(templates)]

                result = {
                    "optimized_prompt": parsed.get("optimized_prompt", ""),
                }
                if matched_templates:
                    result["matched_templates"] = matched_templates
                if parsed.get("reason"):
                    result["reason"] = parsed["reason"]

                return result
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
        "摄影与写实": ["photo", "写真", "摄影", "realistic", "portrait", "写实"],
        "UI与界面": ["ui", "界面", "interface", "app", "网站"],
        "海报与排版": ["poster", "海报", "typography", "字体", "排版"],
        "插画与艺术": ["illustration", "插画", "art", "艺术"],
        "建筑与空间": ["architecture", "建筑", "space", "室内", "空间"],
        "角色与人物": ["character", "角色", "人物", "people"],
        "产品与电商": ["product", "产品", "商品", "e-commerce", "电商"],
        "图表与信息图": ["infographic", "图表", "data", "数据", "信息图"],
        "品牌与Logo": ["brand", "品牌", "logo", "商标"],
        "文档与出版": ["document", "文档", "publishing", "出版"],
        "历史与古典主题": ["history", "历史", "classical", "古典"],
        "场景与叙事": ["scene", "场景", "storytelling", "叙事"],
    }

    matched = []
    for cat_key, terms in keywords_map.items():
        if any(term in user_lower for term in terms):
            for t in templates:
                if t.get("category", "") == cat_key:
                    if t not in matched:
                        matched.append(t)
    
    if not matched:
        matched = templates[:3]
    
    return {
        "matched_templates": matched[:3],
        "optimized_prompt": "请用中文详细描述你想要的画面效果，包括：主体内容、风格、场景、光影、构图等。\n例如：一位年轻女性在咖啡店窗边，自然光从左侧照入，柔和的暖色调，浅景深虚化背景，写实摄影风格，竖构图 3:4",
        "reason": "请输入更具体的需求描述，以便AI为你精准匹配模板并生成中文提示词"
    }
