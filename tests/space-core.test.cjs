const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Core = require('../frontend/space-core.js');

test('defaults, multi-select, switch constraints and custom JSON retain their types', () => {
    const sections = {scene: {fields: {
        choice: {type: 'button-select', options: [{label: 'Friendly label', value: 'Full instruction'}], default: 'missing'},
        multi: {type: 'multi-select', default: ['HDR', 'tripod']},
        'lighting：Window light only': {type: 'switch', default: true},
        disabled: {type: 'switch', default: false},
        materials: {type: 'text', default: ''}
    }}};
    const values = Core.defaults(sections);
    values[Core.fieldId('scene', 'materials')] = '{"wall":"matte white"}';
    const output = JSON.parse(JSON.stringify(Core.compose(sections, values, 'Keep logo')));
    assert.deepEqual(output, {scene: {choice: 'Full instruction', multi: ['HDR','tripod'], lighting: 'Window light only', materials: {wall:'matte white'}}, '补充要求':'Keep logo'});
});

test('saved values stay within current fields and retain supported types', () => {
    const schema = {a: {fields: {x:{type:'text',default:'base'},y:{type:'multi-select',default:[]}}}};
    const restored = Core.restore(schema, {[Core.fieldId('a','x')]:'custom',[Core.fieldId('a','y')]:123,deleted:'bad'});
    assert.equal(restored[Core.fieldId('a','x')], 'custom');
    assert.deepEqual(restored[Core.fieldId('a','y')], []);
    assert.equal(Object.keys(restored).length, 2);
});

test('prototype-like JSON field names remain ordinary output keys', () => {
    const schema = JSON.parse('{"__proto__":{"fields":{"__proto__":{"type":"text","default":"safe"}}}}');
    const output = Core.compose(schema, Core.defaults(schema));
    assert.equal(JSON.parse(JSON.stringify(output)).__proto__.__proto__, 'safe');
    assert.equal({}.safe, undefined);
});

test('reject empty or unsupported configurations', () => {
    assert.throws(() => Core.validateConfig({groups: {}}));
    assert.throws(() => Core.validateConfig({groups: {a:{presets:[]}}}));
    assert.throws(() => Core.validateConfig({groups: {a:{presets:[{key:'x',sections:{a:{fields:{x:{type:'unknown'}}}}}]}}}));
});

const library = process.env.SPACE_PRESET_LIBRARY;
test('preset upgrades migrate old default instructions and preserve custom project facts', () => {
    const sections = {'材料': {fields: {'清单': {type:'select', default:'保留原材料', options:['保留原材料','金属'], previousDefault:'请填写材料清单'}}}};
    const id = Core.fieldId('材料','清单');
    assert.equal(Core.restore(sections, {[id]:'请填写材料清单'})[id], '保留原材料');
    assert.equal(Core.restore(sections, {[id]:'客户指定的白橡木'})[id], '客户指定的白橡木');
});
test('image app URL preserves full JSON and existing base-path configuration', () => {
    const prompt = '{\n"材质": "白色 & 木纹 + 金属", "比例": "16:9"\n}';
    const result = new URL(Core.imageDestination('http://nas:8080/studio?mode=edit', prompt));
    assert.equal(result.pathname, '/studio');
    assert.equal(result.searchParams.get('mode'), 'edit');
    assert.equal(result.searchParams.get('prompt'), prompt);
    assert.throws(() => Core.imageDestination('', prompt));
    assert.throws(() => Core.imageDestination('javascript:alert(1)', prompt));
});

test('cultural wall copy modes retain supplied text and migrate conflicting old defaults', () => {
    const config = JSON.parse(fs.readFileSync(path.join(__dirname, '../frontend/data/professional-presets.json'), 'utf8'));
    for (const preset of config.groups.professional_wall.presets) {
        const sections = preset.sections;
        const contentSection = preset.key === 'wall_concept_v1' ? '文案与层级' : '墙面内容';
        const fields = sections[contentSection].fields;
        const mode = fields['文案补充方式'];
        assert.deepEqual(Core.optionItems(mode).map(x=>x.label), ['仅使用已提供文案','AI 补充栏目标题','AI 补充标题和短文']);
        const copyId = Core.fieldId(contentSection, '准确文案');
        const modeId = Core.fieldId(contentSection, '文案补充方式');
        const saved = {[copyId]:'主标题：刑事审判庭'};
        for (const [sk, section] of Object.entries(sections)) {
            for (const [fk, field] of Object.entries(section.fields)) {
                if (field.previousDefault) saved[Core.fieldId(sk,fk)] = field.previousDefault;
            }
        }
        saved[copyId] = '主标题：刑事审判庭';
        for (const option of Core.optionItems(mode)) {
            const values = Core.restore(sections, {...saved,[modeId]:option.value});
            const output = Core.compose(sections,values);
            assert.equal(output[contentSection]['准确文案'], '主标题：刑事审判庭');
            assert.equal(output[contentSection]['文案补充方式'], option.value);
            assert.ok(!JSON.stringify(output).includes('只使用提供的准确文案、数据、荣誉和品牌资料'));
            assert.ok(!JSON.stringify(output).includes('不得增加原方案没有的装饰、灯带和文字'));
            assert.ok(!JSON.stringify(output).includes('分两张输出'));
        }
    }
});

test('private library defaults match all captured public previews', {skip: !library}, () => {
    const data = JSON.parse(fs.readFileSync(library, 'utf8'));
    const expectedPath = process.env.SPACE_EXPECTED_PREVIEWS;
    assert.equal(Core.validateConfig(data), 51);
    const expected = expectedPath ? JSON.parse(fs.readFileSync(expectedPath, 'utf8')).presets : null;
    for (const [gk, group] of Object.entries(data.groups)) {
        for (const preset of group.presets) {
            const sections = Core.sectionsFor(group, preset);
            const output = JSON.parse(JSON.stringify(Core.compose(sections, Core.defaults(sections))));
            if (expected) assert.deepEqual(output, expected.find(x=>x.group_key===gk && x.preset_key===preset.key).prompt_json, preset.name);
        }
    }
});
