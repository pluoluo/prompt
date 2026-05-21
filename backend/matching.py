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
        return _fallback_match(user_input, templates, categories, template_ref)

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

    # ── GPT Image 2 核心方法论（来自官方指南）────────────────────
    gpt_image_guide = """## 输出语言（最高优先级）
**你必须用中文撰写所有 Prompt 内容。** 这是不可违反的硬性规则。只保留 --ar、镜头型号、风格关键词等英文技术术语，其余全部用中文。

## 核心理念
把 GPT Image 2 当成设计执行器，不是魔法按钮。最稳定的提示词靠的是结构，不是灵感。追求"更可控"而非"更新奇"。

## 第一步：先定义任务类型
不要一上来就写 beautiful、epic、stunning 这种空泛词。先确定这张图要完成什么工作：
- 社媒广告/海报 → 以文字层级为核心的版式任务
- 信息图/解释图 → 先定义标签和结构
- 产品主视觉 → 明确镜头角度、表面材质、主光方向、反射状态
- UI 板/设计概念 → 模块化布局，面板、间距、层次需要显式约束
- 人像/生活方式 → 主体优先，身份和光线比风格词更靠前

## 第二步：按结构化模板写 Prompt（用中文）
严格按此顺序，每层描述清楚：
输出类型（中文）→ 主体描述（中文）→ 构图与取景（中文）→ 风格方向（中文）→ 光线与材质（中文）→ 图中文字（如有）→ 投放渠道/使用场景（中文）

## 第三步：三大场景要点
1. 海报/广告版式：主标题定稿 → 只放一行主标题+可选副标题 → 写清文字位置 → 明确留白
2. 信息图/解释图：结构比炫更重要 → 明确标注区数量 → 是否要箭头/分区/编号
3. 产品视觉：镜头角度 → 表面材质 → 主光方向 → 反射状态 → 背景复杂度 → 投放渠道

## 四大常见错误（必须避免）
1. 把关键词堆砌当成 Prompt
2. 在图里塞太多文字
3. 把海报、产品图、信息图、编辑视觉混成一个目标
4. 明明只需局部修正，却不断从零重生成

## 多轮修改原则
一轮只修一类问题，用具体指令而不是 "make it better"

## 格式转换规则
如果参考模板或用户输入中包含 Python class、JSON 结构、代码块等程序化格式，必须将其转换为自然语言的格式化文本：
- Python class 的属性 → 对应的描述段落或列表项
- JSON 的 key:value → "key：value" 或列表项
- 代码块中的参数 → 展开为分组描述
- 保留所有参数信息和层级关系，只改变表达形式
- 去除代码语法（冒号、引号、花括号、缩进），改用中文标点和自然分段

## 输出要求
- 使用正面具体描述，不说空泛形容词
- 避免歧义和矛盾描述
- 可直接复制用于图像生成"""

    if template_ref:
        # User chose a specific template — skip matching, just generate based on reference
        system_prompt = f"""You are a JSON-only response bot. You MUST output valid JSON and NOTHING ELSE — no markdown, no code fences, no extra text.

你是一个 AI 图像提示词(Prompt)编辑专家。

## 核心原则：模板结构优先

用户已选择了一个参考模板，你需要以该模板为蓝本生成新的 Prompt：
1. 理解模板的整体风格、结构层次和用词习惯——它是怎么组织信息的？
2. 用同样的风格和结构层次，写一个全新的 Prompt 来满足用户需求
3. 不要照搬模板的词句，而是借鉴它的组织方式和表达风格
4. 如果用户需求没覆盖模板中的某些部分，合理补全

## 格式转换
如果模板中包含 Python class、JSON 结构、代码块等程序化格式，必须转换为自然语言格式化文本：
- Python class 属性 → 对应描述段落/列表项
- JSON key:value → "key：value" 或列表项
- 代码块参数 → 展开为分组描述
- 保留所有信息，只改变表达形式，去除代码语法

## 质量标准（参考 GPT Image 2 指南）
- 必须用中文输出（硬性要求），仅保留英文技术术语（--ar、镜头型号、风格关键词）
- 用正面具体描述代替空泛形容词
- 避免歧义和矛盾描述
- 如果是多轮对话，一轮只修一类问题，不要重写整个 prompt

不要匹配其他模板，不要给出匹配理由，不要套用任何预设的模板格式。

直接输出 JSON（optimized_prompt 必须是中文）：
{{"optimized_prompt": "中文提示词内容"}}"""

        user_prompt = f"""用户需求: {user_input}
{template_context}
{history_context}

请参考以上模板的风格和结构，生成一个全新的中文 Prompt 来满足用户需求。不需要匹配其他模板，不需要给匹配理由，只输出一个高质量的中文 Prompt。"""

    else:
        system_prompt = f"""You are a JSON-only response bot. You MUST output valid JSON and NOTHING ELSE — no markdown, no code fences, no extra text.

你是一个 AI 图像提示词(Prompt)专家，严格遵循以下方法论：

{gpt_image_guide}

你的任务：
1. 先判断用户需求属于哪种任务类型（海报/产品图/信息图/人像/UI板/广告素材）
2. 从模板列表中选出最匹配的 2-3 个模板，返回它们的完整标题
3. 用中文解释匹配理由
4. 按照上述方法论生成一个完整的结构化中文 Prompt
5. 如果是多轮对话，遵循"多轮修改原则"

直接输出 JSON（optimized_prompt 必须是中文）：
{{"matched_titles": ["模板标题1", "模板标题2"], "reason": "匹配理由（中文）", "optimized_prompt": "中文提示词内容"}}"""

        user_prompt = f"""用户需求: {user_input}
{template_context}
{history_context}
可用分类:
{category_summary}

模板列表(前50个):
{template_list}

请按照 GPT Image 2 方法论{'并结合对话历史上下文' if history else ''}，从模板列表中选出最匹配的 2-3 个模板（返回模板的完整标题，不要用索引号），然后生成一份可直接用于图像生成的中文 Prompt。optimized_prompt 必须用中文输出。"""

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
        "max_tokens": 3000 if template_ref else 3000
    }
    
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
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
                
                # Match by title (more reliable than numeric indices)
                matched_templates = []
                matched_titles = parsed.get("matched_titles", [])
                if matched_titles:
                    for title in matched_titles:
                        for t in templates:
                            if t.get("title", "").strip() == title.strip():
                                matched_templates.append(t)
                                break
                # Fallback: try old matched_indices format
                if not matched_templates:
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
    
    return _fallback_match(user_input, templates, categories, template_ref)


