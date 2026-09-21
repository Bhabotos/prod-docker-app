import * as api from './api.js';
import { goalSummary, metricCards, profileCard } from './components/cards.js';
import { buildForm } from './components/forms.js';
import { historyTable, monthlyTable } from './components/tables.js';
import { mountChart } from './charts/lineChart.js';
import { announce, clear, h } from './dom.js';
import { todayLocalISO } from './format.js';

const app = document.getElementById('app');
const logoutButton = document.getElementById('logout');
let limits = null;
let disposers = [];

function resetView() {
  disposers.forEach((dispose) => dispose());
  disposers = [];
  clear(app);
}
const card = (title, ...body) => h('section', { class: 'card' }, h('h2', {}, title), ...body);
const range = (r) => `${r.min}–${r.max}`;

// ---------------------------------------------------------------- login
function showLogin(notice) {
  resetView();
  logoutButton.hidden = true;
  const form = buildForm({
    submitLabel: 'Log in',
    fields: [{ name: 'password', label: 'Password', type: 'password', required: true, autocomplete: 'current-password' }],
    onSubmit: async ({ password }) => { await api.login(password); await afterLogin(); },
    successMessage: 'Logged in.',
  });
  app.append(h('section', { class: 'card card--narrow' }, h('h2', {}, 'Log in'),
    notice ? h('p', { class: 'muted', role: 'status' }, notice) : null, form.el));
  form.focus();
}

// ---------------------------------------------------------------- setup (no profile yet)
function profileFields(initial = {}) {
  return [
    { name: 'age_years', label: 'Age', type: 'number', step: 1, value: initial.age_years, required: true, hint: `Adults ${range(limits.age)}` },
    { name: 'sex', label: 'Sex (used for the BMR formula)', type: 'select', value: initial.sex ?? 'male', options: limits.sexes },
    { name: 'height_cm', label: 'Height (cm)', type: 'number', step: 0.1, value: initial.height_cm, required: true, hint: `${range(limits.height_cm)} cm` },
    { name: 'activity_level', label: 'Activity level', type: 'select', wide: true, value: initial.activity_level ?? 'sedentary',
      options: limits.activity_levels.map((a) => ({ value: a.value, label: a.label })) },
  ];
}

function showSetup() {
  resetView();
  logoutButton.hidden = false;
  const form = buildForm({
    submitLabel: 'Create profile',
    fields: [...profileFields(), { name: 'weight_kg', label: 'Current weight (kg)', type: 'number', step: 0.1, required: true, hint: `${range(limits.weight_kg)} kg` }],
    onSubmit: async (values) => { await api.createProfile({ ...values, recorded_on: todayLocalISO() }); await showDashboard('Profile created.'); },
    successMessage: 'Profile created.',
  });
  app.append(h('section', { class: 'card card--narrow' }, h('h2', {}, 'Set up your profile'),
    h('p', { class: 'muted' }, 'Your figures are used only to estimate BMI, BMR and daily calories.'), form.el));
  form.focus();
}

