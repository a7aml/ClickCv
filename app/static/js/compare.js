/* ==========================================================
   compare.js
   Handles all logic for the CV comparison page.

   Flow:
     1. User uploads CV A + CV B (drag/drop or click)
     2. User pastes job description (mandatory)
     3. CTA appears when all three are ready
     4. Click "Run Comparison" → POST /compare/run (multipart)
     5. Loading animation plays
     6. Results rendered: winner banner, score rings,
        criteria table, AI verdict, strengths & weaknesses

   API endpoints (to be built):
     POST /compare/run   — receives cv_a, cv_b, job_description
     Returns JSON with scores and AI analysis
========================================================== */
(function () {
  'use strict';

  /* ── Auth ── */
  function getToken() {
    return localStorage.getItem('access_token')
        || sessionStorage.getItem('access_token');
  }
  if (!getToken()) { window.location.href = '/login'; return; }

  /* ── State ── */
  let fileA = null;
  let fileB = null;
  let analysisId = null;

  /* ── DOM ── */
  const $ = id => document.getElementById(id);

  const DOM = {
    uploadPhase:  $('cmp-upload-phase'),
    loadingPhase: $('cmp-loading-phase'),
    resultsPhase: $('cmp-results-phase'),

    // Upload
    zoneA:    $('cmp-zone-a'),
    zoneB:    $('cmp-zone-b'),
    inputA:   $('cmp-input-a'),
    inputB:   $('cmp-input-b'),
    idleA:    $('cmp-idle-a'),
    idleB:    $('cmp-idle-b'),
    filledA:  $('cmp-filled-a'),
    filledB:  $('cmp-filled-b'),
    fnameA:   $('cmp-fname-a'),
    fnameB:   $('cmp-fname-b'),
    fmetaA:   $('cmp-fmeta-a'),
    fmetaB:   $('cmp-fmeta-b'),
    ficonA:   $('cmp-ficon-a'),
    ficonB:   $('cmp-ficon-b'),
    removeA:  $('cmp-remove-a'),
    removeB:  $('cmp-remove-b'),

    // JD
    jdInput:   $('cmp-jd-input'),
    jdCounter: $('cmp-jd-counter'),

    // CTA
    cta:        $('cmp-cta'),
    ctaLabelA:  $('cmp-cta-a'),
    ctaLabelB:  $('cmp-cta-b'),
    compareBtn: $('cmp-compare-btn'),

    // Loading
    loadingStep: $('cmp-loading-step'),
    loadingFill: $('cmp-loading-fill'),

    // Results
    winnerBanner:  $('cmp-winner-banner'),
    winnerLabel:   $('cmp-winner-label'),
    winnerTitle:   $('cmp-winner-title'),
    winnerSub:     $('cmp-winner-sub'),
    newComparison: $('cmp-new-comparison'),
    scoreA:   $('cmp-score-a'),
    scoreB:   $('cmp-score-b'),
    bandA:    $('cmp-band-a'),
    bandB:    $('cmp-band-b'),
    arcA:     $('cmp-arc-a'),
    arcB:     $('cmp-arc-b'),
    cardA:    $('cmp-card-a'),
    cardB:    $('cmp-card-b'),
    resFnameA: $('cmp-res-fname-a'),
    resFnameB: $('cmp-res-fname-b'),
    criteriaTable: $('cmp-criteria-table'),
    verdictBody:   $('cmp-verdict-body'),
    swGrid:        $('cmp-sw-grid'),

    // User
    avatar:   $('cmp-avatar'),
    username: $('cmp-username'),
    toasts:   $('cmp-toasts'),
    topbar:   $('topbar'),
    mainEl:   document.querySelector('.cmp-main'),
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

  /* ── Helpers ── */
  function band(s) {
    if (s >= 75) return 'strong';
    if (s >= 65) return 'good';
    if (s >= 50) return 'borderline';
    return 'weak';
  }

  function bandLabel(b) {
    return { strong:'Strong Match', good:'Good Match',
             borderline:'Needs Work', weak:'Weak Match' }[b] || b;
  }

  function ringCol(b) {
    return { strong:'#059669', good:'#2563EB',
             borderline:'#D97706', weak:'#DC2626' }[b] || '#DC2626';
  }

  function barCol(v) {
    if (v >= 75) return '#059669';
    if (v >= 50) return '#2563EB';
    if (v >= 30) return '#D97706';
    return '#DC2626';
  }

  const CIRC = 263.9; // r=42

  function ringOffset(score) {
    return (CIRC - (score / 100) * CIRC).toFixed(2);
  }

  function fmt(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes/1024).toFixed(1)} KB`;
    return `${(bytes/1024/1024).toFixed(1)} MB`;
  }

  function toast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = `cmp-toast cmp-toast--${type}`;
    t.textContent = msg;
    DOM.toasts.appendChild(t);
    setTimeout(() => t.classList.add('cmp-toast--show'), 10);
    setTimeout(() => {
      t.classList.remove('cmp-toast--show');
      setTimeout(() => t.remove(), 400);
    }, 3800);
  }

  /* ── CTA visibility ── */
  function checkCta() {
    const jdReady = DOM.jdInput.value.trim().length >= 50;
    const ready   = fileA && fileB && jdReady;
    DOM.cta.style.display = ready ? 'flex' : 'none';
  }

  /* ── File handling ── */
  function setFile(side, file) {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx'].includes(ext)) {
      toast('Only PDF and DOCX files are supported.', 'error');
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast('File must be under 5 MB.', 'error');
      return;
    }

    if (side === 'a') {
      fileA = file;
      DOM.fnameA.textContent = file.name;
      DOM.fmetaA.textContent = `${ext.toUpperCase()} · ${fmt(file.size)}`;
      DOM.ficonA.className   = `cmp-file-card__icon cmp-file-card__icon--${ext}`;
      DOM.idleA.style.display   = 'none';
      DOM.filledA.style.display = 'block';
      DOM.ctaLabelA.textContent = file.name.length > 18
        ? file.name.slice(0, 15) + '…' : file.name;
    } else {
      fileB = file;
      DOM.fnameB.textContent = file.name;
      DOM.fmetaB.textContent = `${ext.toUpperCase()} · ${fmt(file.size)}`;
      DOM.ficonB.className   = `cmp-file-card__icon cmp-file-card__icon--${ext}`;
      DOM.idleB.style.display   = 'none';
      DOM.filledB.style.display = 'block';
      DOM.ctaLabelB.textContent = file.name.length > 18
        ? file.name.slice(0, 15) + '…' : file.name;
    }
    checkCta();
  }

  function removeFile(side) {
    if (side === 'a') {
      fileA = null;
      DOM.inputA.value       = '';
      DOM.idleA.style.display   = 'flex';
      DOM.filledA.style.display = 'none';
    } else {
      fileB = null;
      DOM.inputB.value       = '';
      DOM.idleB.style.display   = 'flex';
      DOM.filledB.style.display = 'none';
    }
    checkCta();
  }

  /* ── Drop zone wiring ── */
  function wireZone(zone, input, side) {
    // Click to open file picker
    zone.addEventListener('click', e => {
      if (e.target.closest('.cmp-remove-btn')) return;
      input.click();
    });

    // Keyboard
    zone.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') input.click();
    });

    // File input change
    input.addEventListener('change', () => {
      if (input.files[0]) setFile(side, input.files[0]);
      input.value = '';
    });

    // Drag & drop
    zone.addEventListener('dragover', e => {
      e.preventDefault();
      zone.classList.add('cmp-drag-over');
    });
    zone.addEventListener('dragleave', () => {
      zone.classList.remove('cmp-drag-over');
    });
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('cmp-drag-over');
      const f = e.dataTransfer.files[0];
      if (f) setFile(side, f);
    });
  }

  wireZone(DOM.zoneA, DOM.inputA, 'a');
  wireZone(DOM.zoneB, DOM.inputB, 'b');

  DOM.removeA.addEventListener('click', e => { e.stopPropagation(); removeFile('a'); });
  DOM.removeB.addEventListener('click', e => { e.stopPropagation(); removeFile('b'); });

  /* ── JD counter ── */
  DOM.jdInput.addEventListener('input', () => {
    const len = DOM.jdInput.value.length;
    DOM.jdCounter.textContent = `${len} / 8000`;
    checkCta();
  });

  /* ── Loading animation ── */
  const STEPS = [
    { text: 'Extracting text from both CVs…',          pct: 15 },
    { text: 'Detecting sections and keywords…',         pct: 30 },
    { text: 'Scoring CV A against the job description…', pct: 48 },
    { text: 'Scoring CV B against the job description…', pct: 64 },
    { text: 'Running AI comparison analysis…',          pct: 80 },
    { text: 'Generating verdict and recommendations…',  pct: 93 },
  ];

  let stepTimer = null;

  function startLoading() {
    let i = 0;
    function next() {
      if (i >= STEPS.length) return;
      DOM.loadingStep.style.opacity = '0';
      setTimeout(() => {
        DOM.loadingStep.textContent   = STEPS[i].text;
        DOM.loadingStep.style.opacity = '1';
        DOM.loadingFill.style.width   = STEPS[i].pct + '%';
        i++;
        stepTimer = setTimeout(next, 4200);
      }, 280);
    }
    next();
  }

  function stopLoading() {
    clearTimeout(stepTimer);
    DOM.loadingFill.style.width = '100%';
  }

  /* ── Phase switcher ── */
  function showPhase(phase) {
    DOM.uploadPhase.style.display  = phase === 'upload'  ? 'block' : 'none';
    DOM.loadingPhase.style.display = phase === 'loading' ? 'flex'  : 'none';
    DOM.resultsPhase.style.display = phase === 'results' ? 'block' : 'none';
    DOM.mainEl?.scrollTo({ top: 0, behavior: 'smooth' });
  }

  /* ── Run comparison ── */
  DOM.compareBtn.addEventListener('click', async () => {
    const jd = DOM.jdInput.value.trim();
    if (!fileA || !fileB) {
      toast('Please upload both CV A and CV B.', 'error'); return;
    }
    if (jd.length < 50) {
      toast('Please paste a job description (minimum 50 characters).', 'error'); return;
    }

    showPhase('loading');
    startLoading();
    DOM.compareBtn.disabled = true;

    try {
      const formData = new FormData();
      formData.append('cv_a', fileA);
      formData.append('cv_b', fileB);
      formData.append('job_description', jd);

      const res  = await fetch('/compare/run', {
        method:  'POST',
        headers: { 'Authorization': `Bearer ${getToken()}` },
        body:    formData,
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || `HTTP ${res.status}`);
      }

      stopLoading();
      renderResults(data);
      showPhase('results');

    } catch (err) {
      stopLoading();
      showPhase('upload');
      toast(err.message || 'Comparison failed. Please try again.', 'error');
      console.error('[compare]', err);
    } finally {
      DOM.compareBtn.disabled = false;
    }
  });

  /* ── Render results ── delegated to compare.render.js ── */
  function renderResults(data) {
    if (window.CMPRender) {
      window.CMPRender.render(data, fileA, fileB, DOM, CRITERIA, CIRC);
    }
  }


  /* ── New comparison ── */
  DOM.newComparison?.addEventListener('click', () => {
    fileA = null; fileB = null;
    DOM.inputA.value = ''; DOM.inputB.value = '';
    DOM.jdInput.value = '';
    DOM.jdCounter.textContent = '0 / 8000';
    DOM.idleA.style.display   = 'flex';
    DOM.filledA.style.display = 'none';
    DOM.idleB.style.display   = 'flex';
    DOM.filledB.style.display = 'none';
    DOM.cta.style.display     = 'none';
    DOM.cardA.classList.remove('cmp-score-card--winner');
    DOM.cardB.classList.remove('cmp-score-card--winner');
    DOM.arcA.style.strokeDashoffset = CIRC;
    DOM.arcB.style.strokeDashoffset = CIRC;
    showPhase('upload');
  });
window._cmpReset = () => DOM.newComparison?.click();
  /* ── User ── */
  async function loadUser() {
    try {
      const res  = await fetch('/auth/me', {
        headers: { 'Authorization': `Bearer ${getToken()}` }
      });
      if (!res.ok) return;
      const d    = await res.json();
      const name = d.name || d.username || 'User';
      if (DOM.username) DOM.username.textContent = name;
      if (DOM.avatar)   DOM.avatar.textContent   = name.charAt(0).toUpperCase();
    } catch (_) {}
  }

  /* ── Topbar scroll shadow ── */
  if (DOM.mainEl && DOM.topbar) {
    DOM.mainEl.addEventListener('scroll', () =>
      DOM.topbar.classList.toggle('scrolled', DOM.mainEl.scrollTop > 8)
    );
  }

  /* ── Boot ── */
  showPhase('upload');
  loadUser();

})();