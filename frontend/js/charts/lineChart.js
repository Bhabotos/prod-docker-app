// SVG line chart with zero dependencies. Geometry comes from chartMath.js (pure, tested).
import { svg } from '../dom.js';
import { formatDate, formatNumber } from '../format.js';
import { dayNumber, dayTicks, isoFromDayNumber, linearScale, niceTicks, paddedExtent, pathFromPoints, visibleBands } from './chartMath.js';

const MARGIN = { top: 12, right: 14, bottom: 26, left: 44 };

/**
 * config = {
 *   title, description, unit,
 *   points: [{ date: 'YYYY-MM-DD', value: number }],
 *   target?: { value, label },             // dashed horizontal line
 *   bands?:  [{ category, label, min, max }] // shaded background zones (API supplies the thresholds)
 * }
 */
export function renderLineChart(container, config, width) {
  const W = Math.max(width || container.clientWidth || 640, 280);
  const H = Math.round(Math.min(Math.max(W * 0.5, 200), 320));
  const plot = { x0: MARGIN.left, x1: W - MARGIN.right, y0: H - MARGIN.bottom, y1: MARGIN.top };

  const { points, target, bands } = config;
  const extent = paddedExtent(points.map((p) => p.value), target ? [target.value] : []);
  const yAxis = niceTicks(extent.min, extent.max, 5);
  const y = linearScale(yAxis.min, yAxis.max, plot.y0, plot.y1);

  const days = points.map((p) => dayNumber(p.date));
  const minDay = Math.min(...days);
  const maxDay = Math.max(...days);
  const x = linearScale(minDay, maxDay, plot.x0 + 8, plot.x1 - 8);

  const titleId = `chart-title-${Math.random().toString(36).slice(2, 8)}`;
  const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-labelledby': titleId, focusable: 'false' },
    svg('title', { id: titleId }, `${config.title}. ${config.description ?? ''}`));

  for (const band of visibleBands(bands, yAxis.min, yAxis.max)) {
    root.append(
      svg('rect', { class: `band-${band.category}`, x: plot.x0, width: plot.x1 - plot.x0, y: y(band.high), height: y(band.low) - y(band.high) }),
      svg('text', { class: 'band-label', x: plot.x1 - 4, y: y(band.high) + 12, 'text-anchor': 'end' }, band.label),
    );
  }
  const decimals = Math.min(2, Math.max(0, ...yAxis.ticks.map((t) => (String(t).split('.')[1] ?? '').length)));
  for (const tick of yAxis.ticks) {
    root.append(
      svg('line', { class: 'grid-line', x1: plot.x0, x2: plot.x1, y1: y(tick), y2: y(tick) }),
      svg('text', { class: 'tick-label', x: plot.x0 - 6, y: y(tick) + 4, 'text-anchor': 'end' }, formatNumber(tick, decimals)),
    );
  }
  for (const day of dayTicks(minDay, maxDay, W < 420 ? 3 : 5)) {
    root.append(svg('text', { class: 'tick-label', x: x(day), y: H - 6, 'text-anchor': 'middle' }, formatDate(isoFromDayNumber(day))));
  }
  root.append(svg('line', { class: 'axis', x1: plot.x0, x2: plot.x1, y1: plot.y0, y2: plot.y0 }));

  if (target) {
    root.append(
      svg('line', { class: 'target-line', x1: plot.x0, x2: plot.x1, y1: y(target.value), y2: y(target.value) }),
      svg('text', { class: 'target-label', x: plot.x0 + 4, y: y(target.value) - 4 }, `${target.label} ${formatNumber(target.value, 1)}`),
    );
  }

  const coords = points.map((p) => ({ x: x(dayNumber(p.date)), y: y(p.value), p }));
  if (coords.length > 1) root.append(svg('path', { class: 'chart-line', d: pathFromPoints(coords) }));
  for (const c of coords) {
    root.append(svg('circle', { class: 'chart-point', cx: c.x, cy: c.y, r: 4.5, tabindex: 0 },
      svg('title', {}, `${formatDate(c.p.date, { year: true })}: ${formatNumber(c.p.value, 1)} ${config.unit}`)));
  }

  container.replaceChildren(root);
}

/** Renders now and again whenever the container's width changes. Returns a disposer. */
export function mountChart(container, getConfig) {
  let lastWidth = 0;
  const draw = () => {
    lastWidth = container.clientWidth;
    const config = getConfig();
    if (config.points.length === 0) {
      container.replaceChildren(Object.assign(document.createElement('p'), { className: 'empty', textContent: config.empty ?? 'No data yet.' }));
      return;
    }
    renderLineChart(container, config, lastWidth);
  };
  draw();
  if (typeof ResizeObserver === 'undefined') return () => {};
  const observer = new ResizeObserver(() => { if (Math.abs(container.clientWidth - lastWidth) > 8) draw(); });
  observer.observe(container);
  return () => observer.disconnect();
}
