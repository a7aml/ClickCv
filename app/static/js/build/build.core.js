/* ==========================================================
   build.core.js
   State, API helper, toast, auto-save scheduler, init.
   Loaded first — all other build.*.js files depend on this.
========================================================== */

/* ── Shared state ── */
const API        = '';
let token        = localStorage.getItem('access_token') || '';
let currentMode  = 'template';
let currentTpl   = 1;
let draftId      = null;
let autoSaveTimer = null;

const TPL_NAMES = { 1:'Classic', 2:'Sidebar', 3:'Minimal', 4:'Bold', 5:'Accent' };

/* ══════════════════════════════════════
   API HELPER
══════════════════════════════════════ */
async function api(method, path, body) {
  const res = await fetch(API + path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + token
    },
    body: body ? JSON.stringify(body) : undefined
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed');
  return data;
}

/* ══════════════════════════════════════
   TOAST
══════════════════════════════════════ */
function showToast(msg, type = '') {
  const t = document.getElementById('cv-toast');
  t.textContent = msg;
  t.className = 'cv-toast' + (type ? ' cv-toast--' + type : '') + ' show';
  setTimeout(() => t.classList.remove('show'), 3000);
}

/* ══════════════════════════════════════
   ENSURE DRAFT EXISTS
   Called before any action that needs
   a draftId — creates one if missing.
══════════════════════════════════════ */
let _draftCreating = false;

async function ensureDraft() {
  if (draftId) return true;
  if (_draftCreating) return false;
  _draftCreating = true;
  try {
    const res = await api('POST', '/cv-builder/draft', {
      mode: 'assisted', template_id: 1
    });
    draftId = res.draft_id;
    return true;
  } catch (e) {
    showToast('Connection error. Please refresh.', 'error');
    return false;
  } finally {
    _draftCreating = false;
  }
}

/* ══════════════════════════════════════
   AUTO-SAVE SCHEDULER
══════════════════════════════════════ */
function scheduleSaveAll(data) {
  clearTimeout(autoSaveTimer);
  autoSaveTimer = setTimeout(async () => {
    if (!draftId) return;  /* never save to null draft */
    const sections = [
      'contact', 'summary', 'experience', 'education',
      'skills', 'projects', 'certifications', 'languages'
    ];
    for (const [i, s] of sections.entries()) {
      try {
        await api('PUT', `/cv-builder/draft/${draftId}/section`, {
          section_type: s,
          position:     i,
          content_json: data[s] || {}
        });
      } catch (e) {}
    }
    const ind = document.getElementById('save-indicator');
    if (ind) { ind.classList.add('show'); setTimeout(() => ind.classList.remove('show'), 2000); }
  }, 1500);
}

/* ══════════════════════════════════════
   EXPORT
   Requires contact name or email filled.
   Auto-creates draft if missing.
══════════════════════════════════════ */
async function exportDraft(format) {
  /* Check contact info filled */
  const name  = document.getElementById('c-name')?.value?.trim();
  const email = document.getElementById('c-email')?.value?.trim();
  if (!name && !email) {
    showToast('Please fill in at least your name or email first.', 'error');
    /* Scroll to and open contact section */
    const contact = document.querySelector('[data-section="contact"]');
    if (contact) {
      contact.classList.add('active');
      contact.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    return;
  }

  /* Ensure draft exists */
  const ok = await ensureDraft();
  if (!ok) return;

  /* Save current data before exporting */
  const d = collectData();
  const sections = ['contact','summary','experience','education','skills','projects','certifications','languages'];
  for (const [i, s] of sections.entries()) {
    try {
      await api('PUT', `/cv-builder/draft/${draftId}/section`, {
        section_type: s, position: i, content_json: d[s] || {}
      });
    } catch (e) {}
  }

  try {
    showToast(`Preparing ${format.toUpperCase()}...`);
    const res = await fetch(`${API}/cv-builder/draft/${draftId}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + token
      },
      body: JSON.stringify({ format })
    });
    if (!res.ok) {
      let errMsg = 'Export failed';
      try { const errData = await res.json(); errMsg = errData.error || errMsg; } catch (_) {}
      throw new Error(errMsg);
    }
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href = url;
    a.download = `${(name || 'cv').replace(/\s+/g, '_')}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`CV exported as ${format.toUpperCase()} ✓`, 'success');
  } catch (err) {
    showToast('Export failed: ' + err.message, 'error');
  }
}

/* ══════════════════════════════════════
   ANALYZE DRAFT
══════════════════════════════════════ */
async function analyzeDraft() {
  const major = document.getElementById('major-select-builder')?.value;
  if (!major) { showToast('Select a major for analysis.', 'error'); return; }

  const ok = await ensureDraft();
  if (!ok) return;

  const btn = document.getElementById('analyze-btn');
  if (btn) { btn.innerHTML = '<span class="spinner"></span> Analyzing...'; btn.disabled = true; }

  try {
    const res = await api('POST', `/cv-builder/draft/${draftId}/analyze`, { major });
    showResultModal(res);
  } catch (e) {
    showToast('Analysis failed: ' + e.message, 'error');
  } finally {
    if (btn) { btn.innerHTML = '✦ Analyze'; btn.disabled = false; }
  }
}

/* ══════════════════════════════════════
   RESULT MODAL
══════════════════════════════════════ */
function showResultModal(res) {
  const score = Math.round(res.overall_score || 0);
  document.getElementById('modal-score').textContent = score + '%';

  const band      = document.getElementById('modal-band');
  const bandText  = res.score_band ||
    (score >= 75 ? 'Strong Match' : score >= 65 ? 'Good Match' : score >= 50 ? 'Borderline' : 'Weak Match');
  const bandColor = score >= 75 ? '#059669' : score >= 65 ? '#2563EB' : score >= 50 ? '#D97706' : '#DC2626';
  band.textContent       = bandText;
  band.style.color       = bandColor;
  band.style.borderColor = bandColor;

  const scores = res.scores || {};
  document.getElementById('modal-scores').innerHTML = [
    ['Keywords',    scores.keyword_score],
    ['Formatting',  scores.formatting_score],
    ['Structure',   scores.structure_score],
    ['Experience',  scores.experience_recency_score],
    ['Education',   scores.education_score],
    ['Achievements',scores.achievements_score],
  ].filter(([, v]) => v != null)
   .map(([label, val]) => `
    <div class="modal__score-item">
      <div class="modal__score-label">${label}</div>
      <div class="modal__score-val">${Math.round(val)}%</div>
    </div>`).join('');

  document.getElementById('result-modal').classList.add('visible');
}

function closeModal() {
  document.getElementById('result-modal').classList.remove('visible');
}

/* ── Analyze panel toggle ── */
function openAnalyzePanel() {
  const p = document.getElementById('analyze-panel');
  if (p) p.style.display = 'flex';
}
function closeAnalyzePanel() {
  const p = document.getElementById('analyze-panel');
  if (p) p.style.display = 'none';
}

/* ── Token validation on load ── */
(async () => {
  if (!token) return;
  try { await api('GET', '/auth/me'); } catch (e) {}
})();