def _fallback_match(
    user_input: str,
    templates: List[Dict[str, Any]],
    categories: List[str],
    template_ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Simple keyword-based fallback matching — respects template_ref mode."""
    # If user selected a template, generate based on it — don't match others
    if template_ref:
        ref_prompt = template_ref.get("prompt", "")
        ref_title = template_ref.get("title", "")
        return {
            "optimized_prompt": f"参考「{ref_title}」的风格和结构，为以下需求生成中文 Prompt：\n\n{user_input}\n\n（AI 服务暂时不可用，以上为需求摘要，请稍后重试）",
            "reason": "",
        }

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


async def image_to_prompt(image_base64: str, media_type: str = "image/jpeg", extra_requirements: str = "") -> Dict[str, Any]:
    """Analyze image via MiniMax VLM (coding plan) + generate structured Chinese prompt."""
    if not MINIMAX_API_KEY:
        return {"optimized_prompt": "请配置 MINIMAX_API_KEY", "error": "No API key"}

    vlm_url = "https://api.minimaxi.com/v1/coding_plan/vlm"
    data_url = f"data:{media_type};base64,{image_base64}"
    prompt_text = "请详细描述这张图片的内容、构图、风格、光线、色彩和氛围"
    if extra_requirements:
        prompt_text += f"。额外需求：{extra_requirements}"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Step 1: VLM image description
            vlm_resp = await client.post(vlm_url, headers={
                "Authorization": f"Bearer {MINIMAX_API_KEY}",
                "Content-Type": "application/json"
            }, json={"prompt": prompt_text, "image_url": data_url})
            vlm_resp.raise_for_status()
            vlm_result = vlm_resp.json()
            if vlm_result.get("base_resp", {}).get("status_code") != 0:
                return {"optimized_prompt": "图像分析失败", "error": vlm_result.get("base_resp", {}).get("status_msg", "")}
            description = vlm_result.get("content", "")

            # Step 2: Convert to structured prompt
            if description:
                text_resp = await client.post(MINIMAX_API_URL, headers={
                    "X-Api-Key": MINIMAX_API_KEY, "Content-Type": "application/json", "anthropic-version": "2023-06-01"
                }, json={
                    "model": "MiniMax-M2.7", "temperature": 0.7, "max_tokens": 2000,
                    "system": "You are a prompt engineer. Convert the image description into a structured Chinese prompt. Output ONLY valid JSON: {\"optimized_prompt\": \"the prompt text\"}. Use GPT Image 2 structure. Must be in Chinese.",
                    "messages": [{"role": "user", "content": f"图片描述：\n{description}\n\n转换为结构化中文提示词。"}]
                })
                text_resp.raise_for_status()
                text_result = text_resp.json()
                content = ""
                for block in text_result.get("content", []):
                    if block.get("type") == "text":
                        content = block.get("text", "")
                        break
                j_start = content.find("{"); j_end = content.rfind("}") + 1
                if j_start != -1 and j_end != -1:
                    parsed = json.loads(content[j_start:j_end])
                    return {"description": description, "optimized_prompt": parsed.get("optimized_prompt", description)}
                return {"description": description, "optimized_prompt": description}
    except Exception as e:
        print(f"Image-to-prompt error: {e}")
        return {"optimized_prompt": "图像分析失败，请稍后重试", "error": str(e)}