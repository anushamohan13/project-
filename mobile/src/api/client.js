import * as SecureStore from 'expo-secure-store';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api';
let refreshPromise = null;

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const refreshToken = await SecureStore.getItemAsync('refresh_token');
      if (!refreshToken) throw new Error('Your session has expired. Please sign in again.');
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        await SecureStore.deleteItemAsync('access_token');
        await SecureStore.deleteItemAsync('refresh_token');
        throw new Error('Your session has expired. Please sign in again.');
      }
      const pair = await response.json();
      await SecureStore.setItemAsync('access_token', pair.access_token);
      await SecureStore.setItemAsync('refresh_token', pair.refresh_token);
      return pair.access_token;
    })().finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

async function request(path, options = {}, retry = true) {
  const token = await SecureStore.getItemAsync('access_token');
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (response.status === 401 && retry && !path.startsWith('/auth/')) {
    await refreshAccessToken();
    return request(path, options, false);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join(', ') : body.detail;
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) return null;
  return response.json();
}

const json = (method, payload) => ({ method, body: JSON.stringify(payload) });

export const api = {
  devLogin: (email, username) => request('/auth/dev-login', json('POST', { email, username })),
  googleLogin: (idToken, username = null) => request('/auth/google', json('POST', { id_token: idToken, username })),
  logout: (refreshToken) => request('/auth/logout', json('POST', { refresh_token: refreshToken })),

  getProfile: () => request('/profile'),
  updateProfile: (payload) => request('/profile', json('PUT', payload)),

  listCategories: () => request('/categories'),
  createCategory: (payload) => request('/categories', json('POST', payload)),
  updateCategory: (id, payload) => request(`/categories/${id}`, json('PUT', payload)),
  deleteCategory: (id) => request(`/categories/${id}`, { method: 'DELETE' }),

  listIncome: () => request('/income-streams'),
  createIncome: (payload) => request('/income-streams', json('POST', payload)),
  updateIncome: (id, payload) => request(`/income-streams/${id}`, json('PUT', payload)),
  deleteIncome: (id) => request(`/income-streams/${id}`, { method: 'DELETE' }),

  listRecurringExpenses: () => request('/recurring-expenses'),
  createRecurringExpense: (payload) => request('/recurring-expenses', json('POST', payload)),
  updateRecurringExpense: (id, payload) => request(`/recurring-expenses/${id}`, json('PUT', payload)),
  deleteRecurringExpense: (id) => request(`/recurring-expenses/${id}`, { method: 'DELETE' }),

  listActivities: (params = '') => request(`/activities${params}`),
  createActivity: (payload) => request('/activities', json('POST', payload)),
  updateActivity: (id, payload) => request(`/activities/${id}`, json('PUT', payload)),
  deleteActivity: (id) => request(`/activities/${id}`, { method: 'DELETE' }),

  listTransactions: (params = '') => request(`/transactions${params}`),
  createTransaction: (payload) => request('/transactions', json('POST', payload)),
  updateTransaction: (id, payload) => request(`/transactions/${id}`, json('PUT', payload)),
  deleteTransaction: (id) => request(`/transactions/${id}`, { method: 'DELETE' }),
  transactionSummary: (params = '') => request(`/transactions/summary${params}`),

  calculateBudget: (payload) => request('/budgets/calculate', json('POST', payload)),
  confirmBudget: (payload) => request('/budgets/confirm', json('POST', payload)),
  latestBudget: () => request('/budgets/latest'),
  budgetHistory: () => request('/budgets/history'),
  compareBudgets: (leftId, rightId) => request(`/budgets/compare?left_id=${encodeURIComponent(leftId)}&right_id=${encodeURIComponent(rightId)}`),

  createWishlist: (payload) => request('/wishlist', json('POST', payload)),
  listWishlist: () => request('/wishlist'),
  updateWishlist: (id, payload) => request(`/wishlist/${id}`, json('PUT', payload)),
  deleteWishlist: (id) => request(`/wishlist/${id}`, { method: 'DELETE' }),
  addWishlistContribution: (id, payload) => request(`/wishlist/${id}/contributions`, json('POST', payload)),

  widgetSnapshot: () => request('/widget/snapshot'),

  getNotificationPreferences: () => request('/notifications/preferences'),
  updateNotificationPreferences: (payload) => request('/notifications/preferences', json('PUT', payload)),
  registerPushToken: (payload) => request('/notifications/push-tokens', json('POST', payload)),
  queueWeeklyReminder: () => request('/notifications/queue-weekly-reminder', { method: 'POST' }),

  createConversation: (payload = { title: 'Financial assistant', mode: 'action' }) => request('/chat/conversations', json('POST', payload)),
  getConversation: (id) => request(`/chat/conversations/${id}`),
  sendConversationMessage: (id, message, mode = 'action') => request(`/chat/conversations/${id}/messages`, json('POST', { message, mode })),
  chat: (message) => request('/chat/messages', json('POST', { message })),
  getProposal: (id) => request(`/chat/proposals/${id}`),
  confirmProposal: (id) => request(`/chat/proposals/${id}/confirm`, { method: 'POST' }),
  rejectProposal: (id) => request(`/chat/proposals/${id}/reject`, { method: 'POST' }),
  reverseProposal: (id) => request(`/chat/proposals/${id}/reverse`, { method: 'POST' }),
  recalculateProposal: (id) => request(`/chat/proposals/${id}/recalculate`, { method: 'POST' }),
};
