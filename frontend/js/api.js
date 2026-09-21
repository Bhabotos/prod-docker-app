// Thin client for the FastAPI backend (same origin: nginx maps /api/* to the API).
// It only transports data and translates errors; all validation and calculation is server-side.

export class ApiError extends Error {
  constructor(status, message, fields = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.fields = fields; // { field_name: "message" } for 422 responses
  }
}

const cleanMessage = (msg) => String(msg).replace(/^Value error,\s*/i, '');

/** Turn an error response into { message, fields }. Pure, so it is unit-tested. */
export function parseError(status, payload) {
  const detail = payload?.detail;
  if (Array.isArray(detail)) {
    const fields = {};
    const general = [];
    for (const item of detail) {
      const name = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : undefined;
      const msg = cleanMessage(item.msg ?? 'Invalid value');
      if (typeof name === 'string' && name !== 'body') fields[name] = fields[name] ?? msg;
      else general.push(msg);
    }
    const message = general[0] ?? 'Please correct the highlighted fields.';
    return { message, fields };
  }
  if (typeof detail === 'string') return { message: detail, fields: {} };
  if (status === 429) return { message: 'Too many attempts. Please wait a while and try again.', fields: {} };
  if (status >= 500) return { message: 'The server had a problem. Please try again in a moment.', fields: {} };
  return { message: `Request failed (${status}).`, fields: {} };
}

let unauthorizedHandler = () => {};
export function onUnauthorized(fn) { unauthorizedHandler = fn; }

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.');
  }
  if (response.status === 204) return null;
  let payload = null;
  try { payload = await response.json(); } catch { /* empty or non-JSON body */ }
  if (!response.ok) {
    const { message, fields } = parseError(response.status, payload);
    if (response.status === 401 && !path.startsWith('/auth/login')) unauthorizedHandler();
    throw new ApiError(response.status, message, fields);
  }
  return payload;
}

export const login = (password) => request('POST', '/auth/login', { password });
export const logout = () => request('POST', '/auth/logout');
export const me = () => request('GET', '/auth/me');
export const getLimits = () => request('GET', '/health/limits');
export const getProfile = () => request('GET', '/profile');
export const createProfile = (body) => request('POST', '/profile', body);
export const updateProfile = (body) => request('PUT', '/profile', body);
export const getSummary = () => request('GET', '/health/summary');
export const getHistory = (limit = 365) => request('GET', `/health/history?limit=${limit}`);
export const getMonthly = (months = 12) => request('GET', `/health/monthly?months=${months}`);
export const recordWeight = (body) => request('POST', '/health/weight', body);
export const deleteWeight = (id) => request('DELETE', `/health/weight/${encodeURIComponent(id)}`);
export const createGoal = (body) => request('POST', '/goals', body);
export const updateGoal = (body) => request('PUT', '/goals', body);
