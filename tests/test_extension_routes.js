'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {resolveRoute} = require('../extension/background.js');

const root = path.resolve(__dirname, '..');
const manifest = JSON.parse(fs.readFileSync(path.join(root, 'extension/manifest.json')));
const [rule] = JSON.parse(fs.readFileSync(path.join(root, 'extension/redirect_rules.json')));

assert.equal(manifest.manifest_version, 3);
assert.deepEqual(manifest.permissions, ['declarativeNetRequestWithHostAccess']);
assert.equal(manifest.declarative_net_request.rule_resources[0].path, 'redirect_rules.json');
assert.equal(rule.condition.regexFilter, '^https?://obscura\\.q(/.*)?$');
assert.equal(rule.action.redirect.regexSubstitution,
  'https://0xenos.qstorage.quilibrium.com\\1');
assert.deepEqual(rule.condition.resourceTypes, ['main_frame']);

assert.equal(
  resolveRoute('https://obscura.q/market/item?view=1#orders'),
  'https://0xenos.qstorage.quilibrium.com/market/item?view=1#orders'
);
assert.equal(
  resolveRoute('https://obscura.q/assets/site.css?v=2'),
  'https://0xenos.qstorage.quilibrium.com/assets/site.css?v=2'
);
assert.equal(
  resolveRoute('http://obscura.q/'),
  'https://0xenos.qstorage.quilibrium.com/'
);
assert.equal(resolveRoute('https://unknown.q/'), null);
assert.equal(resolveRoute('https://sub.obscura.q/'), null);
assert.equal(resolveRoute('https://example.com/'), null);
assert.equal(resolveRoute('chrome-extension://abcdefghijklmnop/page.html'), null);

console.log('Extension-only route tests passed.');
