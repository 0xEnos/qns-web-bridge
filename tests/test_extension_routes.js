'use strict';

const assert = require('node:assert/strict');
const {resolveRoute} = require('../extension/background.js');

assert.equal(
  resolveRoute('https://obscura.q/market/item?view=1#orders'),
  'https://0xenos.qstorage.quilibrium.com/market/item?view=1#orders'
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
