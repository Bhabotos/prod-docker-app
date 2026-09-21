import { h } from '../dom.js';
import { formatDate, formatNumber, signed } from '../format.js';

const STATUS_TEXT = {
  in_progress: 'In progress',
  achieved: 'Target reached',
  behind: 'Currently moving away from the target',
  target_equals_start: 'Target equals your starting weight',
  no_data: 'Record a weight to see progress',
};

function metric(label, value, unit, note, extra) {
  return h('article', { class: 'card metric' },
    h('div', { class: 'label' }, label),
    h('div', { class: 'value' }, value, unit ? h('span', { class: 'unit' }, unit) : null),
    extra ?? null,
    note ? h('div', { class: 'note' }, note) : null);
}

export function profileCard(summary, onEdit) {
  const { profile, latest_weight: latest } = summary;
  const sex = profile.sex === 'male' ? 'Male' : 'Female';
  return h('section', { class: 'card', 'aria-labelledby': 'profile-h' },
    h('div', { class: 'card-head' },
      h('h2', { id: 'profile-h' }, 'Profile'),
      h('button', { class: 'btn btn--ghost btn--small', type: 'button', onClick: onEdit }, 'Edit profile')),
    h('dl', { class: 'profile-list' },
      h('div', {}, h('dt', {}, 'Age'), h('dd', {}, `${profile.age_years}`)),
      h('div', {}, h('dt', {}, 'Sex'), h('dd', {}, sex)),
      h('div', {}, h('dt', {}, 'Height'), h('dd', {}, `${formatNumber(profile.height_cm, 0)} cm`)),
      h('div', {}, h('dt', {}, 'Weight'), h('dd', {}, latest ? `${formatNumber(latest.weight_kg, 1)} kg` : '—'),
        latest ? h('span', { class: 'muted' }, ` ${formatDate(latest.recorded_on)}`) : null)));
}

export function metricCards(summary) {
  const { metrics, goal } = summary;
  const cards = [];
  if (metrics) {
    cards.push(metric('BMI', formatNumber(metrics.bmi, 1), 'kg/m²', 'Estimate: weight ÷ height²',
      h('span', { class: `badge badge--${metrics.bmi_category}` }, metrics.bmi_category_label)));
    cards.push(metric('BMR', formatNumber(metrics.bmr_kcal, 0), 'kcal/day', 'Estimate (Mifflin-St Jeor)'));
    cards.push(metric('Daily calories', formatNumber(metrics.daily_calories_kcal, 0), 'kcal/day',
      `Maintenance estimate: BMR × ${metrics.activity_factor}`));
  } else {
    cards.push(h('article', { class: 'card metric' }, h('div', { class: 'label' }, 'Metrics'),
      h('p', { class: 'muted' }, 'Record your weight to see BMI, BMR and daily calories.')));
  }
  cards.push(metric('Target weight', goal ? formatNumber(goal.target_weight_kg, 1) : '—', goal ? 'kg' : '',
    goal ? (goal.progress.remaining_kg == null ? null : `${signed(goal.progress.remaining_kg)} kg from target`) : 'Set a goal below'));

  const pct = goal?.progress.progress_percent;
  // Width is set through the CSSOM: the page's CSP (style-src 'self') forbids inline style="" attributes.
  const fill = h('span', {});
  if (pct != null) fill.style.width = `${pct}%`;
  const bar = pct == null ? null : h('div', { class: 'progress', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct, 'aria-label': 'Progress towards target weight' }, fill);
  cards.push(metric('Progress', pct == null ? '—' : formatNumber(pct, 1), pct == null ? '' : '%', goal ? STATUS_TEXT[goal.progress.status] : 'No goal yet', bar));
  return h('div', { class: 'grid grid--metrics' }, cards);
}

export function goalSummary(goal) {
  if (!goal) return null;
  return h('div', {},
    h('dl', { class: 'profile-list' },
      h('div', {}, h('dt', {}, 'Starting weight'), h('dd', {}, `${formatNumber(goal.starting_weight_kg, 1)} kg`)),
      h('div', {}, h('dt', {}, 'Target weight'), h('dd', {}, `${formatNumber(goal.target_weight_kg, 1)} kg`)),
      h('div', {}, h('dt', {}, 'Daily calories (your target)'), h('dd', {}, goal.daily_calorie_target ? `${formatNumber(goal.daily_calorie_target, 0)} kcal` : 'Not set')),
      h('div', {}, h('dt', {}, 'Maintenance estimate'), h('dd', {}, goal.daily_calorie_requirement ? `${formatNumber(goal.daily_calorie_requirement, 0)} kcal` : '—'))),
    ...goal.warnings.map((w) => h('p', { class: 'muted', role: 'note' }, w)));
}
