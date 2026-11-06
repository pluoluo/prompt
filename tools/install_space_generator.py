"""Install the Space Generator on an existing Prompt Portal without replacing its data."""
import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


def patch_html(text):
    def image_bridge(current):
        current = current.replace('v=20261106"', 'v=20261106-2"')
        current = current.replace('v=20261106-2"', 'v=20261106-3"')
        current = current.replace('v=20261106-3"', 'v=20261106-4"')
        current = current.replace(' @use-ai="useSpacePrompt"></space-generator>', ' @use-ai="useSpacePrompt" :image-api-url="imageApiUrl" @generate-image="generateImage"></space-generator>')
        current = current.replace("const imageApiUrl = ref('http://localhost:8766');", "const imageApiUrl = ref('');")
        old = '''                function generateImage(prompt) {
                    if (!prompt) return;
                    const url = imageApiUrl.value + '/?prompt=' + encodeURIComponent(prompt);
                    window.open(url, '_blank');
                }'''
        new = '''                function generateImage(prompt) {
                    if (!prompt) return;
                    try {
                        const url = window.SpacePromptCore.imageDestination(imageApiUrl.value, prompt);
                        const tab = window.open(url, '_blank');
                        if (tab) tab.opener = null;
                        else showToast('浏览器阻止了新标签页，请允许此站点打开新标签页后重试。');
                    } catch (error) {
                        showToast(error.message || '生图应用地址无效，请检查 IMAGE_API_URL 配置。');
                    }
                }'''
        if 'window.SpacePromptCore.imageDestination' not in current:
            if current.count(old) != 1:
                raise ValueError('The image-generation bridge could not be located.')
            current = current.replace(old, new, 1)
        return current

    if '<space-generator ' in text:
        markers = ['useSpacePrompt', 'window.SpaceGenerator', './space-core.js', './space-generator.js', './space-generator.css']
        if not all(marker in text for marker in markers):
            raise ValueError('An incomplete generator installation was found; restore its original index first.')
        return image_bridge(text)

    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('The current frontend structure does not match the expected anchor: ' + old[:90])
        text = text.replace(old, new, 1)

    replace('</head>', '    <link rel="stylesheet" href="./space-generator.css?v=20261106">\n</head>')
    replace('            <nav class="header-nav">', '''            <nav class="header-nav">
                <div class="header-nav-item" :class="{active: currentPage === 'space'}" @click="navigate('space')">
                    空间设计
                </div>''')
    replace('        <div class="app-container">', '        <div class="app-container" :class="{\'space-mode\': currentPage === \'space\'}">')
    replace('            <div class="main-content">', '''            <div class="main-content">
                <space-generator v-if="currentPage === 'space'" @use-ai="useSpacePrompt"></space-generator>''')
    replace('    <script>\n        const { createApp, ref, computed, onMounted } = Vue;', '''    <script src="./space-core.js?v=20261106"></script>
    <script src="./space-generator.js?v=20261106"></script>
    <script>
        const { createApp, ref, computed, onMounted } = Vue;''')
    replace('        createApp({\n            setup() {', '''        createApp({
            components: {'space-generator': window.SpaceGenerator},
            setup() {''')
    replace('                function useTemplateInAI() {', '''                function useSpacePrompt(result) {
                    resetConversation();
                    templateRefForAI.value = {
                        id: null, title: result.title, prompt: result.prompt,
                        category: result.category, styles: [], scenes: [],
                        description: '来自空间设计生成器'
                    };
                    matchInput.value = '';
                    currentPage.value = 'match';
                    window.location.hash = 'match';
                }

                function useTemplateInAI() {''')
    replace("['home', 'match', 'submit', 'guide', 'gallery', 'image2text'].includes(hash)", "['home', 'match', 'submit', 'guide', 'gallery', 'image2text', 'space'].includes(hash)")
    replace('                    useTemplateInAI,', '                    useTemplateInAI,\n                    useSpacePrompt,')
    return image_bridge(text)


def safe_target(root, relative):
    target = (root / relative).resolve()
    target.relative_to(root)
    return target


def install(project_dir, apply=False, library=None):
    source = Path(__file__).resolve().parents[1]
    project = Path(project_dir).resolve(strict=True)
    index = safe_target(project, 'frontend/index.html')
    original = index.read_text(encoding='utf-8')
    updated = patch_html(original)
    plan = {}
    for name in ['space-core.js', 'space-generator.js', 'space-generator.css']:
        plan['frontend/' + name] = (source / 'frontend' / name).read_bytes()
    plan['frontend/data/professional-presets.json'] = (source / 'frontend/data/professional-presets.json').read_bytes()
    library_source = Path(library) if library else source / 'frontend/data/space-presets.local.json'
    if library_source.exists():
        parsed = json.loads(library_source.read_text(encoding='utf-8'))
        if not parsed.get('groups'):
            raise ValueError('The library is missing its groups configuration.')
        plan['frontend/data/space-presets.local.json'] = library_source.read_bytes()
    elif not safe_target(project, 'frontend/data/space-presets.local.json').exists():
        raise ValueError('Provide --library with the complete parameters JSON before installing.')
    image_dir = source / 'frontend/data/space-preview.local'
    if image_dir.exists():
        for image in sorted(image_dir.iterdir()):
            if image.is_file() and image.suffix.lower() in {'.jpg', '.jpeg', '.png', '.webp'}:
                plan['frontend/data/space-preview.local/' + image.name] = image.read_bytes()
    # The entry page is activated only after all assets have been written.
    plan['frontend/index.html'] = updated.encode('utf-8')
    changed = {name: content for name, content in plan.items() if not safe_target(project, name).exists() or safe_target(project, name).read_bytes() != content}
    report = {'project': str(project), 'apply': apply, 'changed_files': len(changed), 'paths': list(changed)}
    if not apply or not changed:
        return report
    backup = safe_target(project, '.space-generator-backups/' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    backup.mkdir(parents=True, exist_ok=False)
    originals = {}
    for relative in changed:
        target = safe_target(project, relative)
        if target.exists():
            original_file = safe_target(backup, relative)
            original_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, original_file)
            originals[relative] = original_file
    try:
        for relative, content in changed.items():
            target = safe_target(project, relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(target.name + '.space-update.tmp')
            temporary.write_bytes(content)
            temporary.replace(target)
    except Exception:
        for relative, original_file in originals.items():
            shutil.copy2(original_file, safe_target(project, relative))
        raise
    report['backup'] = str(backup)
    report['sha256'] = {relative: hashlib.sha256(content).hexdigest() for relative, content in changed.items()}
    (backup / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project-dir', required=True)
    parser.add_argument('--library')
    parser.add_argument('--apply', action='store_true', help='Write files after creating a backup; omitted means check only.')
    args = parser.parse_args()
    print(json.dumps(install(args.project_dir, args.apply, args.library), ensure_ascii=False, indent=2))
