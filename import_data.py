import json

with open('/home/sahn/.hermes/prompts/cases.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

templates = []
for case in data.get('cases', []):
    templates.append({
        'id': case.get('id'),
        'title': case.get('title', ''),
        'prompt': case.get('prompt', ''),
        'category': case.get('category', 'Other'),
        'styles': case.get('styles', []),
        'scenes': case.get('scenes', [])
    })

with open('/home/sahn/prompt/backend/prompts_data.json', 'w', encoding='utf-8') as f:
    json.dump(templates, f, ensure_ascii=False, indent=2)

print(f'Imported {len(templates)} templates')
