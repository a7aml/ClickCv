/* ==========================================================
   history.main.js
   Boot file — wires all modules together.
   Load order in history.html:
     1. history.state.js
     2. history.api.js
     3. history.render.js
     4. history.modals.js
     5. history.export.js
     6. history.main.js   ← this file (last)
========================================================== */
(function () {
  'use strict';

  /* ── Destructure modules ── */
  const {
    state, getToken,
    applyClientSearch, showToast,
  } = window.HST;

  const { fetchAnalyses, fetchUser, deleteAnalysis } = window.HSTAPI;

  const {
    showSkeleton, hideSkeleton,
    renderStats, renderList,
    toggleExpand, animateCardOut,
    renderPagination,
  } = window.HSTRender;

  const {
    openDeleteModal, openPreview,
    prevExport, onDeleteConfirmed,
  } = window.HSTModals;

  const { exportPdf } = window.HSTExport;

  /* ── DOM refs ── */
  const filterChips = document.getElementById('filter-chips');
  const sortSelect  = document.getElementById('sort-select');
  const searchInput = document.getElementById('search-input');
  const topbar      = document.getElementById('topbar');
  const mainEl      = document.querySelector('.hst-main');
  const histList    = document.getElementById('hst-list');

  /* ════════════════════════════
     AUTH CHECK
  ════════════════════════════ */
  if (!getToken()) {
    window.location.href = '/login';
    return;
  }

  /* ════════════════════════════
     DATA LOADING
  ════════════════════════════ */
  async function loadPage() {
    showSkeleton();
    try {
      const data = await fetchAnalyses({
        sort:    state.sort,
        page:    state.page,
        perPage: state.perPage,
        filter:  state.filter,
      });

      /* Cache for client-side search */
      state.allLoaded  = data.analyses;
      state.totalPages = data.total_pages;

      renderStats(data.stats);
      renderList(applyClientSearch(data.analyses, state.search));
      renderPagination(data.total, data.total_pages, goToPage);

    } catch (err) {
      hideSkeleton();
      showToast('Failed to load history. Please refresh.', 'error');
      console.error('[history.main] loadPage:', err);
    }
  }

  function goToPage(page) {
    state.page = page;
    loadPage();
    mainEl?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ════════════════════════════
     DELETE FLOW
  ════════════════════════════ */
  onDeleteConfirmed(async (id) => {
    animateCardOut(id);
    try {
      await deleteAnalysis(id);
      showToast('Analysis deleted.', 'success');
      /* Reload to refresh stats + pagination */
      setTimeout(loadPage, 700);
    } catch (err) {
      showToast('Delete failed. Please try again.', 'error');
      console.error('[history.main] delete:', err);
      loadPage(); // restore card
    }
  });

  /* ════════════════════════════
     EVENT DELEGATION — card actions
  ════════════════════════════ */
  histList.addEventListener('click', e => {
    const btn = e.target.closest('[data-action]');
    if (!btn) return;
    const { action, id, filename } = btn.dataset;
    const numId = parseInt(id);

    switch (action) {
      case 'preview': openPreview(numId);                              break;
      case 'export':  exportPdf(numId, filename);                      break;
      case 'delete':  openDeleteModal(numId, filename);                break;
      case 'expand':  toggleExpand(numId);                             break;
      case 'rebuild': window.location.href = `/rebuild?analysis_id=${numId}`; break;
    }
  });

  /* Preview modal export button */
  prevExport.addEventListener('click', () => {
    const id       = parseInt(prevExport.dataset.id);
    const filename = prevExport.dataset.filename;
    if (id) exportPdf(id, filename);
  });

  /* ════════════════════════════
     FILTER · SORT · SEARCH
  ════════════════════════════ */
  filterChips.addEventListener('click', e => {
    const chip = e.target.closest('.hst-chip');
    if (!chip) return;
    filterChips.querySelectorAll('.hst-chip').forEach(c =>
      c.classList.remove('hst-chip--active')
    );
    chip.classList.add('hst-chip--active');
    state.filter = chip.dataset.filter;
    state.page   = 1;
    loadPage();
  });

  sortSelect.addEventListener('change', () => {
    state.sort = sortSelect.value;
    state.page = 1;
    loadPage();
  });

  let searchTimer;
  searchInput.addEventListener('input', () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      state.search = searchInput.value;
      /* Client-side — no API call needed */
      renderList(applyClientSearch(state.allLoaded, state.search));
    }, 280);
  });

  /* ════════════════════════════
     TOPBAR SCROLL SHADOW
  ════════════════════════════ */
  if (mainEl && topbar) {
    mainEl.addEventListener('scroll', () =>
      topbar.classList.toggle('scrolled', mainEl.scrollTop > 8)
    );
  }

  /* ════════════════════════════
     LOAD USER INFO
  ════════════════════════════ */
  async function loadUser() {
    try {
      const data = await fetchUser();
      const name = data.name || data.username || 'User';
      const avatarEl   = document.getElementById('hist-avatar');
      const usernameEl = document.getElementById('hist-username');
      if (usernameEl) usernameEl.textContent = name;
      if (avatarEl)   avatarEl.textContent   = name.charAt(0).toUpperCase();
    } catch (_) { /* non-critical — leave default */ }
  }

  /* ════════════════════════════
     BOOT
  ════════════════════════════ */
  loadUser();
  loadPage();

})();