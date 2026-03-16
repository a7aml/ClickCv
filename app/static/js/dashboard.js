/* ==========================================================
   TechCV Dashboard – Upload CV
   dashboard.js
   Handles: drag-and-drop, file picker, file list render,
            remove, clear-all, and analyse button.
========================================================== */

(function () {
  'use strict';

  /* ── DOM references ── */
  const dropZone    = document.getElementById('drop-zone');
  const fileInput   = document.getElementById('file-input');
  const fileList    = document.getElementById('file-list');
  const fileListSec = document.getElementById('file-list-section');
  const fileCount   = document.getElementById('file-count');
  const analyseCta  = document.getElementById('analyse-cta');
  const ctaDesc     = document.getElementById('cta-desc');
  const clearAllBtn = document.getElementById('clear-all-btn');
  const analyseBtn  = document.getElementById('analyse-btn');

  /* ── State ── */
  let files = []; // Array of { id: number, file: File }

  /* ── Open file picker on click or keyboard ── */
  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  fileInput.addEventListener('change', () => {
    handleFiles(Array.from(fileInput.files));
    fileInput.value = ''; // reset so same file can be re-added
  });

  /* ── Drag-and-drop events ── */
  ['dragenter', 'dragover'].forEach(evt =>
    dropZone.addEventListener(evt, e => {
      e.preventDefault();
      dropZone.classList.add('drag-over');
    })
  );

  ['dragleave', 'dragend', 'drop'].forEach(evt =>
    dropZone.addEventListener(evt, e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
    })
  );

  dropZone.addEventListener('drop', e => {
    const dropped = Array.from(e.dataTransfer.files);
    handleFiles(dropped);
  });

  /* ── File handling helpers ── */

  /**
   * Add valid files to the queue and re-render.
   * @param {File[]} newFiles
   */
  function handleFiles(newFiles) {
    newFiles.forEach(f => {
      if (!isAccepted(f)) return;
      files.push({ id: Date.now() + Math.random(), file: f });
    });
    render();
  }

  /**
   * Returns true if the file extension is accepted.
   * @param {File} f
   * @returns {boolean}
   */
  function isAccepted(f) {
    const ext = getExt(f.name);
    return ['pdf', 'doc', 'docx', 'csv'].includes(ext);
  }

  /**
   * Format a byte count as a human-readable string.
   * @param {number} bytes
   * @returns {string}
   */
  function formatBytes(bytes) {
    if (bytes < 1024)           return bytes + ' B';
    if (bytes < 1024 * 1024)    return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  /**
   * Extract the lowercase extension from a filename.
   * @param {string} name
   * @returns {string}
   */
  function getExt(name) {
    return name.split('.').pop().toLowerCase();
  }

  /**
   * Return the BEM modifier class for the file-type icon.
   * @param {string} ext
   * @returns {string}
   */
  function iconClass(ext) {
    if (ext === 'pdf')                    return 'file-item__icon--pdf';
    if (ext === 'docx' || ext === 'doc') return 'file-item__icon--docx';
    if (ext === 'csv')                    return 'file-item__icon--csv';
    return 'file-item__icon--other';
  }

  /**
   * Return the short text label displayed inside the icon badge.
   * @param {string} ext
   * @returns {string}
   */
  function iconLabel(ext) {
    if (ext === 'pdf')                    return 'PDF';
    if (ext === 'docx' || ext === 'doc') return 'DOC';
    if (ext === 'csv')                    return 'CSV';
    return ext.toUpperCase().slice(0, 3);
  }

  /* ── Render file list ── */
  function render() {
    fileList.innerHTML = '';

    files.forEach(({ id, file }) => {
      const ext  = getExt(file.name);
      const item = document.createElement('div');
      item.className = 'file-item';
      item.setAttribute('role', 'listitem');
      item.setAttribute('data-id', id);

      item.innerHTML = `
        <div class="file-item__icon ${iconClass(ext)}" aria-hidden="true">${iconLabel(ext)}</div>
        <div class="file-item__info">
          <p class="file-item__name" title="${file.name}">${file.name}</p>
          <p class="file-item__meta">${formatBytes(file.size)} &middot; ${ext.toUpperCase()}</p>
        </div>
        <span class="file-item__status file-item__status--ready">
          <span class="file-item__status__dot" aria-hidden="true"></span>Ready
        </span>
        <button
          class="file-item__remove"
          aria-label="Remove ${file.name}"
          data-remove="${id}"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
               stroke="currentColor" stroke-width="2.2"
               stroke-linecap="round" stroke-linejoin="round"
               aria-hidden="true">
            <line x1="18" y1="6"  x2="6"  y2="18"/>
            <line x1="6"  y1="6"  x2="18" y2="18"/>
          </svg>
        </button>
      `;

      fileList.appendChild(item);
    });

    /* Update count badge & visibility */
    const count = files.length;
    fileCount.textContent = count;
    fileListSec.classList.toggle('visible', count > 0);
    analyseCta.classList.toggle('visible', count > 0);
    ctaDesc.textContent = count === 1
      ? '1 file queued and ready for AI analysis.'
      : `${count} files queued and ready for AI analysis.`;
  }

  /* ── Remove individual file ── */
  fileList.addEventListener('click', e => {
    const btn = e.target.closest('[data-remove]');
    if (!btn) return;
    const id = parseFloat(btn.dataset.remove);
    files = files.filter(f => f.id !== id);
    render();
  });

  /* ── Clear all files ── */
  clearAllBtn.addEventListener('click', () => {
    files = [];
    render();
  });

  /* ── Analyse button (wire to your backend here) ── */
  analyseBtn.addEventListener('click', () => {
    if (!files.length) return;

    analyseBtn.textContent = 'Analysing…';
    analyseBtn.disabled = true;

    // TODO: Replace this timeout with a real fetch() / API call
    setTimeout(() => {
      alert(
        `Analysis started for ${files.length} file(s)!\n` +
        '(Connect your backend to process the results.)'
      );

      analyseBtn.innerHTML = `
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2"
             stroke-linecap="round" stroke-linejoin="round"
             aria-hidden="true">
          <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02
                           12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
        </svg>
        Analyse CV
      `;
      analyseBtn.disabled = false;
    }, 1800);
  });
})();