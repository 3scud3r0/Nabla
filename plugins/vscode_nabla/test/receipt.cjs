const {test} = require('node:test');
const assert = require('node:assert/strict');
const {parseReceipt} = require('../out/receipt.js');
test('preview accepts catalog and observation receipts without asserting verification', () => {
    const id = 'a'.repeat(64);
    const value = {schema_version:1, content_id:id, request:{operation:'evaluate'}, result:{value:'2'}};
    assert.deepEqual(parseReceipt(Buffer.from(JSON.stringify(value)), id), value);
    assert.throws(() => parseReceipt(Buffer.from(JSON.stringify(value)), 'b'.repeat(64)));
    assert.throws(() => parseReceipt(Buffer.from('{}')));
    assert.throws(() => parseReceipt(Buffer.alloc(1024*1024+1)));
});
