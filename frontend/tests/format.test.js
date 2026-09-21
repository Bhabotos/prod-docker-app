import assert from 'node:assert/strict';
import { test } from 'node:test';
import { formatDate, formatMonth, formatNumber, parseISODate, signed, todayLocalISO } from '../js/format.js';

test('formatNumber', () => {
  assert.equal(formatNumber(26.57, 1), '26.6');
  assert.equal(formatNumber(1635, 0), '1,635');
  assert.equal(formatNumber(75, 1), '75.0');
  assert.equal(formatNumber(null), '—');
  assert.equal(formatNumber(undefined), '—');
  assert.equal(formatNumber('abc'), '—');
});

test('dates are formatted in UTC so they never shift by a day', () => {
  assert.equal(parseISODate('2026-09-05').toISOString(), '2026-09-05T00:00:00.000Z');
  assert.equal(formatDate('2026-09-05'), '05 Sept'.replace('Sept', new Intl.DateTimeFormat('en-GB', { month: 'short', timeZone: 'UTC' }).format(new Date(Date.UTC(2026, 8, 1)))));
  assert.match(formatDate('2026-01-31', { year: true }), /31 Jan 2026/);
  assert.equal(formatDate(''), '—');
  assert.match(formatMonth('2026-08'), /Aug 2026/);
});

test('signed uses a real minus sign and explicit plus', () => {
  assert.equal(signed(-1.5), '−1.5');
  assert.equal(signed(2), '+2.0');
  assert.equal(signed(0), '0.0');
  assert.equal(signed(null), '—');
});

test('todayLocalISO uses the local calendar date', () => {
  assert.equal(todayLocalISO(new Date(2026, 8, 5, 23, 59)), '2026-09-05');
  assert.equal(todayLocalISO(new Date(2026, 0, 1, 0, 0)), '2026-01-01');
});