// ---------------------------------------------------------------- dashboard
async function showDashboard(message) {
  const [summary, history, monthly] = await Promise.all([api.getSummary(), api.getHistory(365), api.getMonthly(12)]);
  resetView();
  logoutButton.hidden = false;
  document.getElementById('disclaimer').textContent = summary.disclaimer;

  const refresh = async (msg) => { await showDashboard(msg); };
  const editSlot = h('div', {});
  const toggleEdit = () => {
    if (editSlot.childElementCount) { clear(editSlot); return; }
    const form = buildForm({
      submitLabel: 'Save profile',
      fields: profileFields(summary.profile),
      onSubmit: async (values) => { await api.updateProfile(values); await refresh('Profile updated.'); },
      successMessage: 'Profile updated.',
    });
    editSlot.append(card('Edit profile', form.el));
    form.focus();
  };

  const weightForm = buildForm({
    submitLabel: 'Save weight',
    fields: [
      { name: 'recorded_on', label: 'Date', type: 'date', value: todayLocalISO(), required: true, hint: 'One entry per day; saving again replaces it' },
      { name: 'weight_kg', label: 'Weight (kg)', type: 'number', step: 0.1, required: true, hint: `${range(limits.weight_kg)} kg` },
      { name: 'note', label: 'Note (optional)', type: 'text', maxlength: limits.note_max_length },
    ],
    onSubmit: async (values) => { await api.recordWeight(values); await refresh('Weight saved.'); },
    successMessage: 'Weight saved.',
  });

  const goal = summary.goal;
  const goalFields = [
    { name: 'target_weight_kg', label: 'Target weight (kg)', type: 'number', step: 0.1, value: goal?.target_weight_kg, required: true, hint: 'Your own target; the dashboard does not recommend one' },
    { name: 'daily_calorie_target', label: 'Daily calorie target (optional)', type: 'number', step: 1, value: goal?.daily_calorie_target, hint: `Your own number, ${range(limits.calorie_target)} kcal` },
  ];
  if (goal) goalFields.push({ name: 'restart_progress', label: 'Restart progress from my latest weight', type: 'checkbox', value: false });
  else goalFields.splice(1, 0, { name: 'starting_weight_kg', label: 'Starting weight (kg, optional)', type: 'number', step: 0.1, hint: 'Leave empty to start from your latest weight' });
  const goalForm = buildForm({
    submitLabel: goal ? 'Update goal' : 'Set goal',
    fields: goalFields,
    onSubmit: async (values) => { await (goal ? api.updateGoal(values) : api.createGoal(values)); await refresh('Goal saved.'); },
    successMessage: 'Goal saved.',
  });

  const weightChart = h('div', { class: 'chart' });
  const bmiChart = h('div', { class: 'chart' });
  const points = (key) => history.entries.map((e) => ({ date: e.recorded_on, value: e[key] }));
  disposers.push(
    mountChart(weightChart, () => ({ title: 'Weight progress', description: 'Weight in kilograms over time.', unit: 'kg', points: points('weight_kg'),
      target: goal ? { value: goal.target_weight_kg, label: 'Target' } : null, empty: 'Record a weight to see your chart.' })),
    mountChart(bmiChart, () => ({ title: 'BMI history', description: 'BMI over time with category zones.', unit: 'BMI', points: points('bmi'),
      bands: history.bmi_bands, empty: 'Record a weight to see your BMI history.' })),
  );

  const onDelete = async (entry) => {
    if (!window.confirm(`Delete the entry from ${entry.recorded_on} (${entry.weight_kg} kg)?`)) return;
    await api.deleteWeight(entry.id);
    await refresh('Entry deleted.');
  };

  app.append(
    profileCard(summary, toggleEdit), editSlot,
    metricCards(summary),
    h('div', { class: 'split' }, card('Record weight', weightForm.el), card('Goals', goalSummary(goal), goalForm.el)),
    h('div', { class: 'split' }, card('Weight progress', weightChart), card('BMI history', bmiChart)),
    card('Weight & BMI history', historyTable(history, onDelete)),
    card('Monthly progress', monthlyTable(monthly)),
  );
  if (message) announce(message);
}

// ---------------------------------------------------------------- boot
async function afterLogin() {
  limits ??= await api.getLimits();
  try {
    await api.getProfile();
  } catch (error) {
    if (error.status === 404) { showSetup(); return; }
    throw error;
  }
  await showDashboard();
}

function showProblem(error) {
  resetView();
  const disabled = error.status === 503;
  app.append(h('section', { class: 'card card--narrow' }, h('h2', {}, disabled ? 'Not available yet' : 'Something went wrong'),
    h('p', { role: 'alert' }, disabled ? 'The dashboard has not been configured on this server yet.' : error.message)));
}

logoutButton.addEventListener('click', async () => {
  try { await api.logout(); } finally { limits = null; showLogin('You have been logged out.'); }
});
api.onUnauthorized(() => showLogin('Your session has expired. Please log in again.'));

(async () => {
  try {
    await api.me();
  } catch (error) {
    if (error.status === 401) { showLogin(); return; }
    showProblem(error); return;
  }
  try { await afterLogin(); } catch (error) { showProblem(error); }
})();
