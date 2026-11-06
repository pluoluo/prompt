(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.SpacePromptCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
    'use strict';
    const fieldId = (section, field) => JSON.stringify([section, field]);
    function optionItems(field) {
        const raw = field.options || [];
        const list = Array.isArray(raw) ? raw : Object.values(raw).flat();
        return list.map(item => typeof item === 'string'
            ? {label: item, value: item}
            : {label: String(item.label ?? item.value), value: String(item.value)});
    }
    function initialValue(field) {
        if (field.type === 'switch' || field.type === 'boolean') return !!field.default;
        if (field.type === 'multi-select') return Array.isArray(field.default) ? [...field.default] : [];
        if (field.type === 'select' || field.type === 'button-select') {
            const values = optionItems(field).map(item => item.value);
            return values.includes(field.default) ? field.default : (values[0] || '');
        }
        return field.type === 'text' ? String(field.default || '') : '';
    }
    function sectionsFor(group, preset) {
        return preset?.sections && Object.keys(preset.sections).length ? preset.sections : (group?.sections || {});
    }
    function defaults(sections) {
        const result = {};
        for (const [sk, section] of Object.entries(sections)) {
            for (const [fk, field] of Object.entries(section.fields || {})) result[fieldId(sk, fk)] = initialValue(field);
        }
        return result;
    }
    function resolveValue(value) {
        if (typeof value === 'string' && value.trim().startsWith('{') && value.trim().endsWith('}')) {
            try {
                const object = JSON.parse(value);
                if (object && typeof object === 'object' && !Array.isArray(object)) return object;
            } catch (_) { /* Ordinary custom text remains text. */ }
        }
        return value;
    }
    function compose(sections, values, extra = '') {
        const result = Object.create(null);
        for (const [sk, section] of Object.entries(sections)) {
            const nested = Object.create(null);
            for (const [fk, field] of Object.entries(section.fields || {})) {
                const id = fieldId(sk, fk);
                const val = Object.hasOwn(values, id) ? values[id] : initialValue(field);
                if (field.type === 'switch' || field.type === 'boolean') {
                    if (!val) continue;
                    const i = Math.max(fk.indexOf(':'), fk.indexOf('：'));
                    if (i >= 0) nested[fk.slice(0, i).trim()] = fk.slice(i + 1).trim();
                    else nested[fk] = true;
                } else nested[fk] = resolveValue(val);
            }
            result[sk] = nested;
        }
        if (extra.trim()) result['补充要求'] = extra.trim();
        return result;
    }
    function restore(sections, saved) {
        const values = defaults(sections);
        if (!saved || typeof saved !== 'object') return values;
        for (const id of Object.keys(values)) {
            if (!Object.hasOwn(saved, id)) continue;
            const expected = values[id], candidate = saved[id];
            if (Array.isArray(expected) && Array.isArray(candidate) && candidate.every(x => typeof x === 'string')) values[id] = candidate;
            else if (typeof expected === typeof candidate && ['string', 'boolean'].includes(typeof candidate)) values[id] = candidate;
        }
        return values;
    }
    function validateConfig(data) {
        if (!data || typeof data.groups !== 'object' || !data.groups || Array.isArray(data.groups)) throw new Error('预设文件缺少 groups 分类配置');
        let count = 0;
        for (const group of Object.values(data.groups)) {
            if (!Array.isArray(group.presets) || !group.presets.length) throw new Error('预设列表为空或格式错误');
            const keys = new Set();
            for (const preset of group.presets) {
                if (typeof preset.key !== 'string' || keys.has(preset.key)) throw new Error('预设编号缺失或重复');
                keys.add(preset.key);
                const sections = sectionsFor(group, preset);
                if (!Object.keys(sections).length) throw new Error('预设缺少参数字段');
                for (const section of Object.values(sections)) {
                    if (!section || !section.fields || typeof section.fields !== 'object') throw new Error('参数分组格式错误');
                    for (const field of Object.values(section.fields)) {
                        if (!['switch', 'boolean', 'text', 'select', 'button-select', 'multi-select'].includes(field.type)) throw new Error('未知参数类型');
                        if (field.options && (typeof field.options !== 'object' || field.options === null)) throw new Error('参数选项格式错误');
                        optionItems(field);
                    }
                }
                count++;
            }
        }
        if (!count) throw new Error('预设文件中没有可用预设');
        return count;
    }
    return {fieldId, optionItems, initialValue, sectionsFor, defaults, compose, restore, validateConfig};
});
