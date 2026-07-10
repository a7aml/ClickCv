/* ==========================================================
   history.state.js
   Shared state, constants, and pure helper functions.
   Imported by all other history modules via window.HST.
   No DOM access — no side effects.
========================================================== */

window.HST = (function () {
  'use strict';

  /* ── Shared state ── */
  const state = {
    allLoaded:     [],    // full page of analyses from last API call
    filter:        'all',
    sort:          'date_desc',
    search:        '',
    page:          1,
    perPage:       10,
    totalPages:    1,
    pendingDelete: null,  // analysis_id awaiting confirm
    previewId:     null,  // analysis_id currently in preview
  };

  /* ── Criteria metadata ── */
  const CRITERIA = [
    { key: 'keyword_score',            label: 'Keywords',   weight: '35%' },
    { key: 'keyword_placement_score',  label: 'Placement',  weight: '18%' },
    { key: 'formatting_score',         label: 'Formatting', weight: '17%' },
    { key: 'structure_score',          label: 'Sections',   weight: '12%' },
    { key: 'experience_recency_score', label: 'Recency',    weight: '10%' },
    { key: 'achievements_score',       label: 'Achieve.',   weight: '10%' },
    { key: 'job_title_score',          label: 'Job Title',  weight: '8%'  },
    { key: 'education_score',          label: 'Education',  weight: '7%'  },
    { key: 'resume_length_score',      label: 'Length',     weight: '4%'  },
    { key: 'contact_info_score',       label: 'Contact',    weight: '3%'  },
  ];

  /* ── Pure helpers ── */

  function getToken() {
    return localStorage.getItem('access_token')
        || sessionStorage.getItem('access_token');
  }

  function getBand(score) {
    if (score >= 75) return 'strong';
    if (score >= 65) return 'good';
    if (score >= 50) return 'borderline';
    return 'weak';
  }

  function getBandLabel(band) {
    return { strong:'Strong Match', good:'Good Match',
             borderline:'Needs Work', weak:'Weak Match' }[band] || band;
  }

  function getBandEmoji(band) {
    return { strong:'🎯', good:'👍', borderline:'⚠️', weak:'🔧' }[band] || '';
  }

  function getMajorEmoji(major) {
    return { technology:'💻', medical:'🏥', engineering:'⚙️',
             financial:'📊', marketing:'📣' }[major] || '📄';
  }

  function barColor(val) {
    if (val >= 75) return '#059669';
    if (val >= 50) return '#2563EB';
    if (val >= 30) return '#D97706';
    return '#DC2626';
  }

  function ringColor(band) {
    return { strong:'#059669', good:'#2563EB',
             borderline:'#D97706', weak:'#DC2626' }[band] || '#DC2626';
  }

  function ringOffset(score, circ) {
    return (circ - (score / 100) * circ).toFixed(2);
  }

  function fmtDate(iso) {
    return new Date(iso).toLocaleDateString('en-MY', {
      day:'numeric', month:'short', year:'numeric',
    });
  }

  function fmtRelative(iso) {
    const diff = Date.now() - new Date(iso).getTime();
    const m    = Math.floor(diff / 60000);
    if (m < 1)  return 'Just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    if (h < 24) return `${h}h ago`;
    const d = Math.floor(h / 24);
    if (d < 7)  return `${d}d ago`;
    return fmtDate(iso);
  }

  function animateCount(el, from, to, suffix = '', dur = 800) {
    if (!el) return;
    const start = performance.now();
    const tick  = setInterval(() => {
      const pct  = Math.min((performance.now() - start) / dur, 1);
      const ease = 1 - Math.pow(1 - pct, 3);
      el.textContent = Math.round(from + (to - from) * ease) + suffix;
      if (pct >= 1) clearInterval(tick);
    }, dur / 30);
  }

  function applyClientSearch(analyses, search) {
    if (!search.trim()) return analyses;
    const q = search.toLowerCase();
    return analyses.filter(a =>
      (a.filename || '').toLowerCase().includes(q) ||
      (a.major    || '').toLowerCase().includes(q)
    );
  }

  /* ── Toast ── */
  function showToast(msg, type = 'info') {
    const rack  = document.getElementById('toast-rack');
    if (!rack) return;
    const icons = {
      success: '<polyline points="20 6 9 17 4 12"/>',
      error:   '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
      info:    '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
    };
    const t = document.createElement('div');
    t.className = `hst-toast hst-toast--${type}`;
    t.innerHTML = `
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2.5"
           stroke-linecap="round" stroke-linejoin="round">
        ${icons[type] || icons.info}
      </svg>
      <span>${msg}</span>`;
    rack.appendChild(t);
    setTimeout(() => t.classList.add('hst-toast--show'), 10);
    setTimeout(() => {
      t.classList.remove('hst-toast--show');
      setTimeout(() => t.remove(), 400);
    }, 3500);
  }

  /* ── Public API ── */
  return {
    state,
    CRITERIA,
    getToken,
    getBand, getBandLabel, getBandEmoji,
    getMajorEmoji, barColor, ringColor,
    ringOffset, fmtDate, fmtRelative,
    animateCount, applyClientSearch, showToast,
  };
})();