(function() {
  'use strict';

  const API = '';
  let currentFile = null;
  let currentAnalysis = null;
  let allJobs = [];
  let originalDropzoneHTML = '';

  /* ═══════════════════════════════════════
     DOM Elements
  ═══════════════════════════════════════ */
  const uploadView = document.getElementById('upload-view');
  const resultsView = document.getElementById('results-view');
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const searchBtn = document.getElementById('search-btn');
  const backBtn = document.getElementById('back-btn');
  const jobsList = document.getElementById('jobs-list');
  const countrySelect = document.getElementById('country-select');
  const countryError = document.getElementById('country-error-msg');

  /* ═══════════════════════════════════════
     Utilities
  ═══════════════════════════════════════ */
  function token() {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  }

  function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = `cv-toast cv-toast--${type} cv-toast--show`;
    setTimeout(() => {
      toast.classList.remove('cv-toast--show');
    }, 4000);
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function matchColor(label) {
    if (label === 'good') return '#16A34A';
    if (label === 'fair') return '#D97706';
    return '#DC2626';
  }

  function updateSearchButtonState() {
    const hasCv = currentFile !== null || currentAnalysis !== null;
    if (!hasCv) {
      searchBtn.style.display = 'none';
      return;
    }
    searchBtn.style.display = 'block';
    const countryOk = countrySelect && countrySelect.value && countrySelect.value !== '';
    searchBtn.disabled = !countryOk;
    if (countryError) {
      if (countryOk) countryError.classList.add('hide-error');
      else countryError.classList.remove('hide-error');
    }
  }

  /* ═══════════════════════════════════════
     Reset upload state
  ═══════════════════════════════════════ */
  function resetUploadState() {
    currentFile = null;
    currentAnalysis = null;
    dropZone.classList.remove('dz--filled');
    dropZone.innerHTML = originalDropzoneHTML;
    fileInput.value = '';
    searchBtn.style.display = 'none';
    searchBtn.disabled = true;

    // Re-attach dropzone event listeners after innerHTML reset
    dropZone.addEventListener('click', onDropZoneClick);
    dropZone.addEventListener('dragover', onDragOver);
    dropZone.addEventListener('dragleave', onDragLeave);
    dropZone.addEventListener('drop', onDrop);

    // Deselect any active CV item in left panel
    document.querySelectorAll('.fj-cv-item').forEach(el => el.classList.remove('active'));
  }

  /* ═══════════════════════════════════════
     Drop zone event handlers (named so we can re-attach)
  ═══════════════════════════════════════ */
  function onDropZoneClick() {
    fileInput.click();
  }

  function onDragOver(e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  }

  function onDragLeave() {
    dropZone.classList.remove('drag-over');
  }

  function onDrop(e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const files = e.dataTransfer.files;
    if (files.length) handleFileSelect(files[0]);
  }

  dropZone.addEventListener('click', onDropZoneClick);
  dropZone.addEventListener('dragover', onDragOver);
  dropZone.addEventListener('dragleave', onDragLeave);
  dropZone.addEventListener('drop', onDrop);

  fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) handleFileSelect(e.target.files[0]);
  });

  /* ═══════════════════════════════════════
     File select handler
  ═══════════════════════════════════════ */
  function handleFileSelect(file) {
    const validTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword'
    ];
    if (!validTypes.includes(file.type)) {
      showToast('Please upload a PDF or DOCX file', 'error');
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast('File size must be less than 5MB', 'error');
      return;
    }

    currentFile = file;
    currentAnalysis = null;

    // Deselect left panel items
    document.querySelectorAll('.fj-cv-item').forEach(el => el.classList.remove('active'));

    updateSearchButtonState();
    showToast('CV uploaded successfully!', 'success');

    dropZone.classList.add('dz--filled');
    dropZone.innerHTML = `
      <div class="dz-card">
        <div class="dz-card__icon" style="background:rgba(37,99,235,0.08);border-color:rgba(37,99,235,0.2);color:#2563EB">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
            <polyline points="14 2 14 8 20 8"/>
          </svg>
          <div class="dz-card__badge" style="background:#16A34A">✓</div>
        </div>
        <div class="dz-card__body">
          <div class="dz-card__name">${file.name}</div>
          <div class="dz-card__meta">${formatFileSize(file.size)}</div>
          <div class="dz-card__status">
            <span class="dz-card__dot"></span>
            Ready to analyze
          </div>
        </div>
        <div class="dz-card__actions">
          <button class="dz-btn dz-btn--replace" id="upload-replace-btn">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
            </svg>
            Replace
          </button>
          <button class="dz-btn dz-btn--remove" id="upload-remove-btn" title="Remove CV">✕</button>
        </div>
      </div>
    `;

    document.getElementById('upload-replace-btn').onclick = (e) => {
      e.stopPropagation();
      fileInput.click();
    };

    document.getElementById('upload-remove-btn').onclick = (e) => {
      e.stopPropagation();
      resetUploadState();
    };
  }

  /* ═══════════════════════════════════════
     Country select
  ═══════════════════════════════════════ */
  if (countrySelect) {
    countrySelect.addEventListener('change', () => {
      if (currentFile || currentAnalysis) updateSearchButtonState();
    });
  }

  /* ═══════════════════════════════════════
     Search button
  ═══════════════════════════════════════ */
  searchBtn.addEventListener('click', async () => {
    if (!currentFile && !currentAnalysis) {
      showToast('Please upload a CV first', 'error');
      return;
    }

    if (countrySelect && (!countrySelect.value || countrySelect.value === '')) {
      showToast('Please select a country first', 'error');
      if (countryError) countryError.classList.remove('hide-error');
      return;
    }

    const country = countrySelect ? countrySelect.value : '';

    searchBtn.disabled = true;
    searchBtn.innerHTML = `
      <span style="width:14px;height:14px;border:2px solid rgba(255,255,255,.4);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;display:inline-block"></span>
      Analyzing & Searching...
    `;

    try {
      let detectedMajor = null;

      if (currentAnalysis && currentAnalysis.analysis_id) {
        // Already have analysis from left panel click
        detectedMajor = currentAnalysis.major || 'technology';
      } else if (currentFile) {
        // Step 1: Upload CV
        const formData = new FormData();
        formData.append('file', currentFile);
        formData.append('auto_detect', 'true');

        const uploadRes = await fetch(`${API}/analysis/upload`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token()}` },
          body: formData
        });
        if (!uploadRes.ok) throw new Error('Failed to upload CV');
        const uploadData = await uploadRes.json();

        detectedMajor = uploadData.major || 'technology';

        // Step 2: Run analysis
        const analysisRes = await fetch(`${API}/analysis/run`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token()}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            resume_id: uploadData.resume_id,
            major: detectedMajor
          })
        });
        if (!analysisRes.ok) throw new Error('Failed to analyze CV');
        const analysisData = await analysisRes.json();
        currentAnalysis = analysisData;
        currentAnalysis.detectedMajor = detectedMajor;
      }

      // Step 3: Fetch jobs
      await searchJobs(detectedMajor, country);

      // Step 4: Switch to results view
      switchToResultsView();

    } catch (error) {
      showToast(error.message || 'Something went wrong', 'error');
    } finally {
      searchBtn.disabled = false;
      searchBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/>
          <line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        Search Matching Jobs
      `;
    }
  });

  /* ═══════════════════════════════════════
     Phase 2: Results View
  ═══════════════════════════════════════ */
  async function searchJobs(major, country) {
    const url = country
      ? `${API}/jobs/search?major=${major}&country=${country}`
      : `${API}/jobs/search?major=${major}`;

    const jobsRes = await fetch(url, {
      headers: { 'Authorization': `Bearer ${token()}` }
    });
    if (!jobsRes.ok) throw new Error('Failed to fetch jobs');

    const jobsData = await jobsRes.json();
    allJobs = jobsData.jobs || [];

    if (!allJobs.length) {
      renderEmptyJobs();
      return;
    }

    // Match jobs against CV analysis
    const matchRes = await fetch(`${API}/jobs/match`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token()}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        analysis_id: currentAnalysis.analysis_id,
        jobs: allJobs
      })
    });

    if (matchRes.ok) {
      const matchData = await matchRes.json();
      allJobs = matchData.matched_jobs || allJobs;
    }

    renderJobs(allJobs);
  }

  function switchToResultsView() {
    uploadView.style.display = 'none';
    resultsView.style.display = 'grid';

    const filename = currentFile
      ? currentFile.name
      : (currentAnalysis?.filename || 'CV');

    const meta = currentFile
      ? `${formatFileSize(currentFile.size)} • Uploaded just now`
      : 'Previously analysed';

    document.getElementById('cv-filename').textContent = filename;
    document.getElementById('cv-meta').textContent = meta;

    const detectedIndustry = currentAnalysis?.detectedMajor || currentAnalysis?.major || 'Auto-detected';
    document.getElementById('cv-industry').textContent =
      detectedIndustry.charAt(0).toUpperCase() + detectedIndustry.slice(1);

    const score = Math.round(currentAnalysis?.overall_score || 0);
    document.getElementById('cv-score').textContent = score;

    const circle = document.getElementById('score-circle');
    const circumference = 339.292;
    const offset = circumference - (score / 100) * circumference;
    setTimeout(() => {
      circle.style.strokeDashoffset = offset;
    }, 200);
  }

  function renderJobs(jobs) {
    const hasMatch = jobs[0] && jobs[0].match_score !== undefined;
    document.getElementById('jobs-title').textContent = `${jobs.length} jobs found`;
    document.getElementById('jobs-subtitle').textContent = hasMatch ? 'Sorted by match score' : 'Live results';
    jobsList.innerHTML = jobs.map((job, idx) => buildJobCard(job, idx, hasMatch)).join('');
    setTimeout(() => {
      document.querySelectorAll('.match-bar__fill').forEach(bar => {
        bar.style.width = bar.dataset.target + '%';
      });
    }, 100);
  }

  function buildJobCard(job, idx, hasMatch) {
    const score = job.match_score || 0;
    const label = job.match_label || 'fair';
    const color = job.match_color || matchColor(label);
    const logo = (job.company || '?')[0].toUpperCase();

    const matchSection = hasMatch ? `
      <div class="job-card__match">
        <span class="match-badge match-badge--${label}">${Math.round(score)}% match</span>
        <div class="match-bar">
          <div class="match-bar__fill" data-target="${Math.round(score)}" style="width:0;background:${color}"></div>
        </div>
      </div>
    ` : '';

    return `
      <a href="${job.url || job.link || '#'}" target="_blank" rel="noopener noreferrer" class="job-card"
         style="--match-color:${color};animation:slideIn .3s ${idx * 0.05}s ease both;opacity:0;display:block;text-decoration:none;color:inherit">
        <div class="job-card__top">
          <div class="job-card__logo">${logo}</div>
          <div class="job-card__info">
            <h3 class="job-card__title">${job.title || 'Untitled'}</h3>
            <p class="job-card__company">${job.company || 'Unknown'}</p>
            <div class="job-card__meta">
              ${job.location ? `<span class="job-meta-pill">📍 ${job.location}</span>` : ''}
              ${job.job_type ? `<span class="job-meta-pill">⏱ ${job.job_type}</span>` : ''}
              ${job.salary ? `<span class="job-meta-pill">💰 ${job.salary}</span>` : ''}
            </div>
          </div>
          ${matchSection}
        </div>
      </a>
    `;
  }

  function renderEmptyJobs() {
    jobsList.innerHTML = `
      <div class="jobs-empty">
        <div class="jobs-empty__icon">😕</div>
        <h3 class="jobs-empty__title">No jobs found</h3>
        <p class="jobs-empty__text">Try uploading a different CV or check back later for new opportunities.</p>
      </div>
    `;
  }

  /* ═══════════════════════════════════════
     Back / Replace buttons
  ═══════════════════════════════════════ */
  backBtn.addEventListener('click', () => {
    uploadView.style.display = 'flex';
    resultsView.style.display = 'none';
    resetUploadState();
  });

  document.getElementById('replace-cv-btn')?.addEventListener('click', () => {
    backBtn.click();
  });

  /* ═══════════════════════════════════════
     Left panel: load history & make CVs clickable
  ═══════════════════════════════════════ */
  async function loadHistoryAndRender() {
    try {
      const res = await fetch('/history/analyses', {
        headers: { 'Authorization': `Bearer ${token()}` }
      });
      if (!res.ok) return;
      const data = await res.json();
      const analyses = data.analyses || [];

      document.getElementById('fj-count').textContent = analyses.length;

      if (analyses.length) {
        const scores = analyses.map(a => a.overall_score || 0);
        const avg = Math.round(scores.reduce((a, b) => a + b, 0) / scores.length);
        const best = Math.round(Math.max(...scores));

        document.getElementById('fj-total').textContent = analyses.length;
        document.getElementById('fj-avg').textContent = avg + '%';
        document.getElementById('fj-best').textContent = best + '%';
        document.getElementById('fj-best').style.color =
          best >= 75 ? '#059669' : best >= 65 ? '#2563EB' : best >= 50 ? '#D97706' : '#DC2626';

        const emptyEl = document.getElementById('fj-cvs-empty');
        if (emptyEl) emptyEl.style.display = 'none';

        const listDiv = document.getElementById('fj-cvs-list');
        listDiv.innerHTML = '';

        const majorEmoji = (m) => ({ technology: '💻', medical: '🏥', engineering: '⚙️', financial: '📊', marketing: '📢' }[m] || '📄');

        const fmtRelative = (iso) => {
          const d = new Date(iso), diff = Math.floor((Date.now() - d) / 1000);
          if (diff < 60) return 'just now';
          if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
          if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
          if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
          return d.toLocaleDateString('en-MY', { day: 'numeric', month: 'short' });
        };

        analyses.forEach(a => {
          const score = Math.round(a.overall_score || 0);
          const col = score >= 75 ? '#059669' : score >= 65 ? '#2563EB' : score >= 50 ? '#D97706' : '#DC2626';
          const name = a.filename || 'CV';
          const trunc = name.length > 28 ? name.slice(0, 26) + '…' : name;

          const item = document.createElement('div');
          item.className = 'fj-cv-item';
          item.innerHTML = `
            <div class="fj-cv-item__icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <div class="fj-cv-item__info">
              <span class="fj-cv-item__name" title="${name}">${trunc}</span>
              <div class="fj-cv-item__meta">${majorEmoji(a.major)} ${a.major} · ${fmtRelative(a.created_at)}</div>
            </div>
            <span class="fj-cv-item__score" style="color:${col}">${score}</span>
          `;

          item.addEventListener('click', () => {
            document.querySelectorAll('.fj-cv-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');

            currentFile = null;
            currentAnalysis = {
              analysis_id: a.analysis_id,
              resume_id: a.resume_id,
              major: a.major,
              filename: a.filename,
              overall_score: a.overall_score
            };

            dropZone.classList.add('dz--filled');
            dropZone.innerHTML = `
              <div class="dz-card">
                <div class="dz-card__icon" style="background:rgba(37,99,235,0.08);border-color:rgba(37,99,235,0.2);color:#2563EB">
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                  </svg>
                  <div class="dz-card__badge" style="background:#16A34A">✓</div>
                </div>
                <div class="dz-card__body">
                  <div class="dz-card__name">${a.filename}</div>
                  <div class="dz-card__meta">Analysed CV · Score ${score}%</div>
                  <div class="dz-card__status">
                    <span class="dz-card__dot"></span>
                    Ready for job match
                  </div>
                </div>
                <div class="dz-card__actions">
                  <button class="dz-btn dz-btn--replace" id="panel-replace-btn">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                      <polyline points="1 4 1 10 7 10"/>
                      <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/>
                    </svg>
                    Replace
                  </button>
                  <button class="dz-btn dz-btn--remove" id="panel-remove-btn" title="Remove CV">✕</button>
                </div>
              </div>
            `;

            document.getElementById('panel-replace-btn').onclick = (e) => {
              e.stopPropagation();
              fileInput.click();
            };

            document.getElementById('panel-remove-btn').onclick = (e) => {
              e.stopPropagation();
              resetUploadState();
            };

            updateSearchButtonState();
            showToast(`Loaded: ${a.filename}`, 'success');
          });

          listDiv.appendChild(item);
        });
      }
    } catch (e) {
      console.warn('History load error:', e);
    }
  }

  /* ═══════════════════════════════════════
     Animations
  ═══════════════════════════════════════ */
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideIn {
      from { opacity: 0; transform: translateY(16px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);

  /* ═══════════════════════════════════════
     Init
  ═══════════════════════════════════════ */
  async function init() {
    // Save original dropzone HTML before any changes
    originalDropzoneHTML = dropZone.innerHTML;

    try {
      const r = await fetch(`${API}/auth/me`, {
        headers: { 'Authorization': `Bearer ${token()}` }
      });
      if (r.ok) {
        const d = await r.json();
        const initial = (d.name || 'A')[0].toUpperCase();
        const avatarEl = document.getElementById('fj-avatar') || document.getElementById('user-avatar');
        const nameEl = document.getElementById('fj-name') || document.getElementById('user-name');
        if (avatarEl) avatarEl.textContent = initial;
        if (nameEl) nameEl.textContent = d.name || 'User';
      }
    } catch {}

    await loadHistoryAndRender();
  }

  init();
})();