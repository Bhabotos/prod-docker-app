import { h } from '../dom.js';
import { formatDate, formatMonth, formatNumber, signed } from '../format.js';

export function historyTable(history, onDelete) {
  if (history.entries.length === 0) return h('p', { class: 'empty' }, 'No weight entries yet.');
  const rows = [...history.entries].reverse().map((e) => h('tr', {},
    h('td', { 'data-label': 'Date' }, formatDate(e.recorded_on, { year: true })),
    h('td', { class: 'num', 'data-label': 'Weight' }, `${formatNumber(e.weight_kg, 1)} kg`),
    h('td', { class: 'num', 'data-label': 'BMI' }, formatNumber(e.bmi, 1)),
    h('td', { 'data-label': 'Category' }, h('span', { class: `badge badge--${e.bmi_category}` }, e.bmi_category_label)),
    h('td', { 'data-label': 'Note' }, e.note ?? ''),
    h('td', { 'data-label': '' }, h('button', { class: 'btn btn--danger btn--small', type: 'button',
      'aria-label': `Delete entry from ${formatDate(e.recorded_on, { year: true })}`, onClick: () => onDelete(e) }, 'Delete'))));
  return h('div', { class: 'table-wrap' }, h('table', { class: 'stack' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Date'), h('th', { class: 'num' }, 'Weight'), h('th', { class: 'num' }, 'BMI'), h('th', {}, 'Category'), h('th', {}, 'Note'), h('th', {}, h('span', { class: 'sr-only' }, 'Actions')))),
    h('tbody', {}, rows)));
}

export function monthlyTable(monthly) {
  if (monthly.months.length === 0) return h('p', { class: 'empty' }, 'Monthly progress appears once you have entries.');
  const rows = [...monthly.months].reverse().map((m) => h('tr', {},
    h('td', { 'data-label': 'Month' }, formatMonth(m.month)),
    h('td', { class: 'num', 'data-label': 'Entries' }, String(m.entries)),
    h('td', { class: 'num', 'data-label': 'Start' }, `${formatNumber(m.first_weight_kg, 1)} kg`),
    h('td', { class: 'num', 'data-label': 'End' }, `${formatNumber(m.last_weight_kg, 1)} kg`),
    h('td', { class: 'num', 'data-label': 'Change' }, `${signed(m.change_kg)} kg`),
    h('td', { class: 'num', 'data-label': 'Average' }, `${formatNumber(m.average_weight_kg, 1)} kg`)));
  return h('div', { class: 'table-wrap' }, h('table', { class: 'stack' },
    h('thead', {}, h('tr', {}, h('th', {}, 'Month'), h('th', { class: 'num' }, 'Entries'), h('th', { class: 'num' }, 'Start'), h('th', { class: 'num' }, 'End'), h('th', { class: 'num' }, 'Change'), h('th', { class: 'num' }, 'Average'))),
    h('tbody', {}, rows)));
}
