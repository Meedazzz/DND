const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');

global.window = {};
vm.runInThisContext(fs.readFileSync(require.resolve('../public/photo-editor.js'), 'utf8'), { filename: 'photo-editor.js' });

const editor = window.DragonSagaImageEditor;
assert.ok(editor, 'editor API should be registered');
assert.equal(typeof editor.renderMarkup, 'function');
assert.equal(typeof editor.mount, 'function');
assert.ok(Object.isFrozen(editor), 'public API should be immutable');
for (const capability of ['import', 'crop', 'resize', 'rotate', 'flip', 'color', 'filters', 'chroma-key', 'caption', 'undo-redo', 'export', 'campaign-library']) {
  assert.ok(editor.capabilities.includes(capability), `missing capability: ${capability}`);
}

const markup = editor.renderMarkup();
for (const needle of [
  'Редактор изображений', 'photoEditorInput', 'data-editor-key="crop"', 'data-editor-key="brightness"',
  'data-editor-key="chroma"', 'data-editor-key="caption"', 'data-editor-action="undo"',
  'data-editor-action="export"', 'data-editor-action="save-library"', 'image/webp'
]) assert.ok(markup.includes(needle), `markup should include ${needle}`);

const listeners = {};
const root = {
  dataset: {},
  addEventListener(type, callback) { listeners[type] = callback; },
  querySelector() { return null; },
  querySelectorAll() { return []; }
};
editor.mount(root);
for (const event of ['click', 'input', 'change', 'keydown']) assert.equal(typeof listeners[event], 'function', `mount should bind ${event}`);
assert.equal(root.dataset.editorMounted, 'true');

console.log('photo editor smoke: PASS (tool contract + local mount)');
