(function () {
    'use strict';
    const Core = window.SpacePromptCore;
    const STORAGE_KEY = 'prompt_portal_space_v1';
    let configPromise = null;
    function loadConfig() {
        if (!configPromise) configPromise = fetch(new URL('data/space-presets.local.json', document.baseURI), {cache: 'no-cache'})
            .then(async response => {
                if (!response.ok) throw new Error('尚未安装空间设计预设库，请选择完整参数文件，或联系管理员安装。');
                const data = await response.json();
                Core.validateConfig(data);
                return data;
            }).catch(error => { configPromise = null; throw error; });
        return configPromise;
    }
    window.SpaceGenerator = {
        emits: ['use-ai'],
        setup(_, {emit}) {
            const {ref, computed, watch, onMounted} = Vue;
            const config = ref(null), loading = ref(true), error = ref(''), status = ref('');
            const groupKey = ref(''), presetKey = ref(''), search = ref('');
            const values = ref({}), extra = ref(''), customOpen = ref({}), customDraft = ref({});
            const reference = ref(''), previewFailed = ref(false), confirmReset = ref(false);
            let initialized = false, saved = {presets: {}};
            try { const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY)); if (parsed && typeof parsed.presets === 'object' && parsed.presets) saved = parsed; } catch (_) {}
            const groups = computed(() => Object.entries(config.value?.groups || {}).map(([key, group]) => ({key, ...group})));
            const group = computed(() => config.value?.groups[groupKey.value]);
            const preset = computed(() => group.value?.presets.find(item => item.key === presetKey.value));
            const presetImage = computed(() => {
                const file = preset.value?.preview?.items?.[0]?.localImage;
                return typeof file === 'string' && /^data\/space-preview\.local\/[a-zA-Z0-9_.-]+$/.test(file) ? file : '';
            });
            const sections = computed(() => Core.sectionsFor(group.value, preset.value));
            const sectionList = computed(() => Object.entries(sections.value).map(([key, section]) => ({key, ...section,
                fieldsList: Object.entries(section.fields || {}).map(([fieldKey, field]) => ({key: fieldKey, id: Core.fieldId(key, fieldKey), ...field}))})));
            const filteredPresets = computed(() => (group.value?.presets || []).filter(item => (item.name || item.key).toLowerCase().includes(search.value.toLowerCase())));
            const count = computed(() => groups.value.reduce((total, item) => total + item.presets.length, 0));
            const prompt = computed(() => JSON.stringify(Core.compose(sections.value, values.value, extra.value), null, 4));
            const selectedId = () => JSON.stringify([groupKey.value, presetKey.value]);
            function persist() {
                if (!initialized || !preset.value) return;
                saved.last = {group: groupKey.value, preset: presetKey.value};
                saved.presets[selectedId()] = {values: values.value, extra: extra.value};
                try { localStorage.setItem(STORAGE_KEY, JSON.stringify(saved)); }
                catch (_) { status.value = '浏览器无法保存进度；当前结果仍可复制或下载。'; }
            }
            function selectPreset(key) {
                if (initialized) persist();
                presetKey.value = key;
                const state = saved.presets[selectedId()];
                values.value = Core.restore(sections.value, state?.values);
                extra.value = typeof state?.extra === 'string' ? state.extra : '';
                customOpen.value = {}; customDraft.value = {}; confirmReset.value = false; previewFailed.value = false;
                initialized = true;
                persist();
            }
            function selectGroup(key) {
                persist(); initialized = false;
                groupKey.value = key; search.value = '';
                selectPreset(group.value.presets[0].key);
            }
            function install(data) {
                Core.validateConfig(data); initialized = false; config.value = data;
                const last = saved.last;
                groupKey.value = data.groups[last?.group] ? last.group : Object.keys(data.groups)[0];
                const target = group.value.presets.find(item => item.key === last?.preset) || group.value.presets[0];
                selectPreset(target.key); error.value = '';
            }
            async function load() {
                loading.value = true; error.value = '';
                try { install(await loadConfig()); }
                catch (e) { error.value = e.message || '预设加载失败，请重试。'; }
                finally { loading.value = false; }
            }
            async function importConfig(event) {
                const file = event.target.files[0]; if (!file) return;
                try {
                    if (file.size > 12 * 1024 * 1024) throw new Error('预设文件过大，请选择 12MB 以内的 JSON 文件。');
                    install(JSON.parse(await file.text()));
                    status.value = '预设已在当前页面载入；刷新后将重新读取服务器预设库。';
                } catch (e) { status.value = '载入失败：' + e.message; }
                event.target.value = '';
            }
            function choose(field, value) {
                if (field.type === 'multi-select') {
                    const list = values.value[field.id] || [];
                    values.value[field.id] = list.includes(value) ? list.filter(item => item !== value) : [...list, value];
                } else values.value[field.id] = value;
            }
            function selected(field, value) {
                const current = values.value[field.id];
                return Array.isArray(current) ? current.includes(value) : current === value;
            }
            function openCustom(field) {
                customOpen.value[field.id] = !customOpen.value[field.id];
                if (!Object.hasOwn(customDraft.value, field.id)) customDraft.value[field.id] = '';
            }
            function applyCustom(field) {
                const text = (customDraft.value[field.id] || '').trim();
                if (!text) { status.value = '请先填写自定义内容。'; return; }
                if (text.startsWith('{')) {
                    try { const parsed = JSON.parse(text); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error(); }
                    catch (_) { status.value = 'JSON 对象格式有误，请检查引号、逗号及括号。'; return; }
                }
                if (field.type === 'multi-select') {
                    const current = values.value[field.id] || [];
                    if (!current.includes(text)) values.value[field.id] = [...current, text];
                } else values.value[field.id] = text;
                customOpen.value[field.id] = false; status.value = '自定义内容已应用。';
            }
            function customValues(field) {
                const known = new Set(Core.optionItems(field).map(item => item.value));
                const current = values.value[field.id];
                return (Array.isArray(current) ? current : [current]).filter(item => typeof item === 'string' && item && !known.has(item));
            }
            function summary(field) {
                const current = values.value[field.id];
                const describe = value => {
                    if (value.startsWith('{')) { try { const parsed = JSON.parse(value); if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) return '自定义 JSON 对象'; } catch (_) {} }
                    const item = Core.optionItems(field).find(item => item.value === value);
                    const label = item?.label || value;
                    return label.length > 70 ? label.slice(0, 70) + '…' : label;
                };
                return Array.isArray(current) ? (current.map(describe).join(' · ') || '未选择') : (typeof current === 'string' ? describe(current) : '');
            }
            function resetPreset() {
                if (!confirmReset.value) { confirmReset.value = true; return; }
                values.value = Core.defaults(sections.value); extra.value = ''; customOpen.value = {}; customDraft.value = {};
                confirmReset.value = false; status.value = '当前预设已恢复默认。'; persist();
            }
            async function copy() {
                try {
                    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(prompt.value);
                    else {
                        const previous = document.activeElement;
                        const input = document.createElement('textarea'); input.value = prompt.value;
                        input.style.cssText = 'position:fixed;left:-9999px;top:0'; document.body.appendChild(input); input.select();
                        const copied = document.execCommand('copy'); input.remove(); previous?.focus();
                        if (!copied) throw new Error();
                    }
                    status.value = 'JSON 已复制。'; return true;
                } catch (_) { status.value = '复制未成功，请下载 JSON，或选中右侧文本后复制。'; return false; }
            }
            function download() {
                const blob = new Blob([prompt.value + '\n'], {type: 'application/json;charset=utf-8'});
                const url = URL.createObjectURL(blob), link = document.createElement('a'); link.href = url;
                link.download = (preset.value?.name || '空间设计提示词').replace(/[<>:"/\\|?*]/g, '-') + '.json';
                document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
                status.value = 'JSON 文件已准备下载。';
            }
            function useAI() {
                persist(); emit('use-ai', {title: preset.value.name, category: group.value.name, prompt: prompt.value});
            }
            function focusOutput() {
                document.getElementById('space-output')?.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
            async function openDoubao() {
                const tab = window.open('https://www.doubao.com/chat/', '_blank');
                if (tab) tab.opener = null;
                const copied = await copy();
                if (copied) status.value = tab ? '已复制，请在豆包中粘贴并添加原图。' : '已复制；浏览器阻止了新窗口，可手动打开豆包。';
            }
            function previewImage(event) {
                const file = event.target.files[0]; if (!file) return;
                if (!file.type.startsWith('image/') || file.type === 'image/svg+xml' || file.size > 12 * 1024 * 1024) { status.value = '请选择 12MB 以内的普通图片。'; return; }
                const reader = new FileReader(); reader.onload = () => { reference.value = reader.result; }; reader.readAsDataURL(file);
                event.target.value = '';
            }
            watch([values, extra], persist, {deep: true});
            onMounted(load);
            return {loading, error, status, config, groupKey, presetKey, search, values, extra, customOpen, customDraft,
                reference, previewFailed, presetImage, confirmReset, groups, group, preset, sectionList, filteredPresets, count, prompt, load, importConfig,
                selectGroup, selectPreset, choose, selected, openCustom, applyCustom, customValues, summary,
                resetPreset, copy, download, useAI, focusOutput, openDoubao, previewImage, optionItems: Core.optionItems};
        },
        template: `
        <div class="space-studio">
            <div v-if="loading" class="sp-load-state" role="status">正在载入设计预设…</div>
            <div v-else-if="error" class="sp-load-state"><p role="alert">{{ error }}</p><button class="sp-btn" @click="load">重新载入</button> <label class="sp-btn">选择预设文件<input class="sp-file-input" type="file" accept=".json,application/json" @change="importConfig"></label></div>
            <div v-else class="sp-layout">
                <div class="sp-main">
                    <div class="sp-heading"><div><div class="sp-eyebrow">SPACE DESIGN / PROMPT STUDIO</div><h1>空间设计生成器</h1><p>选一套场景预设，调好材质与光影，让模型图更接近你想要的效果。</p></div><div class="sp-count">{{ count }} 套场景预设</div></div>
                    <div class="sp-groups" aria-label="设计分类"><button v-for="g in groups" :key="g.key" :aria-pressed="groupKey === g.key" @click="selectGroup(g.key)">{{ g.icon }} {{ g.name }} <small>{{ g.presets.length }}</small></button></div>
                    <div class="sp-preset-tools"><input class="sp-input" v-model="search" type="search" placeholder="搜索当前分类的场景预设" aria-label="搜索场景预设"><span>{{ filteredPresets.length }} 套预设</span></div>
                    <div class="sp-presets" aria-label="场景预设"><button v-for="p in filteredPresets" :key="p.key" :aria-pressed="presetKey === p.key" @click="selectPreset(p.key)">{{ p.name || p.key }}</button><div v-if="!filteredPresets.length" class="sp-empty">没有匹配的预设，试试其他关键词。</div></div>
                    <section class="sp-section" v-for="(section, i) in sectionList" :key="section.key"><h2 class="sp-section-title"><span class="sp-section-number">{{ String(i + 1).padStart(2, '0') }}</span>{{ section.key }}</h2>
                        <div class="sp-section-grid"><div class="sp-card" v-for="field in section.fieldsList" :key="field.id">
                            <div class="sp-card-head"><h3>{{ field.label || field.key }}</h3><small v-if="field.type === 'multi-select'">可多选</small></div>
                            <p v-if="field.description" class="sp-description">{{ field.description }}</p>
                            <label v-if="field.type === 'switch' || field.type === 'boolean'"><input class="sp-switch" type="checkbox" v-model="values[field.id]" :aria-label="field.label || field.key"> {{ values[field.id] ? '开启' : '关闭' }}</label>
                            <textarea v-else-if="field.type === 'text'" class="sp-input" v-model="values[field.id]" :aria-label="field.label || field.key"></textarea>
                            <template v-else><div class="sp-pills" :aria-label="field.label || field.key"><button class="sp-pill" v-for="(option, oi) in optionItems(field)" :key="oi" :aria-pressed="selected(field, option.value)" :title="option.value" @click="choose(field, option.value)">{{ option.label }}</button><button class="sp-pill" v-for="(value, ci) in customValues(field)" :key="'custom-' + ci" aria-pressed="true" :title="value" @click="field.type === 'multi-select' ? choose(field, value) : openCustom(field)">自定义 {{ ci + 1 }} {{ field.type === 'multi-select' ? '×' : '' }}</button><button class="sp-custom" @click="openCustom(field)">＋ 自定义</button></div><p class="sp-chosen">{{ summary(field) }}</p>
                                <div class="sp-custom-box" v-if="customOpen[field.id]"><textarea class="sp-input" v-model="customDraft[field.id]" :aria-label="'自定义：' + (field.label || field.key)" placeholder="填写具体要求，也可粘贴完整 JSON 对象"></textarea><div class="sp-custom-actions"><button class="sp-link-btn" @click="customOpen[field.id] = false">取消</button><button class="sp-btn" @click="applyCustom(field)">应用</button></div></div>
                            </template>
                        </div></div>
                    </section>
                    <div class="sp-extra"><label for="sp-extra-input">补充要求</label><textarea id="sp-extra-input" class="sp-input" v-model="extra" placeholder="例如：右侧品牌标志保持清晰，柜体侧板为平整哑光白色。"></textarea></div>
                    <div class="sp-foot"><button class="sp-link-btn" @click="resetPreset">{{ confirmReset ? '确认恢复当前预设默认值' : '恢复当前预设默认值' }}</button><button v-if="confirmReset" class="sp-link-btn" @click="confirmReset = false">取消</button><span>参数自动保存在当前浏览器</span></div>
                </div>
                <aside class="sp-output" id="space-output"><div class="sp-output-top"><h2>{{ preset?.name }}</h2><p>先保持默认，只调整你需要改变的部分。</p></div>
                    <div class="sp-reference"><img v-if="reference || (presetImage && !previewFailed)" :src="reference || presetImage" :alt="reference ? '你选择的场景参考图' : preset.name + ' · 预设效果参考'" @error="previewFailed = true"><label class="sp-reference-label">{{ reference ? '更换场景参考图' : '＋ 选择自己的场景参考图' }}<input class="sp-file-input" type="file" accept="image/png,image/jpeg,image/webp,image/gif" @change="previewImage"><br><small>仅在本机预览，生成提示词时不会上传</small></label><button v-if="reference" class="sp-link-btn" @click="reference = ''">查看预设参考图</button></div>
                    <div class="sp-output-tabs"><strong>JSON 提示词</strong><span>● 实时更新</span></div><pre class="sp-code" tabindex="0" aria-label="JSON 提示词结果">{{ prompt }}</pre>
                    <div class="sp-actions"><button class="sp-btn sp-btn-primary" @click="copy">复制 JSON</button><button class="sp-btn" @click="download">下载 JSON</button><button class="sp-btn sp-btn-wide" @click="useAI">继续用 AI 改写 →</button><button class="sp-link-btn sp-btn-wide" @click="openDoubao">复制并打开豆包 ↗</button></div>
                    <div v-if="status" class="sp-status" role="status">{{ status }}</div>
                    <div class="sp-source">预设来源：LIN 网站公开前台 · 交流学习整理<br><a href="https://154.201.65.81/" target="_blank" rel="noopener noreferrer">查看原始来源 ↗</a></div>
                </aside>
            </div><div v-if="config && !loading && !error" class="sp-mobile-actions"><button class="sp-btn" @click="focusOutput">查看提示词 ↓</button><button class="sp-btn sp-btn-primary" @click="copy">复制当前 JSON</button></div><div v-if="error && status" class="sp-status" role="status">{{ status }}</div>
        </div>`
    };
})();
