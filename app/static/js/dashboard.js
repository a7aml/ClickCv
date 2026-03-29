/* ==========================================================
   dashboard.js  — v2

   Changes:
   1. File displays INSIDE the drop zone — no overflow below grid
   2. window.showScanAnimation() — "Neural Document Scan" overlay
      Called by dashboard.analyse.js instead of spinner button
   3. window.cvFiles shared state — unchanged API
========================================================== */
(function () {
  'use strict';

  const dropZone    = document.getElementById('drop-zone');
  const fileInput   = document.getElementById('file-input');
  const analyseCta  = document.getElementById('analyse-cta');
  const ctaDesc     = document.getElementById('cta-desc');
  const clearAllBtn = document.getElementById('clear-all-btn');
  const jdTextarea  = document.getElementById('jd-textarea');
  const charCountEl = document.getElementById('char-count');
  const MAX_CHARS   = 8000;

  window.cvFiles = [];

  /* ── Helpers ── */
  const getExt    = n => n.split('.').pop().toLowerCase();
  const fmtBytes  = b => b < 1024 ? b+' B' : b < 1048576
                        ? (b/1024).toFixed(1)+' KB'
                        : (b/1048576).toFixed(1)+' MB';

  /* Save original empty state */
  const EMPTY_HTML = dropZone.innerHTML;

  /* ══════════════════════════════════════
     DROP ZONE RENDERING
  ══════════════════════════════════════ */
  function renderDropZone() {
    if (!window.cvFiles.length) {
      dropZone.innerHTML = EMPTY_HTML;
      dropZone.classList.remove('dz--filled');
      attachEmptyHandlers();
    } else {
      const { file } = window.cvFiles[0];
      const ext      = getExt(file.name);
      const isPdf    = ext === 'pdf';
      const accent   = isPdf ? '#B91C1C' : '#1D4ED8';
      const accentBg = isPdf ? 'rgba(185,28,28,.09)' : 'rgba(29,78,216,.09)';

      dropZone.classList.add('dz--filled');
      dropZone.innerHTML = `
        <div class="dz-card">
          <div class="dz-card__icon" style="background:${accentBg};border-color:${accent}30">
            <svg width="32" height="40" viewBox="0 0 32 40" fill="none">
              <rect x=".75" y=".75" width="30.5" height="38.5" rx="3.25"
                fill="${accentBg}" stroke="${accent}" stroke-width="1.5"/>
              <path d="M20 .75v9.5h11.25" stroke="${accent}" stroke-width="1.5" fill="none"/>
              <rect class="dz-scan-line" x="4" y="15" width="24" height="2.5"
                rx="1.25" fill="${accent}" opacity=".55"/>
              <rect x="4" y="21" width="18" height="1.8" rx=".9"
                fill="${accent}" opacity=".2"/>
              <rect x="4" y="25" width="22" height="1.8" rx=".9"
                fill="${accent}" opacity=".2"/>
              <rect x="4" y="29" width="14" height="1.8" rx=".9"
                fill="${accent}" opacity=".2"/>
            </svg>
            <span class="dz-card__badge" style="background:${accent}">${ext.toUpperCase()}</span>
          </div>

          <div class="dz-card__body">
            <p class="dz-card__name" title="${file.name}">${file.name}</p>
            <p class="dz-card__meta">${fmtBytes(file.size)} · ${ext.toUpperCase()}</p>
            <div class="dz-card__status">
              <span class="dz-card__dot"></span>Ready for analysis
            </div>
          </div>

          <div class="dz-card__actions">
            <button class="dz-btn dz-btn--replace" id="dz-replace">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.3"
                   stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/>
                <path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>
              </svg>
              Replace
            </button>
            <button class="dz-btn dz-btn--remove" id="dz-remove" aria-label="Remove">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" stroke-width="2.3"
                   stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6"  y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>

          <div class="dz-card__check">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
                 stroke="#059669" stroke-width="3"
                 stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
          </div>
        </div>`;

      document.getElementById('dz-replace').onclick = e => {
        e.stopPropagation(); fileInput.click();
      };
      document.getElementById('dz-remove').onclick = e => {
        e.stopPropagation();
        window.cvFiles = [];
        renderDropZone();
      };
    }
    syncCta();
  }

  function attachEmptyHandlers() {
    dropZone.addEventListener('click',    () => fileInput.click(), { once: true });
    dropZone.addEventListener('keydown',  e => { if (e.key==='Enter'||e.key===' ') fileInput.click(); }, { once: true });
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave',() => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      ingestFiles(e.dataTransfer.files);
    }, { once: true });
  }

  function ingestFiles(list) {
    Array.from(list).forEach(f => {
      if (['pdf','doc','docx'].includes(getExt(f.name)))
        window.cvFiles = [{ id: Date.now(), file: f }];
    });
    renderDropZone();
  }

  function syncCta() {
    const has = window.cvFiles.length > 0;
    analyseCta.classList.toggle('visible', has);
    if (ctaDesc && has)
      ctaDesc.textContent = window.cvFiles[0].file.name + ' — ready for AI analysis.';
  }

  fileInput.addEventListener('change', () => {
    ingestFiles(fileInput.files); fileInput.value = '';
  });

  if (clearAllBtn) clearAllBtn.onclick = () => {
    window.cvFiles = []; renderDropZone();
  };

  /* JD counter */
  if (jdTextarea && charCountEl) {
    jdTextarea.addEventListener('input', () => {
      const n = jdTextarea.value.length;
      charCountEl.textContent = `${n.toLocaleString()} / ${MAX_CHARS.toLocaleString()}`;
      charCountEl.classList.toggle('char-count--warn',  n > MAX_CHARS * .85);
      charCountEl.classList.toggle('char-count--limit', n >= MAX_CHARS);
      jdTextarea.classList.toggle('is-filled', n > 0);
    });
  }

  /* Topbar scroll */
  const topbar   = document.getElementById('topbar');
  const dashMain = document.querySelector('.dashboard');
  if (dashMain && topbar)
    dashMain.addEventListener('scroll', () =>
      topbar.classList.toggle('scrolled', dashMain.scrollTop > 8));

  /* Scroll reveal */
  if (dashMain) {
    const obs = new IntersectionObserver(entries => entries.forEach(e => {
      if (e.isIntersecting) { e.target.classList.add('visible'); obs.unobserve(e.target); }
    }), { root: dashMain, threshold: .08 });
    document.querySelectorAll('.reveal').forEach(el => obs.observe(el));
  }

  /* ══════════════════════════════════════
     NEURAL DOCUMENT SCAN ANIMATION
     
     Concept: The CV gets "disassembled" into
     a floating 3D blueprint, scanned by a laser
     that reveals glowing data nodes connected by
     circuit traces — then implodes into the score.

     Triggered by dashboard.analyse.js via
     window.showScanAnimation().
     Returns { finish(), error() } control object.
  ══════════════════════════════════════ */
  window.showScanAnimation = function () {
    document.getElementById('scan-overlay')?.remove();

    const o = document.createElement('div');
    o.id = 'scan-overlay';
    o.innerHTML = `
      <!-- Starfield particles -->
      <canvas id="scan-canvas"></canvas>

      <!-- Central scanner panel -->
      <div class="scan-panel" id="scan-panel">

        <!-- Document ghost -->
        <div class="scan-ghost">
          <div class="sg-corner sg-tl"></div>
          <div class="sg-corner sg-tr"></div>
          <div class="sg-corner sg-bl"></div>
          <div class="sg-corner sg-br"></div>
          <div class="sg-lines">
            ${Array.from({length:13}, (_,i) =>
              `<div class="sg-line" style="--i:${i};width:${50+Math.random()*45}%"></div>`
            ).join('')}
          </div>
          <!-- The laser beam -->
          <div class="scan-beam" id="scan-beam"></div>
        </div>

        <!-- Criteria nodes (appear post-scan) -->
        <div class="scan-criteria" id="scan-criteria">
          ${[
            {k:'KW', label:'Keywords',   x:12, y:20, c:'#2563EB'},
            {k:'FT', label:'Formatting', x:78, y:28, c:'#06B6D4'},
            {k:'SC', label:'Sections',   x:8,  y:55, c:'#8B5CF6'},
            {k:'EX', label:'Experience', x:80, y:58, c:'#F59E0B'},
            {k:'ED', label:'Education',  x:28, y:80, c:'#10B981'},
            {k:'AC', label:'Achieve.',   x:68, y:80, c:'#EF4444'},
          ].map(n => `
            <div class="sc-node" style="left:${n.x}%;top:${n.y}%;--nc:${n.c}" data-label="${n.label}">
              <span>${n.k}</span>
            </div>`).join('')}
          <svg class="sc-lines-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
            <line x1="12" y1="20" x2="78" y2="28" class="sc-edge"/>
            <line x1="78" y1="28" x2="80" y2="58" class="sc-edge"/>
            <line x1="8"  y1="55" x2="68" y2="80" class="sc-edge"/>
            <line x1="28" y1="80" x2="80" y2="58" class="sc-edge"/>
            <line x1="12" y1="20" x2="8"  y2="55" class="sc-edge"/>
            <line x1="78" y1="28" x2="68" y2="80" class="sc-edge"/>
            <line x1="8"  y1="55" x2="28" y2="80" class="sc-edge"/>
          </svg>
        </div>
      </div>

      <!-- Status -->
      <div class="scan-status-row">
        <div class="scan-pulse-ring"></div>
        <span class="scan-status-text" id="scan-msg">Initialising neural scan...</span>
      </div>

      <!-- Progress -->
      <div class="scan-track">
        <div class="scan-fill" id="scan-fill"></div>
        <div class="scan-fill-glow" id="scan-fill-glow"></div>
      </div>`;

    document.body.appendChild(o);
    requestAnimationFrame(() => o.classList.add('scan-visible'));

    /* ── Particle canvas ── */
    const canvas = document.getElementById('scan-canvas');
    const ctx    = canvas.getContext('2d');
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;

    const particles = Array.from({length: 60}, () => ({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      r: Math.random() * 1.5 + .3,
      vx: (Math.random() - .5) * .4,
      vy: (Math.random() - .5) * .4,
      a: Math.random() * .5 + .1,
    }));

    let animId;
    function drawParticles() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach(p => {
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0) p.x = canvas.width;
        if (p.x > canvas.width) p.x = 0;
        if (p.y < 0) p.y = canvas.height;
        if (p.y > canvas.height) p.y = 0;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI*2);
        ctx.fillStyle = `rgba(99,179,237,${p.a})`;
        ctx.fill();
      });
      animId = requestAnimationFrame(drawParticles);
    }
    drawParticles();

    /* ── Progress & messages ── */
    const msgs = [
      {t:'Extracting document structure...',  p:10},
      {t:'Running NLP section detection...',  p:24},
      {t:'Scoring keyword density...',        p:38},
      {t:'Analysing ATS compatibility...',    p:52},
      {t:'Detecting formatting issues...',    p:65},
      {t:'Measuring achievement impact...',   p:76},
      {t:'Generating AI recommendations...', p:87},
      {t:'Compiling your report...',          p:95},
    ];

    const msgEl  = document.getElementById('scan-msg');
    const fillEl = document.getElementById('scan-fill');
    const glowEl = document.getElementById('scan-fill-glow');

    let mi = 0;
    const tick = setInterval(() => {
      if (mi >= msgs.length) { clearInterval(tick); return; }
      const m = msgs[mi++];
      msgEl.style.opacity = '0';
      setTimeout(() => { msgEl.textContent = m.t; msgEl.style.opacity = '1'; }, 180);
      fillEl.style.width = m.p + '%';
      glowEl.style.width = m.p + '%';
    }, 700);

    /* Reveal nodes after beam sweep (1.6s) */
    setTimeout(() => {
      document.getElementById('scan-criteria')?.classList.add('sc-visible');
    }, 1600);

    return {
      finish() {
        clearInterval(tick);
        cancelAnimationFrame(animId);
        fillEl.style.width  = '100%';
        glowEl.style.width  = '100%';
        msgEl.textContent   = '✓ Analysis complete';
        o.classList.add('scan-success');
        setTimeout(() => {
          o.style.opacity = '0';
          o.style.transform = 'scale(1.04)';
          setTimeout(() => o.remove(), 550);
        }, 380);
      },
      error(msg) {
        clearInterval(tick);
        cancelAnimationFrame(animId);
        o.classList.add('scan-error');
        msgEl.textContent = msg || 'Analysis failed. Please try again.';
        setTimeout(() => {
          o.style.opacity = '0';
          setTimeout(() => o.remove(), 500);
        }, 2200);
      }
    };
  };

  /* ── Boot ── */
  renderDropZone();

})();