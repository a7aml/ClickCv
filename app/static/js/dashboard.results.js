/* ==========================================================
   dashboard.results.js  — v3 REDESIGN + CV Preview
   
   Layout:
     Zone 1 — Full-width hero with band background gradient
     Zone 2 — 3-column body:
       Left  (22%) — Section status + Missing keywords visual
       Center(50%) — Criteria bars with ghost targets + radar chart
       Right (28%) — Quick wins prominent + rec cards + score gauge
   
   Phase 2 async: showRecsLoading / updateRecommendations / showRecsError
   CV Preview: openCvPreview() via dashboard.cv-preview.js
========================================================== */
(function () {
  'use strict';

  /* ── Band config ── */
  const BAND = {
    strong:     {
      color: '#059669', light: '#10b981', bg: 'rgba(5,150,105,.06)',
      border: 'rgba(5,150,105,.18)', label: 'Strong Match', emoji: '🎯',
      heroGrad: 'linear-gradient(135deg, rgba(5,150,105,.12) 0%, rgba(16,185,129,.06) 50%, rgba(255,255,255,0) 100%)',
      ringGrad: ['#059669','#10b981'],
    },
    good:       {
      color: '#2563EB', light: '#3b82f6', bg: 'rgba(37,99,235,.06)',
      border: 'rgba(37,99,235,.18)', label: 'Good Match', emoji: '👍',
      heroGrad: 'linear-gradient(135deg, rgba(37,99,235,.10) 0%, rgba(6,182,212,.05) 50%, rgba(255,255,255,0) 100%)',
      ringGrad: ['#2563EB','#06B6D4'],
    },
    borderline: {
      color: '#D97706', light: '#f59e0b', bg: 'rgba(217,119,6,.06)',
      border: 'rgba(217,119,6,.18)', label: 'Needs Work', emoji: '⚠️',
      heroGrad: 'linear-gradient(135deg, rgba(217,119,6,.10) 0%, rgba(245,158,11,.05) 50%, rgba(255,255,255,0) 100%)',
      ringGrad: ['#D97706','#f59e0b'],
    },
    weak:       {
      color: '#DC2626', light: '#ef4444', bg: 'rgba(220,38,38,.06)',
      border: 'rgba(220,38,38,.18)', label: 'Weak Match', emoji: '🔧',
      heroGrad: 'linear-gradient(135deg, rgba(220,38,38,.10) 0%, rgba(239,68,68,.05) 50%, rgba(255,255,255,0) 100%)',
      ringGrad: ['#DC2626','#ef4444'],
    },
  };

  const CRITERIA = [
    { key: 'keyword_score',            label: 'Keyword Matching',     weight: 35, short: 'Keywords',   target: 75 },
    { key: 'keyword_placement_score',  label: 'Keyword Placement',    weight: 18, short: 'Placement',  target: 75 },
    { key: 'formatting_score',         label: 'Formatting',           weight: 17, short: 'Format',     target: 90 },
    { key: 'structure_score',          label: 'Section Completeness', weight: 12, short: 'Structure',  target: 90 },
    { key: 'experience_recency_score', label: 'Experience Recency',   weight: 10, short: 'Recency',    target: 80 },
    { key: 'achievements_score',       label: 'Achievements',         weight: 10, short: 'Achieve.',   target: 70 },
    { key: 'job_title_score',          label: 'Job Title Match',      weight:  8, short: 'Job Title',  target: 80 },
    { key: 'education_score',          label: 'Education',            weight:  7, short: 'Education',  target: 75 },
    { key: 'resume_length_score',      label: 'Resume Length',        weight:  4, short: 'Length',     target: 100 },
    { key: 'contact_info_score',       label: 'Contact Info',         weight:  3, short: 'Contact',    target: 100 },
  ];

  function barColor(v) {
    if (v >= 75) return '#059669';
    if (v >= 50) return '#2563EB';
    if (v >= 30) return '#D97706';
    return '#DC2626';
  }

  function kwSeverityColor(idx, total) {
    const ratio = idx / total;
    if (ratio < 0.33) return { bg: 'rgba(220,38,38,.10)', color: '#DC2626', border: 'rgba(220,38,38,.25)' };
    if (ratio < 0.66) return { bg: 'rgba(217,119,6,.10)',  color: '#D97706', border: 'rgba(217,119,6,.25)' };
    return                   { bg: 'rgba(37,99,235,.08)',  color: '#2563EB', border: 'rgba(37,99,235,.20)' };
  }

  /* ══════════════════════════════════════════════════
     PUBLIC: renderAnalysisResults
  ══════════════════════════════════════════════════ */
  window.renderAnalysisResults = function (data, major) {
    const existing = document.getElementById('results-panel');
    if (existing) existing.remove();

    const score         = Math.round((data.overall_score || 0) * 10) / 10;
    const band          = data.score_band        || 'weak';
    const scores        = data.scores            || {};
    const sections      = data.detected_sections || [];
    const missingSec    = data.missing_sections  || [];          // required missing only (affects score)
    const allMissingKw  = data.missing_keywords  || [];          // full list for preview
    const missingKw     = allMissingKw.slice(0, 15);             // sliced for sidebar display
    const usedJd        = data.used_jd;
    const bc            = BAND[band] || BAND.weak;

    // ALL absent sections (required + optional) — matches the sidebar ✗ count
    const ALL_KNOWN_SECTIONS = ['summary','experience','education','skills','contact',
                                'certifications','projects','achievements','languages'];
    const allAbsentSec = ALL_KNOWN_SECTIONS.filter(s => !sections.includes(s));

    // ── Store data for CV Preview modal ──────────────────────────────
    // missingKeywords: full unsliced list so every gap is highlighted
    // foundKeywords:   from backend; falls back to empty (preview still shows missing)
    window.__cvPreviewData = {
      rawText:          data.raw_text       || '',
      sections:         data.sections_data  || {},
      missingKeywords:  allMissingKw,
      foundKeywords:    data.found_keywords || [],
      missingSections:  allAbsentSec,                            // ALL absent (required + optional)
      requiredMissing:  missingSec,                              // only required ones (for score)
      analysisId:       data.analysis_id,
    };

    const panel = document.createElement('div');
    panel.id        = 'results-panel';
    panel.className = 'rp';
    panel.style.cssText = 'display:none;opacity:0;transition:opacity .4s ease;';
    panel.innerHTML = buildHTML({ score, band, bc, scores, sections, missingSec, missingKw, allMissingKw, usedJd, major, analysisId: data.analysis_id, allAbsentSec });

    const uploadSection = document.getElementById('analyze');
    const dashMain      = document.querySelector('.dashboard');
    const dashParent    = dashMain ? dashMain.parentNode : null;

    if (dashParent) {
      dashParent.insertBefore(panel, dashMain.nextSibling);
    } else {
      uploadSection.insertAdjacentElement('afterend', panel);
    }

    if (dashMain) {
      dashMain.style.transition = 'opacity .3s ease';
      dashMain.style.opacity    = '0';
    } else {
      uploadSection.style.transition = 'opacity .3s ease';
      uploadSection.style.opacity    = '0';
    }

    setTimeout(() => {
      if (dashMain) dashMain.style.display = 'none';
      else          uploadSection.style.display = 'none';

      panel.style.display = 'block';
      panel.getBoundingClientRect();
      panel.style.opacity = '1';

      const layoutEl = document.querySelector('.layout') || document.body;
      layoutEl.scrollTo?.({ top: 0, behavior: 'smooth' });

      setTimeout(() => panel.querySelector('.rp-hero')?.classList.add('rp-hero--visible'), 50);

      setTimeout(() => {
        animateCounter(panel.querySelector('.rp-score__num'), 0, score, 1600);
        const arc = panel.querySelector('.rp-score__arc');
        if (arc) {
          arc.style.transition       = 'stroke-dashoffset 1.6s cubic-bezier(.35,0,.15,1)';
          arc.style.strokeDashoffset = arc.dataset.dash;
        }
        setTimeout(() => animateNeedle(panel, score), 200);
      }, 200);

      setTimeout(() => {
        panel.querySelectorAll('.rp-stat__num[data-target]').forEach(el => {
          animateCounter(el, 0, parseFloat(el.dataset.target), 900);
        });
      }, 600);

      setTimeout(() => {
        panel.querySelectorAll('.rp-bar__fill[data-target]').forEach((bar, i) => {
          setTimeout(() => {
            bar.style.transition = 'width .7s cubic-bezier(.4,0,.2,1)';
            bar.style.width      = bar.dataset.target + '%';
          }, i * 70);
        });
      }, 500);

      setTimeout(() => {
        panel.querySelectorAll('.rp-card[data-delay]').forEach(card => {
          setTimeout(() => card.classList.add('rp-card--visible'), +card.dataset.delay);
        });
      }, 300);

      setTimeout(() => drawRadarChart(panel, scores), 900);

    }, 320);

    // ── Button handlers ───────────────────────────────────────────────
    panel.querySelector('#analyse-another-btn')?.addEventListener('click', () => resetToUpload(panel, uploadSection));

    panel.querySelector('#preview-cv-btn')?.addEventListener('click', () => {
      if (typeof window.openCvPreview === 'function') {
        window.openCvPreview();
      }
    });

    panel.querySelector('#rebuild-btn')?.addEventListener('click', () => {
      window.location.href = `/rebuild?analysis_id=${data.analysis_id}`;
    });

    // Expandable rec cards (delegated)
    panel.addEventListener('click', e => {
      const header = e.target.closest('.rec-card__header');
      if (!header) return;
      const card   = header.closest('.rec-card');
      if (!card) return;
      const isOpen = card.classList.contains('rec-card--open');
      panel.querySelectorAll('.rec-card--open').forEach(c => c.classList.remove('rec-card--open'));
      if (!isOpen) card.classList.add('rec-card--open');
    });
  };

  /* ══════════════════════════════════════════════════
     PUBLIC: showRecsLoading
  ══════════════════════════════════════════════════ */
  window.showRecsLoading = function () {
    const p = document.getElementById('rp-rec-panel');
    if (!p) return;
    p.innerHTML = `
      <div class="rp-card__head">
        <div class="rp-card__title-wrap">
          <span class="rp-card__icon rp-card__icon--purple">💬</span>
          <h3 class="rp-card__title">AI Recommendations</h3>
        </div>
        <span class="rp-card__badge rp-card__badge--loading">Generating...</span>
      </div>
      <div class="rp-recs-loading">
        <div class="rp-recs-spinner"></div>
        <p class="rp-recs-loading__text">Generating personalised AI recommendations...<br>
          <span style="font-size:11px;opacity:.6">Usually 10–20 seconds</span></p>
      </div>`;
  };

  /* ══════════════════════════════════════════════════
     PUBLIC: updateRecommendations
  ══════════════════════════════════════════════════ */
  window.updateRecommendations = function (recs) {
    if (!recs) return;

    const s = document.querySelector('.rp-hero__summary');
    if (s && recs.summary_message) s.textContent = recs.summary_message;

    const recCount   = (recs.sections || []).length;
    const recCountEl = document.querySelector('.rp-stat__num[data-rec-count]');
    if (recCountEl) animateCounter(recCountEl, 0, recCount, 600);

    const qwPanel = document.getElementById('rp-quickwins-panel');
    if (qwPanel && (recs.quick_wins || []).length) {
      qwPanel.style.display = '';
      qwPanel.innerHTML = buildQuickWins(recs.quick_wins);
      qwPanel.classList.add('rp-card--visible');
    }

    const recPanel = document.getElementById('rp-rec-panel');
    if (recPanel) {
      recPanel.innerHTML = `
        <div class="rp-card__head">
          <div class="rp-card__title-wrap">
            <span class="rp-card__icon rp-card__icon--purple">💬</span>
            <h3 class="rp-card__title">AI Recommendations</h3>
          </div>
          <span class="rp-card__badge">${recCount} sections</span>
        </div>
        <p class="rp-card__desc" style="margin-bottom:10px">Click any card to expand the full suggestion.</p>
        <div class="rec-list">${buildRecommendations(recs.sections || [])}</div>`;
      recPanel.classList.add('rp-card--visible');
    }

    const kwPanel = document.getElementById('rp-topkw-panel');
    if (kwPanel && (recs.top_keywords_to_add || []).length) {
      kwPanel.style.display = '';
      kwPanel.innerHTML = `
        <div class="rp-card__head">
          <div class="rp-card__title-wrap">
            <span class="rp-card__icon rp-card__icon--green">✓</span>
            <h3 class="rp-card__title">Keywords to Add</h3>
          </div>
          <span class="rp-card__badge rp-card__badge--green">AI picked</span>
        </div>
        <div class="rp-kw-grid">
          ${(recs.top_keywords_to_add || []).map(k => `<span class="rp-kw rp-kw--add">+ ${k}</span>`).join('')}
        </div>`;
      kwPanel.classList.add('rp-card--visible');
    }
  };

  /* ══════════════════════════════════════════════════
     PUBLIC: showRecsError
  ══════════════════════════════════════════════════ */
  window.showRecsError = function (msg) {
    const p = document.getElementById('rp-rec-panel');
    if (!p) return;
    p.innerHTML = `
      <div class="rp-card__head">
        <div class="rp-card__title-wrap">
          <span class="rp-card__icon rp-card__icon--purple">💬</span>
          <h3 class="rp-card__title">AI Recommendations</h3>
        </div>
        <span class="rp-card__badge rp-card__badge--orange">Unavailable</span>
      </div>
      <div class="rp-empty"><span style="font-size:24px">⚠️</span>
        <p>${msg || 'Could not load AI recommendations. Your ATS score is still accurate.'}</p>
      </div>`;
  };

  /* ══════════════════════════════════════════════════
     RESET
  ══════════════════════════════════════════════════ */
  function resetToUpload(panel, uploadSection) {
    panel.style.transition = 'opacity .3s ease';
    panel.style.opacity    = '0';
    setTimeout(() => {
      panel.remove();

      const dashMain = document.querySelector('.dashboard');
      if (dashMain) {
        dashMain.style.display    = '';
        dashMain.style.transition = 'opacity .3s ease';
        dashMain.style.opacity    = '0';
        dashMain.getBoundingClientRect();
        dashMain.style.opacity    = '1';
      } else {
        uploadSection.style.display    = '';
        uploadSection.style.transition = 'opacity .3s ease';
        uploadSection.style.opacity    = '0';
        uploadSection.getBoundingClientRect();
        uploadSection.style.opacity    = '1';
      }

      window.cvFiles = [];
      ['file-list','file-list-section','analyse-cta','file-count','file-input'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        if (id === 'file-list')        el.innerHTML = '';
        if (id === 'file-list-section' || id === 'analyse-cta') el.classList.remove('visible');
        if (id === 'file-count')       el.textContent = '0';
        if (id === 'file-input')       el.value = '';
      });

      if (dashMain) dashMain.scrollTo?.({ top: 0, behavior: 'smooth' });
    }, 320);
  }

  /* ══════════════════════════════════════════════════
     MAIN HTML BUILDER
  ══════════════════════════════════════════════════ */
  function buildHTML({ score, band, bc, scores, sections, missingSec, missingKw, allMissingKw, usedJd, major, analysisId, allAbsentSec }) {
    const kwCount  = missingKw.length;
    const secMiss  = missingSec.length;

    const R    = 64;
    const circ = +(2 * Math.PI * R).toFixed(2);
    const dash = +((score / 100) * circ).toFixed(2);

    const topCriteria = [...CRITERIA]
      .map(c => ({ ...c, val: scores[c.key] || 0 }))
      .sort((a, b) => a.val - b.val)
      .slice(0, 3);

    return `
    <div class="rp-hero" style="background:${bc.heroGrad}">

      <div class="rp-hero__top">

        <div class="rp-score-wrap">
          <div class="rp-score">
            <svg class="rp-score__svg" viewBox="0 0 156 156">
              <circle cx="78" cy="78" r="${R}" fill="none" stroke="rgba(0,0,0,.06)" stroke-width="14"/>
              <circle class="rp-score__arc" cx="78" cy="78" r="${R}" fill="none"
                stroke="url(#scoreGrad_${band})" stroke-width="14" stroke-linecap="round"
                stroke-dasharray="${circ}" stroke-dashoffset="${circ}"
                data-dash="${circ - dash}"
                style="transform:rotate(-90deg);transform-origin:center"/>
              <defs>
                <linearGradient id="scoreGrad_${band}" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%"   stop-color="${bc.color}"/>
                  <stop offset="100%" stop-color="${bc.light}"/>
                </linearGradient>
              </defs>
            </svg>
            <div class="rp-score__label">
              <span class="rp-score__num" style="color:${bc.color}">0</span>
              <span class="rp-score__sub">/100</span>
            </div>
          </div>
          <div class="rp-band" style="color:${bc.color};background:${bc.bg};border-color:${bc.border}">
            <span>${bc.emoji}</span><span>${bc.label}</span>
          </div>
        </div>

        <div class="rp-hero__info">
          <h2 class="rp-hero__title">ATS Analysis Complete</h2>
          <p class="rp-hero__summary">Your CV has been analysed across 10 weighted ATS criteria. AI recommendations are loading...</p>
          <div class="rp-hero__meta">
            <span class="rp-meta-pill">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg>
              ${major}
            </span>
            ${usedJd
              ? `<span class="rp-meta-pill rp-meta-pill--jd">✓ JD matched</span>`
              : `<span class="rp-meta-pill rp-meta-pill--warn">⚠ Industry keywords only — add a JD for better accuracy</span>`}
          </div>
          <div class="rp-hero__weaknesses">
            <span class="rp-hero__weak-label">Biggest gaps:</span>
            ${topCriteria.map(c => `
              <span class="rp-hero__weak-pill" style="color:${barColor(c.val)};border-color:${barColor(c.val)}40;background:${barColor(c.val)}0f">
                ${c.short} ${c.val}
              </span>`).join('')}
          </div>
        </div>

        <div class="rp-gauge-wrap">
          <canvas id="rp-gauge" width="180" height="110"></canvas>
          <div class="rp-gauge__label" style="color:${bc.color}">${bc.label}</div>
        </div>

        <!-- Actions — Preview CV button added here -->
        <div class="rp-hero__actions">
          <button class="btn btn--ghost btn--sm" id="analyse-another-btn">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
            Analyse Another
          </button>
          <button class="btn btn--ghost btn--sm" id="preview-cv-btn">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
            Preview CV
          </button>
          <button class="btn btn--secondary btn--sm" onclick="window.print()">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
            Export
          </button>
          <button class="btn btn--primary btn--sm" id="rebuild-btn">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
            Rebuild CV
          </button>
        </div>
      </div>

      <div class="rp-hero__stats" style="display:none"></div>
    </div>

    <div class="rp-body">

      <div class="rp-col rp-col--left">

        <div class="rp-card" data-delay="0">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--${allAbsentSec.length>0?'red':'green'}">📄</span>
              <h3 class="rp-card__title">CV Sections</h3>
            </div>
            ${allAbsentSec.length > 0
              ? `<span class="rp-card__badge rp-card__badge--red">${allAbsentSec.length} missing</span>`
              : `<span class="rp-card__badge rp-card__badge--green">Complete ✓</span>`}
          </div>
          <div class="rp-sections-list">
            ${['summary','experience','education','skills','contact','certifications','projects','achievements','languages'].map(s => {
              const present  = sections.includes(s);
              const required = ['summary','experience','education','skills','contact'].includes(s);
              return `<div class="rp-section-row">
                <span class="rp-section-icon" style="color:${present?'#059669':'#DC2626'}">
                  ${present ? '✓' : '✗'}
                </span>
                <span class="rp-section-name" style="color:${present?'var(--color-text)':'#DC2626'}">${s}</span>
                ${required && !present ? `<span class="rp-section-badge">Required</span>` : ''}
                ${!required ? `<span class="rp-section-badge rp-section-badge--opt">Optional</span>` : ''}
              </div>`;
            }).join('')}
          </div>
        </div>

        ${missingKw.length ? `
        <div class="rp-card" data-delay="100">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--orange">🔍</span>
              <h3 class="rp-card__title">Missing Keywords</h3>
            </div>
            <span class="rp-card__badge rp-card__badge--orange">${allMissingKw.length} gaps</span>
          </div>
          <p class="rp-card__desc">Color shows priority — red = most critical for your score.</p>
          <div class="rp-kw-severity">
            ${missingKw.map((k, i) => {
              const c = kwSeverityColor(i, missingKw.length);
              return `<span class="rp-kw-pill" style="background:${c.bg};color:${c.color};border-color:${c.border}" title="Missing keyword">${k}</span>`;
            }).join('')}
          </div>
          <div class="rp-kw-legend">
            <span class="rp-kw-leg-dot" style="background:#DC2626"></span><span>Critical</span>
            <span class="rp-kw-leg-dot" style="background:#D97706"></span><span>Important</span>
            <span class="rp-kw-leg-dot" style="background:#2563EB"></span><span>Nice to have</span>
          </div>
        </div>` : `
        <div class="rp-card rp-card--success" data-delay="100">
          <div style="text-align:center;padding:16px 8px">
            <div style="font-size:32px;margin-bottom:8px">🎯</div>
            <p style="margin:0;font-weight:700;color:#059669">No missing keywords!</p>
            <p style="margin:4px 0 0;font-size:12px;color:var(--color-muted)">Your CV covers all key terms.</p>
          </div>
        </div>`}

      </div>

      <div class="rp-col rp-col--center">

        <div class="rp-card" data-delay="60">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--blue">📊</span>
              <h3 class="rp-card__title">10-Criteria Breakdown</h3>
            </div>
            <div style="display:flex;align-items:center;gap:10px">
              <span class="rp-legend-dot" style="background:rgba(0,0,0,.12)"></span>
              <span style="font-size:10px;color:var(--color-muted)">Target 75%</span>
              <span class="rp-card__badge">ATS Algorithm</span>
            </div>
          </div>
          <div class="rp-criteria">${buildCriteriaBars(scores)}</div>
        </div>

        <div class="rp-card" data-delay="140">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--blue">🕸️</span>
              <h3 class="rp-card__title">Skills Radar</h3>
            </div>
            <span class="rp-card__badge">vs Target</span>
          </div>
          <p class="rp-card__desc">Blue = your CV. Gray = target benchmark (75%). Bigger area = stronger match.</p>
          <div style="display:flex;justify-content:center;padding:8px 0">
            <canvas id="rp-radar" width="320" height="260"></canvas>
          </div>
        </div>

      </div>

      <div class="rp-col rp-col--right">

        <div class="rp-card rp-card--wins" id="rp-quickwins-panel" data-delay="40" style="display:none"></div>

        <div class="rp-card" id="rp-rec-panel" data-delay="120">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--purple">💬</span>
              <h3 class="rp-card__title">AI Recommendations</h3>
            </div>
            <span class="rp-card__badge">Loading...</span>
          </div>
          <div class="rp-recs-loading">
            <div class="rp-recs-spinner"></div>
            <p class="rp-recs-loading__text">Generating AI recommendations...<br>
              <span style="font-size:11px;opacity:.6">Usually 10–20 seconds</span></p>
          </div>
        </div>

        <div class="rp-card" id="rp-topkw-panel" data-delay="200" style="display:none"></div>

      </div>
    </div>`;
  }

  /* ── Criteria bars with ghost target ── */
  function buildCriteriaBars(scores) {
    return CRITERIA.map(({ key, label, weight, target }) => {
      const val   = scores[key] || 0;
      const color = barColor(val);
      const gap   = Math.max(0, target - val);
      return `
        <div class="rp-criteria__row">
          <div class="rp-criteria__label">
            <span class="rp-criteria__name">${label}</span>
            <span class="rp-criteria__weight">${weight}%</span>
          </div>
          <div class="rp-bar-wrap">
            <div class="rp-bar-ghost" style="width:${target}%"></div>
            <div class="rp-bar">
              <div class="rp-bar__fill" style="width:0%;background:${color}" data-target="${val}"></div>
            </div>
            ${gap > 5 ? `<span class="rp-bar__gap">+${gap} needed</span>` : ''}
          </div>
          <span class="rp-criteria__score" style="color:${color}">${val}</span>
        </div>`;
    }).join('');
  }

  /* ── Quick wins builder ── */
  function buildQuickWins(wins) {
    return `
      <div class="rp-card__head">
        <div class="rp-card__title-wrap">
          <span class="rp-card__icon rp-card__icon--yellow" style="font-size:16px">⚡</span>
          <h3 class="rp-card__title">Quick Wins</h3>
        </div>
        <span class="rp-card__badge rp-card__badge--green">Do these today</span>
      </div>
      <p class="rp-card__desc">These 3 actions will give you the highest score boost with least effort.</p>
      <div class="rp-wins">
        ${wins.map((w, i) => `
        <div class="rp-win">
          <div class="rp-win__num">${i + 1}</div>
          <div class="rp-win__content">
            <p class="rp-win__text">${w}</p>
          </div>
        </div>`).join('')}
      </div>`;
  }

  /* ── Rec cards builder ── */
  function buildRecommendations(recSections) {
    if (!recSections.length) return `
      <div class="rp-empty"><span style="font-size:28px">🎉</span>
        <p>No major issues — your CV is in great shape!</p></div>`;

    return recSections.map((rec, i) => {
      const pColor = rec.priority === 1 ? '#DC2626' : rec.priority === 2 ? '#D97706' : '#2563EB';
      const pLabel = rec.priority === 1 ? 'Critical' : rec.priority === 2 ? 'Important' : 'Minor';
      const pIcon  = rec.priority === 1 ? '🔴' : rec.priority === 2 ? '🟡' : '🔵';
      return `
        <div class="rec-card" style="animation-delay:${i * 60}ms">
          <div class="rec-card__header">
            <div class="rec-card__meta">
              <span class="rec-card__section">${rec.section.toUpperCase()}</span>
              <span class="rec-card__priority" style="color:${pColor};background:${pColor}15;border-color:${pColor}30">
                ${pIcon} ${pLabel}
              </span>
            </div>
            <p class="rec-card__issue">${rec.issue}</p>
            <span class="rec-card__chevron">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="6 9 12 15 18 9"/></svg>
            </span>
          </div>
          <div class="rec-card__body">
            <p class="rec-card__recommendation">${rec.recommendation}</p>
            ${rec.rewrite_example ? `
            <div class="rec-card__rewrite">
              <div class="rec-card__rewrite-label">✏ Suggested rewrite</div>
              <p class="rec-card__rewrite-text">${rec.rewrite_example}</p>
            </div>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  /* ══════════════════════════════════════════════════
     RADAR CHART (canvas)
  ══════════════════════════════════════════════════ */
  function drawRadarChart(panel, scores) {
    const canvas = panel.querySelector('#rp-radar');
    if (!canvas) return;
    const ctx    = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H / 2 + 10;
    const R  = Math.min(W, H) * 0.36;

    const points  = CRITERIA.slice(0, 8);
    const N       = points.length;
    const vals    = points.map(p => (scores[p.key] || 0) / 100);
    const targets = points.map(p => p.target / 100);

    function coord(i, r, total) {
      const angle = (Math.PI * 2 * i / total) - Math.PI / 2;
      return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
    }

    ctx.clearRect(0, 0, W, H);

    [0.25, 0.5, 0.75, 1.0].forEach(ratio => {
      ctx.beginPath();
      for (let i = 0; i < N; i++) {
        const p = coord(i, R * ratio, N);
        i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
      }
      ctx.closePath();
      ctx.strokeStyle = ratio === 0.75 ? 'rgba(37,99,235,.25)' : 'rgba(0,0,0,.07)';
      ctx.lineWidth   = ratio === 0.75 ? 1.5 : 1;
      ctx.setLineDash(ratio === 0.75 ? [4, 3] : []);
      ctx.stroke();
      ctx.setLineDash([]);
      if (ratio === 1.0) {
        ctx.fillStyle = 'rgba(0,0,0,.3)';
        ctx.font      = '9px Inter,system-ui,sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('100', cx, cy - R - 4);
      }
    });

    for (let i = 0; i < N; i++) {
      const p = coord(i, R, N);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(p.x, p.y);
      ctx.strokeStyle = 'rgba(0,0,0,.08)';
      ctx.lineWidth   = 1;
      ctx.stroke();
    }

    ctx.beginPath();
    for (let i = 0; i < N; i++) {
      const p = coord(i, R * targets[i], N);
      i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
    ctx.fillStyle   = 'rgba(0,0,0,.06)';
    ctx.strokeStyle = 'rgba(0,0,0,.18)';
    ctx.lineWidth   = 1.5;
    ctx.fill();
    ctx.stroke();

    ctx.beginPath();
    for (let i = 0; i < N; i++) {
      const p = coord(i, R * vals[i], N);
      i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
    ctx.fillStyle   = 'rgba(37,99,235,.18)';
    ctx.strokeStyle = '#2563EB';
    ctx.lineWidth   = 2;
    ctx.fill();
    ctx.stroke();

    for (let i = 0; i < N; i++) {
      const p = coord(i, R * vals[i], N);
      ctx.beginPath();
      ctx.arc(p.x, p.y, 4, 0, Math.PI * 2);
      ctx.fillStyle   = '#2563EB';
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth   = 1.5;
      ctx.stroke();
    }

    ctx.fillStyle = 'rgba(15,22,36,.65)';
    ctx.font      = 'bold 9.5px Inter,system-ui,sans-serif';
    for (let i = 0; i < N; i++) {
      const p     = coord(i, R * 1.18, N);
      const angle = (Math.PI * 2 * i / N) - Math.PI / 2;
      ctx.textAlign = Math.abs(Math.cos(angle)) < 0.1
        ? 'center'
        : Math.cos(angle) > 0 ? 'left' : 'right';
      ctx.fillText(points[i].short, p.x, p.y + 3);
    }

    ctx.fillStyle = 'rgba(37,99,235,.7)';
    ctx.fillRect(W - 90, H - 36, 10, 10);
    ctx.fillStyle = 'rgba(0,0,0,.25)';
    ctx.fillRect(W - 90, H - 20, 10, 10);
    ctx.fillStyle = 'rgba(15,22,36,.55)';
    ctx.font      = '9px Inter,system-ui,sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Your CV', W - 76, H - 28);
    ctx.fillText('Target',  W - 76, H - 12);
  }

  /* ══════════════════════════════════════════════════
     SCORE GAUGE (speedometer)
  ══════════════════════════════════════════════════ */
  function animateNeedle(panel, score) {
    const canvas = panel.querySelector('#rp-gauge');
    if (!canvas) return;
    const ctx    = canvas.getContext('2d');
    const W = canvas.width, H = canvas.height;
    const cx = W / 2, cy = H - 18;
    const R  = 72;

    const zones = [
      { from: 0,   to: 50,  color: '#DC2626' },
      { from: 50,  to: 65,  color: '#D97706' },
      { from: 65,  to: 75,  color: '#2563EB' },
      { from: 75,  to: 100, color: '#059669' },
    ];

    function scoreToAngle(s) {
      return Math.PI + (s / 100) * Math.PI;
    }

    function draw(currentScore) {
      ctx.clearRect(0, 0, W, H);

      zones.forEach(z => {
        ctx.beginPath();
        ctx.arc(cx, cy, R, scoreToAngle(z.from), scoreToAngle(z.to));
        ctx.lineWidth   = 14;
        ctx.strokeStyle = z.color + '55';
        ctx.stroke();
      });

      const activeZone = zones.find(z => currentScore >= z.from && currentScore <= z.to) || zones[zones.length-1];
      ctx.beginPath();
      ctx.arc(cx, cy, R, Math.PI, scoreToAngle(currentScore));
      ctx.lineWidth   = 14;
      ctx.strokeStyle = activeZone.color;
      ctx.lineCap     = 'round';
      ctx.stroke();

      ctx.fillStyle = 'rgba(15,22,36,.45)';
      ctx.font      = 'bold 8px Inter,system-ui,sans-serif';
      ctx.textAlign = 'center';
      [
        { s: 25,  label: 'Weak'   },
        { s: 57,  label: 'OK'     },
        { s: 70,  label: 'Good'   },
        { s: 87,  label: 'Strong' },
      ].forEach(({ s, label }) => {
        const a  = scoreToAngle(s);
        const lx = cx + (R + 16) * Math.cos(a);
        const ly = cy + (R + 16) * Math.sin(a);
        ctx.fillText(label, lx, ly);
      });

      const angle     = scoreToAngle(currentScore);
      const needleLen = R - 12;
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(cx + needleLen * Math.cos(angle), cy + needleLen * Math.sin(angle));
      ctx.strokeStyle = activeZone.color;
      ctx.lineWidth   = 2.5;
      ctx.lineCap     = 'round';
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fillStyle = activeZone.color;
      ctx.fill();
    }

    let current = 0;
    const target = score;
    const dur    = 1400;
    const start  = performance.now();
    function animate(now) {
      const p    = Math.min((now - start) / dur, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      current    = ease * target;
      draw(current);
      if (p < 1) requestAnimationFrame(animate);
    }
    requestAnimationFrame(animate);
  }

  /* ── Counter animation ── */
  function animateCounter(el, from, to, duration) {
    if (!el) return;
    const start = performance.now();
    function step(now) {
      const p    = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(from + (to - from) * ease);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

})();