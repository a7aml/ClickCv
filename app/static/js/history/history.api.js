/* ==========================================================
   history.api.js
   All HTTP calls to history_routes.py.
   Depends on: history.state.js (window.HST)
   Exposes:    window.HSTAPI
========================================================== */

window.HSTAPI = (function () {
  'use strict';

  const { getToken, showToast } = window.HST;

  /* ── Base fetch wrapper ── */
  async function apiFetch(url, opts = {}) {
    const res = await fetch(url, {
      ...opts,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getToken()}`,
        ...(opts.headers || {}),
      },
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  /* ── GET /history/analyses ── */
  async function fetchAnalyses({ sort, page, perPage, filter }) {
    const params = new URLSearchParams({ sort, page, per_page: perPage });
    if (filter && filter !== 'all') params.set('major', filter);
    return apiFetch(`/history/analyses?${params}`);
  }

  /* ── GET /history/analyses/<id> ── */
  async function fetchDetail(id) {
    return apiFetch(`/history/analyses/${id}`);
  }

  /* ── DELETE /history/analyses/<id> ── */
  async function deleteAnalysis(id) {
    return apiFetch(`/history/analyses/${id}`, { method: 'DELETE' });
  }

  /* ── GET /auth/me ── */
  async function fetchUser() {
    return apiFetch('/auth/me');
  }

  /* ── Public ── */
  return { fetchAnalyses, fetchDetail, deleteAnalysis, fetchUser };
})();