/* ==========================================================
   history.modals.js
   Preview modal (full analysis detail) and delete confirm modal.
   Depends on: history.state.js, history.api.js, history.render.js
   Exposes:    window.HSTModals
========================================================== */

window.HSTModals = (function () {
  'use strict';

  const {
    state, CRITERIA,
    getBand, getBandLabel, getBandEmoji,
    getMajorEmoji, barColor, ringColor,
    ringOffset, fmtDate, showToast,
  } = window.HST;

  const { fetchDetail } = window.HSTAPI;
  const { animateCardOut } = window.HSTRender;

  /* ── DOM refs ── */
  const DEL  = document.getElementById('delete-modal');
  const PREV = document.getElementById('preview-modal');

  const delBody      = document.getElementById('del-modal-body');
  const delCancel    = document.getElementById('delete-cancel');
  const delConfirm   = document.getElementById('delete-confirm');
  const prevBody     = document.getElementById('preview-body');
  const prevTitle    = document.getElementById('prev-modal-title');
  const prevClose    = document.getElementById('preview-close');
  const prevClose2   = document.getElementById('preview-close-2');
  const prevExport   = document.getElementById('preview-export');

  /* ════════════════════════════
     MODAL OPEN / CLOSE
  ════════════════════════════ */
  function showModal(el) {
    el.style.display = 'flex';
    requestAnimationFrame(() => el.classList.add('hst-backdrop--visible'));
    document.body.style.overflow = 'hidden';
  }

  function closeModal(el) {
    el.classList.remove('hst-backdrop--visible');
    setTimeout(() => {
      el.style.display = 'none';
      document.body.style.overflow = '';
    }, 260);
  }

  /* ════════════════════════════
     DELETE MODAL
  ════════════════════════════ */
  function openDeleteModal(id, filename) {
    state.pendingDelete = id;
    delBody.textContent =
      `This will permanently remove the analysis for "${filename || 'this CV'}". This cannot be undone.`;
    showModal(DEL);
  }

  function closeDeleteModal() {
    closeModal(DEL);
    state.pendingDelete = null;
  }

  /* Wired later via onDeleteConfirmed callback */
  let _onDeleteConfirmed = null;

  delCancel.addEventListener('click', closeDeleteModal);

  delConfirm.addEventListener('click', async () => {
    if (!state.pendingDelete) return;
    const id = state.pendingDelete;
    closeDeleteModal();
    if (_onDeleteConfirmed) await _onDeleteConfirmed(id);
  });

  DEL.addEventListener('click', e => {
    if (e.target === DEL) closeDeleteModal();
  });

  /* ════════════════════════════
     PREVIEW MODAL
  ════════════════════════════ */
  async function openPreview(id) {
    state.previewId = id;

    /* Show modal immediately with spinner */
    prevBody.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:center;padding:56px">
        <div class="hst-ske" style="width:50px;height:50px;border-radius:50%"></div>
      </div>`;
    showModal(PREV);

    const data = await fetchDetail(id).catch(() => null);
    if (!data) { closeModal(PREV); showToast('Failed to load detail.', 'error'); return; }

    prevTitle.textContent = data.filename || 'Analysis Report';
    prevBody.innerHTML    = buildPreviewBody(data);

    /* Attach export button context */
    prevExport.dataset.id       = id;
    prevExport.dataset.filename = data.filename || `Analysis_${id}`;

    /* Animate ring + bars */
    requestAnimationFrame(() => {
      setTimeout(() => {
        const rf = prevBody.querySelector('.prev-ring__fill');
        if (rf) rf.style.strokeDashoffset = rf.dataset.offset;
        prevBody.querySelectorAll('.prev-crit__fill[data-prev-w]').forEach(el => {
          el.style.width = el.dataset.prevW;
        });
      }, 60);
    });
  }

  function closePreview() {
    closeModal(PREV);
    state.previewId = null;
  }

  function buildPreviewBody(data) {
    const band  = data.score_band || getBand(data.overall_score);
    const score = Math.round(data.overall_score || 0);
    const rc    = ringColor(band);
    const CIRC  = 197.9;   // r=31.5
    const off   = ringOffset(score, CIRC);

    const criteriaHTML = CRITERIA.map(c => {
      const val = Math.round(data[c.key] || 0);
      const col = barColor(val);
      return `
        <div class="prev-crit">
          <div class="prev-crit__head">
            <span class="prev-crit__name">${c.label}</span>
            <span class="prev-crit__weight">${c.weight}</span>
          </div>
          <div class="prev-crit__bar">
            <div class="prev-crit__fill" data-prev-w="${val}%"
                 style="background:${col}"></div>
          </div>
          <span class="prev-crit__score" style="color:${col}">${val}</span>
        </div>`;
    }).join('');

    const missing = (data.missing_keywords || []).slice(0, 20);
    const missingHTML = missing.length
      ? missing.map(k => `<span class="prev-kw">${k}</span>`).join('')
      : '<span style="font-size:12px;color:var(--color-muted)">None missing.</span>';

    const missingSec = data.missing_sections || [];
    const missSecHTML = missingSec.length
      ? missingSec.map(s => `<span class="prev-kw">${s}</span>`).join('')
      : '<span style="font-size:12px;color:#059669">All required sections present.</span>';

    const recsHTML = (data.recommendations || []).map(r => {
      const pColor = r.priority===1 ? '#DC2626' : r.priority===2 ? '#D97706' : '#2563EB';
      const pLabel = r.priority===1 ? 'Critical' : r.priority===2 ? 'Important' : 'Minor';
      return `
        <div style="padding:12px 14px;background:#f8faff;
                    border:1px solid var(--color-border);border-radius:10px">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px">
            <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:999px;
                         background:${pColor}18;color:${pColor};border:1px solid ${pColor}33">
              ${pLabel}
            </span>
            <span style="font-size:12.5px;font-weight:700;color:var(--color-text)">
              ${r.title}
            </span>
          </div>
          <p style="font-size:12px;color:var(--color-muted);margin:0;line-height:1.6">
            ${r.description || ''}
          </p>
        </div>`;
    }).join('');

    return `
      <!-- Score hero -->
      <div class="prev-hero">
        <div class="prev-ring">
          <svg viewBox="0 0 70 70">
            <circle class="prev-ring__track" cx="35" cy="35" r="31.5"/>
            <circle class="prev-ring__fill"
              cx="35" cy="35" r="31.5"
              style="stroke:${rc};stroke-dashoffset:${CIRC}"
              data-offset="${off}"/>
          </svg>
          <div class="prev-ring__label">
            <span class="prev-ring__num" style="color:${rc}">${score}</span>
            <span class="prev-ring__sub">/100</span>
          </div>
        </div>
        <div class="prev-hero-info">
          <h3 class="prev-hero-title">${data.filename || 'CV Analysis'}</h3>
          <div class="prev-hero-band" style="color:${rc}">
            ${getBandEmoji(band)} ${getBandLabel(band)}
          </div>
          <div class="prev-hero-pills">
            <span class="prev-pill">
              ${getMajorEmoji(data.major)}
              ${data.major.charAt(0).toUpperCase() + data.major.slice(1)}
            </span>
            <span class="prev-pill">📅 ${fmtDate(data.created_at)}</span>
          </div>
        </div>
      </div>

      <!-- Criteria -->
      <p class="prev-section-lbl">10-Criteria Breakdown</p>
      <div class="prev-crit-grid">${criteriaHTML}</div>

      <!-- Missing keywords -->
      <p class="prev-section-lbl" style="margin-top:18px">Missing Keywords</p>
      <div class="prev-kw-grid" style="margin-bottom:16px">${missingHTML}</div>

      <!-- Missing sections -->
      <p class="prev-section-lbl">Missing Sections</p>
      <div class="prev-kw-grid" style="margin-bottom:${recsHTML ? '0' : '4px'}">${missSecHTML}</div>

      ${recsHTML ? `
      <!-- AI Recommendations -->
      <p class="prev-section-lbl" style="margin-top:18px">AI Recommendations</p>
      <div style="display:flex;flex-direction:column;gap:8px">${recsHTML}</div>` : ''}`;
  }

  /* Wire close buttons */
  prevClose.addEventListener('click',  closePreview);
  prevClose2.addEventListener('click', closePreview);
  PREV.addEventListener('click', e => { if (e.target === PREV) closePreview(); });

  /* ESC */
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    if (PREV.classList.contains('hst-backdrop--visible')) closePreview();
    if (DEL.classList.contains('hst-backdrop--visible'))  closeDeleteModal();
  });

  /* ── Public ── */
  return {
    openDeleteModal,
    openPreview,
    closePreview,
    prevExport,
    onDeleteConfirmed: (fn) => { _onDeleteConfirmed = fn; },
  };
})();