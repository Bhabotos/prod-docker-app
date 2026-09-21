import assert from 'node:assert/strict';
import { afterEach, test } from 'node:test';
import * as api from '../js/api.js';

const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; api.onUnauthorized(() => {}); });

const respond = (status, body) => async () => ({ ok: status >= 200 && status < 300, status, json: async () => { if (body === undefined) throw new Error('no body'); return body; } });

test('parseError maps 422 details to fields and strips the pydantic prefix', () => {
  const { message, fields } = api.parseError(422, { detail: [
    { loc: ['body', 'age_years'], msg: 'Value error, Age must be between 18 and 100.' },
    { loc: ['body', 'weight_kg'], msg: 'Input should be a valid number' },
  ] });
  assert.deepEqual(fields, { age_years: 'Age must be between 18 and 100.', weight_kg: 'Input should be a valid number' });
  assert.equal(message, 'Please correct the highlighted fields.');
});

test('parseError keeps string details, and has sensible fallbacks', () => {
  assert.deepEqual(api.parseError(409, { detail: 'A profile already exists.' }), { message: 'A profile already exists.', fields: {} });
  assert.match(api.parseError(429, null).message, /Too many attempts/);
  assert.match(api.parseError(500, null).message, /server had a problem/);
  assert.match(api.parseError(418, null).message, /418/);
  assert.equal(api.parseError(422, { detail: [{ loc: ['body'], msg: 'Field required' }] }).message, 'Field required');
});

test('requests are same-origin, send cookies, and JSON-encode bodies', async () => {
  let seen;
  globalThis.fetch = async (url, init) => { seen = { url, init }; return respond(200, { ok: true })(); };
  await api.recordWeight({ weight_kg: 75 });
  assert.equal(seen.url, '/api/health/weight');
  assert.equal(seen.init.method, 'POST');
  assert.equal(seen.init.credentials, 'same-origin');
  assert.equal(seen.init.headers['Content-Type'], 'application/json');
  assert.equal(seen.init.body, '{"weight_kg":75}');
  await api.getSummary();
  assert.equal(seen.url, '/api/health/summary');
  assert.equal(seen.init.body, undefined);
});

test('204 responses resolve to null', async () => {
  globalThis.fetch = respond(204);
  assert.equal(await api.deleteWeight(7), null);
});

test('errors surface as ApiError with status and per-field messages', async () => {
  globalThis.fetch = respond(422, { detail: [{ loc: ['body', 'height_cm'], msg: 'Value error, Height must be between 100 and 250 cm.' }] });
  await assert.rejects(api.updateProfile({}), (e) => e instanceof api.ApiError && e.status === 422 && e.fields.height_cm === 'Height must be between 100 and 250 cm.');
});

test('a 401 anywhere except login triggers the unauthorised handler', async () => {
  let called = 0;
  api.onUnauthorized(() => { called += 1; });
  globalThis.fetch = respond(401, { detail: 'Not authenticated.' });
  await assert.rejects(api.getSummary(), { status: 401 });
  assert.equal(called, 1);
  await assert.rejects(api.login('wrong'), { status: 401 });
  assert.equal(called, 1, 'a failed login must not bounce back to the login screen');
});

test('network failures become a friendly ApiError', async () => {
  globalThis.fetch = async () => { throw new TypeError('fetch failed'); };
  await assert.rejects(api.getSummary(), (e) => e instanceof api.ApiError && e.status === 0 && /Cannot reach the server/.test(e.message));
});

test('ids in URLs are encoded', async () => {
  let url;
  globalThis.fetch = async (u) => { url = u; return respond(204)(); };
  await api.deleteWeight('1/../2');
  assert.equal(url, '/api/health/weight/1%2F..%2F2');
});
