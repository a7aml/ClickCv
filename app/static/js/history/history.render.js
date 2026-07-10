/* ==========================================================
   history.render.js
   Renders the card list, stats strip, and pagination.
   Depends on: history.state.js (window.HST)
   Exposes:    window.HSTRender
========================================================== */

window.HSTRender = (function () {
  'use strict';

  const {
    state, CRITERIA,
    getBand, getBandLabel, getMajorEmoji,
    barColor, ringColor, ringOffset,
    fmtRelative, animateCount,
  } = window.HST;

  /* ── DOM refs ── */
  const DOM = {
    skeleton:   document.getElementById('skeleton-wrap'),
    list:       document.getElementById('hst-list'),
    empty:      document.getElementById('hst-empty'),
    emptyTitle: document.getElementById('empty-title'),
    emptyText:  document.getElementById('empty-text'),
    pagination: document.getElementById('hst-pagination'),
    statTotal:  document.getElementById('stat-total'),
    statAvg:    document.getElementById('stat-avg'),
    statBest:   document.getElementById('stat-best'),
    statRecent: document.getElementById('stat-recent'),
  };

  /* ════════════════════════════
     SKELETON
  ════════════════════════════ */
  function showSkeleton() {
    DOM.skeleton.style.display = 'flex';
    DOM.list.style.display     = 'none';
    DOM.empty.style.display    = 'none';
  }

  function hideSkeleton() {
    DOM.skeleton.style.display = 'none';
  }

  /* ════════════════════════════
     STATS
  ════════════════════════════ */
  function renderStats(stats) {
    if (!stats) return;
    animateCount(DOM.statTotal, 0, stats.total,          '');
    animateCount(DOM.statAvg,   0, stats.average_score,  '%');
    animateCount(DOM.statBest,  0, stats.best_score,      '%');
    DOM.statRecent.textContent = stats.last_created
      ? fmtRelative(stats.last_created) : '—';
  }

  /* ════════════════════════════
     CARD LIST
  ════════════════════════════ */
  function renderList(analyses) {
    hideSkeleton();

    if (!analyses || !analyses.length) {
      DOM.list.style.display      = 'none';
      DOM.pagination.style.display = 'none';
      DOM.empty.style.display     = 'flex';
      if (state.search) {
        DOM.emptyTitle.textContent = 'No results found';
        DOM.emptyText.textContent  = `No analyses match "${state.search}".`;
      } else {
        DOM.emptyTitle.textContent = 'No analyses yet';
        DOM.emptyText.textContent  = 'Upload your first CV to get an ATS score.';
      }
      return;
    }

    DOM.empty.style.display = 'none';
    DOM.list.style.display  = 'flex';
    DOM.list.innerHTML = analyses.map((a, i) => buildCard(a, i)).join('');

    /* Trigger ring + bar animations */
    requestAnimationFrame(() => {
      document.querySelectorAll('.hst-ring__fill[data-offset]').forEach(el => {
        el.style.strokeDashoffset = el.dataset.offset;
      });
      document.querySelectorAll('.hst-mini-bar__fill[data-w]').forEach(el => {
        el.style.width = el.dataset.w;
      });
    });
  }

  /* ── Build one card ── */
  function buildCard(a, idx) {
    const band   = a.score_band || getBand(a.overall_score);
    const score  = Math.round(a.overall_score || 0);
    const ext    = (a.filename || '').split('.').pop().toLowerCase() || 'pdf';
    const isPdf  = ext === 'pdf';
    const rc     = ringColor(band);
    const CIRC   = 131.9;                        // r=21
    const offset = ringOffset(score, CIRC);

    return `
      <div class="hst-card" id="hst-card-${a.analysis_id}"
           data-id="${a.analysis_id}" role="listitem"
           style="animation:hstCardIn .4s ${idx * 0.06}s ease both">

        <div class="hst-card__row">

          <!-- File icon -->
          <div class="hst-card__file hst-card__file--${isPdf ? 'pdf' : 'docx'}">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                 stroke="${isPdf ? '#B91C1C' : '#1D4ED8'}"
                 stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span class="hst-card__file-badge">${ext.toUpperCase()}</span>
          </div>

          <!-- Info -->
          <div class="hst-card__info">
            <p class="hst-card__name" title="${a.filename}">${a.filename || 'CV Analysis'}</p>
            <div class="hst-card__meta">
              <span class="hst-card__major-pill">
                ${getMajorEmoji(a.major)}
                ${a.major.charAt(0).toUpperCase() + a.major.slice(1)}
              </span>
              <span class="hst-card__time">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none"
                     stroke="currentColor" stroke-width="2.5"
                     stroke-linecap="round" stroke-linejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="12 6 12 12 16 14"/>
                </svg>
                ${fmtRelative(a.created_at)}
              </span>
              ${a.rec_count
                ? `<span class="hst-card__time">${a.rec_count} suggestion${a.rec_count !== 1 ? 's' : ''}</span>`
                : ''}
            </div>
          </div>

          <!-- Score ring -->
          <div class="hst-card__score-wrap">
            <div class="hst-ring">
              <svg viewBox="0 0 46 46">
                <circle class="hst-ring__track" cx="23" cy="23" r="21"/>
                <circle class="hst-ring__fill band--${band}"
                  cx="23" cy="23" r="21"
                  data-offset="${offset}"
                  style="stroke-dashoffset:${CIRC};stroke:${rc}"/>
              </svg>
              <div class="hst-ring__num band--${band}">${score}</div>
            </div>
            <span class="hst-card__band band--${band}">${getBandLabel(band)}</span>
          </div>

          <!-- Mini bars (top 4 criteria) -->
          <div class="hst-card__bars">${buildMiniBars(a)}</div>

          <!-- Actions -->
          <div class="hst-card__actions">
            <button class="hst-btn hst-btn--preview" type="button"
                    data-action="preview" data-id="${a.analysis_id}" title="Preview analysis">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                <circle cx="12" cy="12" r="3"/>
              </svg>
              Preview
            </button>
            <button class="hst-btn hst-btn--export" type="button"
                    data-action="export" data-id="${a.analysis_id}"
                    data-filename="${a.filename}" title="Export PDF">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              Export
            </button>
            <button class="hst-btn hst-btn--rebuild" type="button"
                    data-action="rebuild" data-id="${a.analysis_id}"
                    title="Rebuild this CV with AI">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round" stroke-linejoin="round">
                <polyline points="23 4 23 10 17 10"/>
                <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
              </svg>
              Rebuild
            </button>
            <button class="hst-btn hst-btn--delete" type="button"
                    data-action="delete" data-id="${a.analysis_id}"
                    data-filename="${a.filename}" title="Delete"
                    aria-label="Delete analysis for ${a.filename}">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"/>
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                <path d="M10 11v6"/><path d="M14 11v6"/>
              </svg>
            </button>
            <button class="hst-btn--expand" type="button"
                    data-action="expand" data-id="${a.analysis_id}"
                    aria-label="Expand all criteria" title="Expand criteria">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.5"
                   stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Expanded detail panel -->
        <div class="hst-card__detail">
          <div class="hst-card__detail-inner">
            ${buildExpandedCriteria(a)}
            ${buildMissingKeywords(a)}
          </div>
        </div>
      </div>`;
  }

  function buildMiniBars(a) {
    return CRITERIA.slice(0, 4).map(c => {
      const val = Math.round(a[c.key] || 0);
      const col = barColor(val);
      return `
        <div class="hst-mini-bar">
          <span class="hst-mini-bar__label">${c.label}</span>
          <div class="hst-mini-bar__track">
            <div class="hst-mini-bar__fill" data-w="${val}%"
                 style="background:${col}"></div>
          </div>
          <span class="hst-mini-bar__val" style="color:${col}">${val}</span>
        </div>`;
    }).join('');
  }

  function buildExpandedCriteria(a) {
    return CRITERIA.map(c => {
      const val = Math.round(a[c.key] || 0);
      const col = barColor(val);
      return `
        <div class="hst-detail-crit">
          <span class="hst-detail-crit__name">${c.label}</span>
          <div class="hst-detail-crit__track">
            <div class="hst-detail-crit__fill"
                 data-expand-w="${val}%"
                 style="background:${col}"></div>
          </div>
          <span class="hst-detail-crit__score" style="color:${col}">${val}</span>
        </div>`;
    }).join('');
  }

  function buildMissingKeywords(a) {
    const kws = (a.missing_keywords || []).slice(0, 12);
    const pills = kws.length
      ? kws.map(k => `<span class="hst-kw-pill">${k}</span>`).join('')
      : '<span style="font-size:12px;color:var(--color-muted)">No critical keywords missing.</span>';
    return `
      <div class="hst-detail-kw-row">
        <span class="hst-detail-kw-label">Missing keywords</span>
        ${pills}
      </div>`;
  }

  /* ── Expand / collapse card ── */
  function toggleExpand(id) {
    const card = document.getElementById(`hst-card-${id}`);
    if (!card) return;
    const isOpen = card.classList.contains('hst-card--open');
    document.querySelectorAll('.hst-card--open').forEach(c =>
      c.classList.remove('hst-card--open')
    );
    if (!isOpen) {
      card.classList.add('hst-card--open');
      requestAnimationFrame(() => {
        card.querySelectorAll('.hst-detail-crit__fill[data-expand-w]').forEach(el => {
          el.style.width = el.dataset.expandW;
        });
      });
    }
  }

  /* ── Animate card out before delete ── */
  function animateCardOut(id) {
    const card = document.getElementById(`hst-card-${id}`);
    if (!card) return;
    card.style.transition = 'opacity .3s, transform .3s, max-height .4s, margin .3s, padding .3s';
    card.style.opacity    = '0';
    card.style.transform  = 'translateX(20px) scale(.97)';
    card.style.maxHeight  = card.offsetHeight + 'px';
    setTimeout(() => {
      card.style.maxHeight   = '0';
      card.style.padding     = '0';
      card.style.margin      = '0';
      card.style.borderWidth = '0';
    }, 280);
    setTimeout(() => card.remove(), 680);
  }

  /* ════════════════════════════
     PAGINATION
  ════════════════════════════ */
  function renderPagination(total, totalPages, onPageChange) {
    if (totalPages <= 1) {
      DOM.pagination.style.display = 'none';
      return;
    }
    DOM.pagination.style.display = 'flex';

    let html = `
      <button class="hst-pag-btn" id="pag-prev"
              ${state.page === 1 ? 'disabled' : ''}
              aria-label="Previous page">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round">
          <polyline points="15 18 9 12 15 6"/>
        </svg>
      </button>`;

    for (let p = 1; p <= totalPages; p++) {
      const active = p === state.page;
      html += `<button class="hst-pag-btn ${active ? 'hst-pag-btn--active' : ''}"
                       data-pag="${p}"
                       aria-label="Page ${p}"
                       ${active ? 'aria-current="page"' : ''}>${p}</button>`;
    }

    html += `
      <button class="hst-pag-btn" id="pag-next"
              ${state.page === totalPages ? 'disabled' : ''}
              aria-label="Next page">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </button>`;

    DOM.pagination.innerHTML = html;

    document.getElementById('pag-prev')?.addEventListener('click', () => {
      if (state.page > 1) onPageChange(state.page - 1);
    });
    document.getElementById('pag-next')?.addEventListener('click', () => {
      if (state.page < totalPages) onPageChange(state.page + 1);
    });
    DOM.pagination.querySelectorAll('[data-pag]').forEach(btn =>
      btn.addEventListener('click', () => onPageChange(parseInt(btn.dataset.pag)))
    );
  }

  /* ── Public ── */
  return {
    showSkeleton, hideSkeleton,
    renderStats, renderList,
    toggleExpand, animateCardOut,
    renderPagination,
  };
})();