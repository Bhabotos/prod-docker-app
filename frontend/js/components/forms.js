// Generic form builder. The browser only checks "not empty"; every real rule (ranges, dates, adult ages...)
// is enforced by the API and its message is shown next to the field.
import { ApiError } from '../api.js';
import { h } from '../dom.js';

let uid = 0;

/**
 * fields: [{ name, label, type: 'number'|'text'|'date'|'password'|'select'|'checkbox', options?: [{value,label}],
 *            value?, hint?, step?, min?, max?, required?, maxlength?, autocomplete?, wide? }]
 * Returns { el, focus }.
 */
export function buildForm({ fields, submitLabel, onSubmit, successMessage = 'Saved.' }) {
  const id = `f${uid += 1}`;
  const controls = {};
  const errorEls = {};

  const formError = h('p', { class: 'form-error', role: 'alert', hidden: true });
  const formOk = h('p', { class: 'form-ok', role: 'status', hidden: true });
  const submit = h('button', { class: 'btn', type: 'submit' }, submitLabel);

  const fieldEls = fields.map((f) => {
    const inputId = `${id}-${f.name}`;
    const errId = `${inputId}-err`;
    let control;
    if (f.type === 'select') {
      control = h('select', { id: inputId, name: f.name },
        (f.options ?? []).map((o) => h('option', { value: o.value, selected: o.value === f.value }, o.label)));
    } else if (f.type === 'checkbox') {
      control = h('input', { id: inputId, name: f.name, type: 'checkbox', checked: Boolean(f.value) });
    } else {
      control = h('input', {
        id: inputId, name: f.name, type: f.type, value: f.value ?? '', step: f.step, min: f.min, max: f.max,
        maxlength: f.maxlength, autocomplete: f.autocomplete ?? 'off', inputmode: f.type === 'number' ? 'decimal' : undefined,
      });
    }
    control.setAttribute('aria-describedby', errId);
    controls[f.name] = control;
    errorEls[f.name] = h('p', { class: 'field-error', id: errId, role: 'alert', hidden: true });

    if (f.type === 'checkbox') {
      return h('div', { class: 'field field-check' }, control, h('label', { for: inputId }, f.label), errorEls[f.name]);
    }
    return h('div', { class: f.wide ? 'field field--wide' : 'field' },
      h('label', { for: inputId }, f.label), control,
      f.hint ? h('span', { class: 'hint' }, f.hint) : null, errorEls[f.name]);
  });

  const showFieldError = (name, message) => {
    const el = errorEls[name];
    if (!el) return false;
    el.textContent = message ?? '';
    el.hidden = !message;
    if (message) controls[name].setAttribute('aria-invalid', 'true'); else controls[name].removeAttribute('aria-invalid');
    return true;
  };
  const clearErrors = () => {
    for (const name of Object.keys(errorEls)) showFieldError(name, '');
    formError.hidden = true; formOk.hidden = true;
  };

  const readValues = () => Object.fromEntries(fields.map((f) => {
    const c = controls[f.name];
    if (f.type === 'checkbox') return [f.name, c.checked];
    const raw = c.value.trim();
    if (f.type === 'number') return [f.name, raw === '' ? null : Number(raw.replace(',', '.'))];
    if (f.type === 'password') return [f.name, c.value]; // never trim passwords
    return [f.name, raw === '' ? null : raw];
  }));

  const el = h('form', { novalidate: true, onSubmit: async (event) => {
    event.preventDefault();
    clearErrors();
    const values = readValues();
    let missing = false;
    for (const f of fields) {
      if (f.required && (values[f.name] === null || values[f.name] === '' || Number.isNaN(values[f.name]))) {
        showFieldError(f.name, Number.isNaN(values[f.name]) ? 'Enter a number.' : 'This field is required.');
        missing = true;
      }
    }
    if (missing) { formError.textContent = 'Please correct the highlighted fields.'; formError.hidden = false; return; }

    submit.disabled = true;
    try {
      await onSubmit(values);
      formOk.textContent = successMessage; formOk.hidden = false;
    } catch (error) {
      if (!(error instanceof ApiError)) throw error;
      let unmatched = false;
      for (const [name, message] of Object.entries(error.fields)) unmatched = !showFieldError(name, message) || unmatched;
      if (unmatched || Object.keys(error.fields).length === 0 || error.status !== 422) {
        formError.textContent = error.message; formError.hidden = false;
      } else {
        formError.textContent = 'Please correct the highlighted fields.'; formError.hidden = false;
      }
    } finally {
      submit.disabled = false;
    }
  } }, fields.length > 3 ? [h('div', { class: 'form-row' }, fieldEls)] : fieldEls, formError, formOk, h('div', {}, submit));

  return { el, focus: () => controls[fields[0].name]?.focus() };
}
