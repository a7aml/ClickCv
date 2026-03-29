/* ==========================================================
   dashboard.results.js  (~480 lines)
   3-Zone redesign:
     Zone 1 — Full-width score hero (large ring, band, summary)
     Zone 2 — Left 55%: criteria bars, missing keywords, sections
     Zone 3 — Right 45%: quick wins, expandable rec cards, keywords
   Option C UX: upload fades out → results fade in.
   Exposes window.renderAnalysisResults(data, major).
========================================================== */
(function () {
  'use strict';

  /* ── Band config ── */
  const BAND = {
    strong:     { color: '#059669', bg: 'rgba(5,150,105,.08)',   border: 'rgba(5,150,105,.20)',  label: 'Strong Match', emoji: '🎯', grad: 'linear-gradient(135deg,#059669,#10b981)' },
    good:       { color: '#2563EB', bg: 'rgba(37,99,235,.08)',  border: 'rgba(37,99,235,.20)',  label: 'Good Match',   emoji: '👍', grad: 'linear-gradient(135deg,#2563EB,#06B6D4)' },
    borderline: { color: '#D97706', bg: 'rgba(217,119,6,.08)',  border: 'rgba(217,119,6,.20)',  label: 'Needs Work',   emoji: '⚠️', grad: 'linear-gradient(135deg,#D97706,#f59e0b)' },
    weak:       { color: '#DC2626', bg: 'rgba(220,38,38,.08)',  border: 'rgba(220,38,38,.20)',  label: 'Weak Match',   emoji: '🔧', grad: 'linear-gradient(135deg,#DC2626,#ef4444)' },
  };

  const CRITERIA_META = [
    { key: 'keyword_score',            label: 'Keyword Matching',    weight: 35 },
    { key: 'keyword_placement_score',  label: 'Keyword Placement',   weight: 18 },
    { key: 'formatting_score',         label: 'Formatting',          weight: 17 },
    { key: 'structure_score',          label: 'Section Completeness',weight: 12 },
    { key: 'experience_recency_score', label: 'Experience Recency',  weight: 10 },
    { key: 'achievements_score',       label: 'Achievements',        weight: 10 },
    { key: 'job_title_score',          label: 'Job Title Match',     weight:  8 },
    { key: 'education_score',          label: 'Education',           weight:  7 },
    { key: 'resume_length_score',      label: 'Resume Length',       weight:  4 },
    { key: 'contact_info_score',       label: 'Contact Info',        weight:  3 },
  ];

  /* ── Score thresholds → label ── */
  function scoreLabel(v) {
    if (v >= 75) return { text: 'Strong',      color: '#059669' };
    if (v >= 50) return { text: 'Good',        color: '#2563EB' };
    if (v >= 30) return { text: 'Needs work',  color: '#D97706' };
    return              { text: 'Critical',    color: '#DC2626' };
  }

  /* ── Public entry point ── */
  window.renderAnalysisResults = function (data, major) {
    const existing = document.getElementById('results-panel');
    if (existing) existing.remove();

    const score      = Math.round((data.overall_score || 0) * 10) / 10;
    const band       = data.score_band    || 'weak';
    const scores     = data.scores        || {};
    const recs       = data.recommendations || {};
    const sections   = data.detected_sections || [];
    const missingSec = data.missing_sections  || [];
    const missingKw  = (data.missing_keywords || []).slice(0, 12);
    const usedJd     = data.used_jd;
    const bc         = BAND[band] || BAND.weak;

    /* Score ring geometry — large 140px */
    const R    = 58;
    const circ = +(2 * Math.PI * R).toFixed(2);
    const dash = +((score / 100) * circ).toFixed(2);

    /* Build panel */
    const panel = document.createElement('div');
    panel.id        = 'results-panel';
    panel.className = 'rp';
    panel.style.cssText = 'display:none;opacity:0;transition:opacity .4s ease;';
    panel.innerHTML = buildHTML({ score, band, bc, scores, recs, sections,
                                   missingSec, missingKw, usedJd, major, R, circ, dash });

    const uploadSection = document.getElementById('analyze');
    uploadSection.insertAdjacentElement('afterend', panel);

    /* Option C — fade upload out then fade results in */
    uploadSection.style.transition = 'opacity .3s ease';
    uploadSection.style.opacity    = '0';

    setTimeout(() => {
      uploadSection.style.display = 'none';
      panel.style.display         = 'block';
      panel.getBoundingClientRect(); /* force reflow */
      panel.style.opacity         = '1';

      const dashMain = document.querySelector('.dashboard');
      if (dashMain) dashMain.scrollTo({ top: 0, behavior: 'smooth' });

      /* ── Animations ── */
      /* 1. Hero entrance — zone slides up */
      setTimeout(() => {
        panel.querySelector('.rp-hero')?.classList.add('rp-hero--visible');
      }, 50);

      /* 2. Score counter + ring arc */
      setTimeout(() => {
        animateCounter(panel.querySelector('.rp-score__num'), 0, score, 1400);
        const arc = panel.querySelector('.rp-score__arc');
        if (arc) {
          arc.style.transition       = 'stroke-dashoffset 1.4s cubic-bezier(.35,0,.15,1)';
          arc.style.strokeDashoffset = arc.dataset.dash;
        }
      }, 200);

      /* 3. Stat counters in hero footer */
      setTimeout(() => {
        panel.querySelectorAll('.rp-stat__num[data-target]').forEach(el => {
          animateCounter(el, 0, parseFloat(el.dataset.target), 900);
        });
      }, 500);

      /* 4. Criteria bars — staggered 60ms apart */
      setTimeout(() => {
        panel.querySelectorAll('.rp-bar__fill').forEach((bar, i) => {
          setTimeout(() => {
            bar.style.transition = 'width .65s cubic-bezier(.4,0,.2,1)';
            bar.style.width      = bar.dataset.target + '%';
          }, i * 60);
        });
      }, 400);

      /* 5. Cards fade-slide in from bottom */
      setTimeout(() => {
        panel.querySelectorAll('.rp-card[data-delay]').forEach(card => {
          setTimeout(() => card.classList.add('rp-card--visible'), +card.dataset.delay);
        });
      }, 300);

    }, 320);

    /* Button handlers */
    panel.querySelector('#analyse-another-btn')?.addEventListener('click', () =>
      resetToUpload(panel, uploadSection)
    );
    panel.querySelector('#rebuild-btn')?.addEventListener('click', () => {
      window.location.href = '/build-cv';
    });

    /* Expandable rec cards */
    panel.addEventListener('click', e => {
      const header = e.target.closest('.rec-card__header');
      if (!header) return;
      const card = header.closest('.rec-card');
      if (!card) return;
      const isOpen = card.classList.contains('rec-card--open');
      /* Close all */
      panel.querySelectorAll('.rec-card--open').forEach(c => c.classList.remove('rec-card--open'));
      /* Toggle clicked */
      if (!isOpen) card.classList.add('rec-card--open');
    });
  };

  /* ── Reset to upload ── */
  function resetToUpload(panel, uploadSection) {
    panel.style.transition = 'opacity .3s ease';
    panel.style.opacity    = '0';
    setTimeout(() => {
      panel.remove();
      uploadSection.style.display    = '';
      uploadSection.style.transition = 'opacity .3s ease';
      uploadSection.style.opacity    = '0';
      uploadSection.getBoundingClientRect();
      uploadSection.style.opacity    = '1';
      window.cvFiles = [];
      ['file-list','file-list-section','analyse-cta','file-count','file-input'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        if (id === 'file-list')        el.innerHTML = '';
        if (id === 'file-list-section' || id === 'analyse-cta') el.classList.remove('visible');
        if (id === 'file-count')       el.textContent = '0';
        if (id === 'file-input')       el.value = '';
      });
      const dashMain = document.querySelector('.dashboard');
      if (dashMain) dashMain.scrollTo({ top: 0, behavior: 'smooth' });
    }, 320);
  }

  /* ══════════════════════════════════════════════════
     HTML BUILDER
  ══════════════════════════════════════════════════ */
  function buildHTML({ score, band, bc, scores, recs, sections,
                        missingSec, missingKw, usedJd, major, R, circ, dash }) {

    const kwCount  = missingKw.length;
    const secMiss  = missingSec.length;
    const recCount = (recs.sections || []).length;

    return `
    <!-- ═══ ZONE 1 — SCORE HERO ═══ -->
    <div class="rp-hero">

      <div class="rp-hero__left">
        <!-- Large score ring -->
        <div class="rp-score">
          <svg class="rp-score__svg" viewBox="0 0 140 140">
            <!-- Track -->
            <circle cx="70" cy="70" r="${R}" fill="none"
              stroke="rgba(0,0,0,.07)" stroke-width="12"/>
            <!-- Arc -->
            <circle class="rp-score__arc" cx="70" cy="70" r="${R}" fill="none"
              stroke="${bc.color}" stroke-width="12" stroke-linecap="round"
              stroke-dasharray="${circ}" stroke-dashoffset="${circ}"
              data-dash="${circ - dash}"
              style="transform:rotate(-90deg);transform-origin:center;filter:drop-shadow(0 0 8px ${bc.color}60)"/>
          </svg>
          <div class="rp-score__label">
            <span class="rp-score__num" style="color:${bc.color}">0</span>
            <span class="rp-score__sub">/100</span>
          </div>
        </div>

        <!-- Band + summary -->
        <div class="rp-hero__info">
          <div class="rp-band" style="color:${bc.color};background:${bc.bg};border-color:${bc.border}">
            <span>${bc.emoji}</span>
            <span>${bc.label}</span>
          </div>
          <h2 class="rp-hero__title">ATS Analysis Complete</h2>
          <p class="rp-hero__summary">${recs.summary_message || 'Your CV has been analysed across 10 weighted ATS criteria.'}</p>
          <div class="rp-hero__meta">
            <span class="rp-meta-pill">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-4 0v2"/></svg>
              ${major}
            </span>
            ${usedJd
              ? '<span class="rp-meta-pill rp-meta-pill--jd"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>JD matched</span>'
              : '<span class="rp-meta-pill rp-meta-pill--warn">Industry keywords</span>'}
          </div>
        </div>
      </div>

      <!-- Hero stats strip -->
      <div class="rp-hero__stats">
        <div class="rp-stat">
          <span class="rp-stat__num" data-target="${kwCount}">${kwCount}</span>
          <span class="rp-stat__label">Missing keywords</span>
        </div>
        <div class="rp-stat__divider"></div>
        <div class="rp-stat">
          <span class="rp-stat__num" data-target="${secMiss}" style="color:${secMiss > 0 ? '#DC2626' : '#059669'}">${secMiss}</span>
          <span class="rp-stat__label">Missing sections</span>
        </div>
        <div class="rp-stat__divider"></div>
        <div class="rp-stat">
          <span class="rp-stat__num" data-target="${recCount}">${recCount}</span>
          <span class="rp-stat__label">AI suggestions</span>
        </div>
        <div class="rp-stat__divider"></div>
        <div class="rp-stat">
          <span class="rp-stat__num" data-target="${sections.length}">${sections.length}</span>
          <span class="rp-stat__label">Detected sections</span>
        </div>
      </div>

      <!-- Actions -->
      <div class="rp-hero__actions">
        <button class="btn btn--ghost btn--sm" id="analyse-another-btn">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
          </svg>
          Analyse Another
        </button>
        <button class="btn btn--secondary btn--sm" onclick="window.print()">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/>
          </svg>
          Export
        </button>
        <button class="btn btn--primary btn--sm" id="rebuild-btn">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
          </svg>
          Rebuild CV
        </button>
      </div>
    </div>

    <!-- ═══ ZONES 2 + 3 — BODY ═══ -->
    <div class="rp-body">

      <!-- ── Zone 2: Left — Metrics ── -->
      <div class="rp-zone rp-zone--left">

        <!-- Criteria bars -->
        <div class="rp-card" data-delay="0">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--blue">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
              </span>
              <h3 class="rp-card__title">10-Criteria Breakdown</h3>
            </div>
            <span class="rp-card__badge">ATS Algorithm</span>
          </div>
          <div class="rp-criteria">${buildCriteriaBars(scores)}</div>
        </div>

        <!-- Section analysis -->
        <div class="rp-card" data-delay="80">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--${secMiss > 0 ? 'red' : 'green'}">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </span>
              <h3 class="rp-card__title">Section Analysis</h3>
            </div>
            ${secMiss > 0
              ? `<span class="rp-card__badge rp-card__badge--red">${secMiss} missing</span>`
              : `<span class="rp-card__badge rp-card__badge--green">All present</span>`}
          </div>
          ${secMiss > 0 ? `
          <p class="rp-card__desc" style="color:#DC2626;margin-bottom:8px;font-weight:600">Missing required sections:</p>
          <div class="rp-tags" style="margin-bottom:12px">
            ${missingSec.map(s => `<span class="rp-tag rp-tag--bad">✗ ${s}</span>`).join('')}
          </div>` : ''}
          <p class="rp-card__desc" style="margin-bottom:8px">Detected sections:</p>
          <div class="rp-tags">
            ${sections.map(s => `<span class="rp-tag rp-tag--good">✓ ${s}</span>`).join('')}
          </div>
        </div>

        <!-- Missing keywords -->
        ${missingKw.length ? `
        <div class="rp-card" data-delay="160">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--orange">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              </span>
              <h3 class="rp-card__title">Missing Keywords</h3>
            </div>
            <span class="rp-card__badge rp-card__badge--orange">${missingKw.length} gaps</span>
          </div>
          <p class="rp-card__desc">Add these naturally into your CV to boost your keyword score.</p>
          <div class="rp-kw-grid">
            ${missingKw.map(k => `<span class="rp-kw">${k}</span>`).join('')}
          </div>
        </div>` : ''}

      </div>

      <!-- ── Zone 3: Right — Actions ── -->
      <div class="rp-zone rp-zone--right">

        <!-- Quick wins -->
        ${(recs.quick_wins || []).length ? `
        <div class="rp-card rp-card--accent" data-delay="60">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--yellow">⚡</span>
              <h3 class="rp-card__title">Quick Wins</h3>
            </div>
            <span class="rp-card__badge rp-card__badge--green">Do these today</span>
          </div>
          <div class="rp-wins">
            ${(recs.quick_wins || []).map((w, i) => `
            <div class="rp-win" style="animation-delay:${i * 80}ms">
              <span class="rp-win__num">${i + 1}</span>
              <span class="rp-win__text">${w}</span>
            </div>`).join('')}
          </div>
        </div>` : ''}

        <!-- AI Recommendations — expandable -->
        <div class="rp-card" data-delay="120">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--purple">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              </span>
              <h3 class="rp-card__title">AI Recommendations</h3>
            </div>
            <span class="rp-card__badge">${(recs.sections || []).length} sections</span>
          </div>
          <p class="rp-card__desc" style="margin-bottom:12px">Click any recommendation to expand the full suggestion and rewrite example.</p>
          <div class="rec-list">
            ${buildRecommendations(recs.sections || [])}
          </div>
        </div>

        <!-- Top keywords to add -->
        ${(recs.top_keywords_to_add || []).length ? `
        <div class="rp-card" data-delay="200">
          <div class="rp-card__head">
            <div class="rp-card__title-wrap">
              <span class="rp-card__icon rp-card__icon--green">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              </span>
              <h3 class="rp-card__title">Keywords to Add</h3>
            </div>
          </div>
          <div class="rp-kw-grid">
            ${(recs.top_keywords_to_add || []).map(k => `<span class="rp-kw rp-kw--add">+ ${k}</span>`).join('')}
          </div>
        </div>` : ''}

      </div>
    </div>`;
  }

  /* ── Criteria bars ── */
  function buildCriteriaBars(scores) {
    return CRITERIA_META.map(({ key, label, weight }) => {
      const val   = scores[key] || 0;
      const sl    = scoreLabel(val);
      const color = sl.color;
      return `
        <div class="rp-criteria__row">
          <div class="rp-criteria__label">
            <span class="rp-criteria__name">${label}</span>
            <span class="rp-criteria__weight">${weight}%</span>
          </div>
          <div class="rp-bar">
            <div class="rp-bar__fill" style="width:0%;background:${color}" data-target="${val}"></div>
          </div>
          <span class="rp-criteria__score" style="color:${color}">${val}</span>
        </div>`;
    }).join('');
  }

  /* ── Expandable rec cards ── */
  function buildRecommendations(recSections) {
    if (!recSections.length) {
      return `<div class="rp-empty">
        <span style="font-size:24px">🎉</span>
        <p>No major issues found — your CV is in great shape!</p>
      </div>`;
    }
    return recSections.map((rec, i) => {
      const pColor = rec.priority === 1 ? '#DC2626' : rec.priority === 2 ? '#D97706' : '#2563EB';
      const pLabel = rec.priority === 1 ? 'Critical' : rec.priority === 2 ? 'Important' : 'Minor';
      const pIcon  = rec.priority === 1 ? '🔴' : rec.priority === 2 ? '🟡' : '🔵';
      return `
        <div class="rec-card" style="animation-delay:${i * 70}ms">
          <div class="rec-card__header">
            <div class="rec-card__meta">
              <span class="rec-card__section">${rec.section.toUpperCase()}</span>
              <span class="rec-card__priority" style="color:${pColor};background:${pColor}15;border-color:${pColor}35">
                ${pIcon} ${pLabel}
              </span>
            </div>
            <p class="rec-card__issue">${rec.issue}</p>
            <span class="rec-card__chevron">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="6 9 12 15 18 9"/>
              </svg>
            </span>
          </div>
          <div class="rec-card__body">
            <p class="rec-card__recommendation">${rec.recommendation}</p>
            ${rec.rewrite_example ? `
            <div class="rec-card__rewrite">
              <div class="rec-card__rewrite-label">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/>
                </svg>
                Suggested rewrite
              </div>
              <p class="rec-card__rewrite-text">${rec.rewrite_example}</p>
            </div>` : ''}
          </div>
        </div>`;
    }).join('');
  }

  /* ── Animate number counter ── */
  function animateCounter(el, from, to, duration) {
    if (!el) return;
    const start = performance.now();
    function step(now) {
      const p = Math.min((now - start) / duration, 1);
      const ease = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(from + (to - from) * ease);
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

})();