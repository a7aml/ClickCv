/* ==========================================================
   dashboard.analyse.js  (~150 lines)
   Responsibility: analyse button click handler, upload API
   call, run API call, progress updates, error handling.
   Depends on: dashboard.js (window.cvFiles)
               dashboard.results.js (window.renderAnalysisResults)
========================================================== */
(function () {
  'use strict';

  const analyseBtn  = document.getElementById('analyse-btn');
  const majorSelect = document.getElementById('major-select');
  const jdTextarea  = document.getElementById('jd-textarea');

  /* ── Auth ── */
  function getToken() {
    return localStorage.getItem('access_token')
        || sessionStorage.getItem('access_token');
  }

  /* ── Sleep helper ── */
  function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

  /* ── Button state ── */
  function setAnalysing(on) {
    analyseBtn.disabled = on;
    if (on) {
      analyseBtn.innerHTML = `
        <span class="btn-spinner"></span>
        <span id="progress-label">Preparing...</span>`;
    } else {
      analyseBtn.innerHTML = `
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14
                           18.18 21.02 12 17.77 5.82 21.02
                           7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        Analyse CV`;
    }
  }

  function updateProgress(label) {
    const el = document.getElementById('progress-label');
    if (el) el.textContent = label;
  }

  /* ── Toast ── */
  function showToast(message, type = 'info') {
    const existing = document.getElementById('cv-toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.id = 'cv-toast';
    toast.className = `cv-toast cv-toast--${type}`;
    const icon = type === 'error'
      ? '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>'
      : '<polyline points="20 6 9 17 4 12"/>';
    toast.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
           stroke="currentColor" stroke-width="2.5"
           stroke-linecap="round" stroke-linejoin="round">${icon}</svg>
      <span>${message}</span>`;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('cv-toast--show'), 10);
    setTimeout(() => {
      toast.classList.remove('cv-toast--show');
      setTimeout(() => toast.remove(), 400);
    }, 4000);
  }

  /* ── Main handler ── */
  if (analyseBtn) {
    analyseBtn.addEventListener('click', async () => {
      if (!window.cvFiles || !window.cvFiles.length) return;

      /* Validate major — uses pill selector error if available */
      if (!majorSelect || !majorSelect.value) {
        if (typeof window.showMajorError === 'function') {
          window.showMajorError();
        }
        showToast('Please select your industry major first.', 'error');
        return;
      }

      /* Validate auth */
      const token = getToken();
      if (!token) {
        showToast('Session expired. Please log in again.', 'error');
        setTimeout(() => window.location.href = '/login', 1500);
        return;
      }

      /* Start scan animation — replaces spinner */
      const scan = window.showScanAnimation ? window.showScanAnimation() : null;

      try {
        /* ── Step 1: Upload ── */
        const formData = new FormData();
        formData.append('file', window.cvFiles[0].file);
        formData.append('major', majorSelect.value);
        const jd = jdTextarea ? jdTextarea.value.trim() : '';
        if (jd) formData.append('job_description', jd);

        const uploadResp = await fetch('/analysis/upload', {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}` },
          body: formData,
        });
        const uploadData = await uploadResp.json();
        if (!uploadResp.ok) throw new Error(uploadData.error || 'Upload failed.');

        /* ── Step 2: Run ── */
        updateProgress('Running ATS scoring algorithm...');
        await sleep(300);
        updateProgress('Generating AI recommendations...');

        const runResp = await fetch('/analysis/run', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            resume_id:       uploadData.resume_id,
            major:           majorSelect.value,
            job_description: jd,
          }),
        });
        const result = await runResp.json();
        if (!runResp.ok) throw new Error(result.error || 'Analysis failed.');

        updateProgress('Preparing your results...');
        await sleep(400);

        /* ── Step 3: Render ── */
        if (scan) scan.finish();
        setAnalysing(false);
        if (typeof window.renderAnalysisResults === 'function') {
          window.renderAnalysisResults(result, majorSelect.value);
        }

      } catch (err) {
        if (scan) scan.error(err.message);
        setAnalysing(false);
        showToast(err.message || 'Something went wrong. Please try again.', 'error');
      }
    });
  }

})();