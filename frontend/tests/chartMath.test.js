import assert from 'node:assert/strict';
import { test } from 'node:test';
import { dayNumber, dayTicks, isoFromDayNumber, linearScale, niceTicks, paddedExtent, pathFromPoints, visibleBands } from '../js/charts/chartMath.js';

test('niceTicks returns round, ordered ticks that cover the data', () => {
  const { ticks, min, max } = niceTicks(72.3, 77.8, 5);
  assert.ok(min <= 72.3 && max >= 77.8);
  assert.deepEqual(ticks, [...ticks].sort((a, b) => a - b));
  const steps = ticks.slice(1).map((t, i) => Number((t - ticks[i]).toFixed(6)));
  assert.equal(new Set(steps).size, 1, 'equal spacing');
  assert.ok([1, 2, 2.5, 5, 10].includes(steps[0]) || Number.isInteger(steps[0] * 10), `round step ${steps[0]}`);
});

test('niceTicks handles a flat series and invalid input', () => {
  const flat = niceTicks(75, 75);
  assert.ok(flat.min < 75 && flat.max > 75 && flat.ticks.length >= 2);
  assert.deepEqual(niceTicks(NaN, 1).ticks, []);
});

test('linearScale maps the domain onto the range and centres a zero-width domain', () => {
  const s = linearScale(0, 10, 100, 0); // inverted, like an SVG y axis
  assert.equal(s(0), 100);
  assert.equal(s(10), 0);
  assert.equal(s(5), 50);
  assert.equal(linearScale(3, 3, 0, 200)(3), 100);
});

test('dayNumber is timezone independent and round-trips', () => {
  assert.equal(dayNumber('1970-01-02'), 1);
  assert.equal(dayNumber('2026-03-29') - dayNumber('2026-03-28'), 1); // across a DST change in many zones
  assert.equal(isoFromDayNumber(dayNumber('2026-09-05')), '2026-09-05');
});

test('dayTicks spreads whole days and collapses when there is one day', () => {
  assert.deepEqual(dayTicks(10, 10), [10]);
  assert.deepEqual(dayTicks(0, 30, 4), [0, 10, 20, 30]);
  assert.equal(new Set(dayTicks(0, 1, 5)).size, dayTicks(0, 1, 5).length, 'no duplicate ticks on a short range');
});

test('pathFromPoints builds an SVG path', () => {
  assert.equal(pathFromPoints([{ x: 1, y: 2 }, { x: 3.14159, y: 4 }]), 'M1.0 2.0 L3.1 4.0');
  assert.equal(pathFromPoints([]), '');
});

test('visibleBands clips open-ended bands and drops the ones outside the view', () => {
  const bands = [
    { category: 'underweight', label: 'U', min: null, max: 18.5 },
    { category: 'normal', label: 'N', min: 18.5, max: 25 },
    { category: 'overweight', label: 'O', min: 25, max: 30 },
    { category: 'obesity', label: 'B', min: 30, max: null },
  ];
  const seen = visibleBands(bands, 20, 28);
  assert.deepEqual(seen.map((b) => [b.category, b.low, b.high]), [['normal', 20, 25], ['overweight', 25, 28]]);
  assert.deepEqual(visibleBands(null, 0, 1), []);
});

test('paddedExtent adds headroom, includes extras such as a target, and copes with empty data', () => {
  const e = paddedExtent([75, 77], [70]);
  assert.ok(e.min < 70 && e.max > 77);
  assert.deepEqual(paddedExtent([]), { min: 0, max: 1 });
  const flat = paddedExtent([75]);
  assert.ok(flat.min < 75 && flat.max > 75);
});
