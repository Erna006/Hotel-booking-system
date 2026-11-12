const base = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';
let token = null;
export function setToken(value) { token = value; }
export async function api(path, {method = 'GET', body, key} = {}) {
  const response = await fetch(`${base}${path}`, {
    method, headers: {'Content-Type': 'application/json', ...(token ? {Authorization: `Bearer ${token}`} : {}), ...(key ? {'Idempotency-Key': key} : {})},
    ...(body !== undefined ? {body: JSON.stringify(body)} : {})
  });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && token) window.dispatchEvent(new Event('session-expired'));
    const byCode = {
      email_taken: 'Этот email уже зарегистрирован.',
      room_number_taken: 'Номер комнаты с таким числом уже существует.',
      self_change_forbidden: 'Нельзя понизить или отключить самого себя.'
    };
    if (byCode[data.error?.code]) throw new Error(byCode[data.error.code]);
    const text = {401: 'Войдите в аккаунт заново.', 403: 'Недостаточно прав.', 409: 'Данные изменились или возник конфликт. Обновите поиск.', 422: 'Проверьте введённые данные.'}[response.status];
    throw new Error(text || data.error?.message || 'Не удалось выполнить запрос');
  }
  return data;
}
