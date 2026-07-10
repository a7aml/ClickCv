/* ==========================================================
   preview.js — Resume Preview Page (post AI-generation)
   Depends on: build.core.js (api, showToast, token, currentTpl)
               build.preview.js (renderPreview)
   Globals expected: DRAFT_ID (read from <body data-draft-id>)
========================================================== */

const DRAFT_ID = parseInt(document.body.dataset.draftId, 10);

const EMPTY_SECTIONS = {
  contact:        { name: '', email: '', phone: '', location: '', linkedin: '', website: '' },
  summary:        { text: '' },
  experience:     [],
  education:      [],
  skills:         [],
  projects:       [],
  certifications: [],
  languages:      [],
};

/* ══════════════════════════════════════
   LOAD DATA
   1) Prefer sessionStorage (set by generate.js right after
      generation — has sections in one shot).
   2) Fall back to API: GET /draft/<id> for sections.
══════════════════════════════════════ */
async function loadPreviewData() {
  const cacheKey = `generated_resume_${DRAFT_ID}`;
  const cached   = sessionStorage.getItem(cacheKey);

  if (cached) {
    try {
      return JSON.parse(cached);
    } catch (e) { /* fall through to API */ }
  }

  // Fallback — fetch sections from the draft
  const draftRes = await api('GET', `/cv-builder/draft/${DRAFT_ID}`);
  const sections = {};
  (draftRes.sections || []).forEach(s => {
    sections[s.section_type] = s.content_json;
  });

  return { sections, generation_errors: null };
}

/* ══════════════════════════════════════
   RENDER CV
══════════════════════════════════════ */
function renderCv(sections) {
  const d = { ...EMPTY_SECTIONS };

  for (const key of Object.keys(EMPTY_SECTIONS)) {
    if (sections[key] !== undefined && sections[key] !== null) {
      d[key] = sections[key];
    }
  }

  // Ensure contact/summary are objects, others are arrays
  if (typeof d.contact !== 'object' || Array.isArray(d.contact)) d.contact = EMPTY_SECTIONS.contact;
  if (typeof d.summary !== 'object' || Array.isArray(d.summary)) d.summary = EMPTY_SECTIONS.summary;
  for (const key of ['experience', 'education', 'skills', 'projects', 'certifications', 'languages']) {
    if (!Array.isArray(d[key])) d[key] = [];
  }

  currentTpl = 1;
  renderPreview(d);
}

/* ══════════════════════════════════════
   WARNING BANNER — partial AI failures
══════════════════════════════════════ */
function renderWarning(generationErrors) {
  if (!generationErrors || !Object.keys(generationErrors).length) return;

  const failedSections = Object.keys(generationErrors).filter(k => k !== 'score');
  if (!failedSections.length) return;

  const banner = document.getElementById('preview-warning');
  const text   = document.getElementById('preview-warning-text');

  text.textContent =
    `AI generation had trouble with: ${failedSections.join(', ')}. ` +
    `These sections were filled using your original notes instead — you can ` +
    `regenerate them individually using the "✨ AI Enhance" buttons in the builder.`;
  banner.style.display = 'flex';
}

/* ══════════════════════════════════════
   ACTIONS
══════════════════════════════════════ */
function wireActions() {
  document.getElementById('btn-edit').addEventListener('click', () => {
    window.location.href = `/build-cv?draft=${DRAFT_ID}`;
  });

  document.getElementById('btn-download-pdf').addEventListener('click', () => downloadExport('pdf'));
  document.getElementById('btn-download-docx').addEventListener('click', () => downloadExport('docx'));
}

async function downloadExport(format) {
  const btn = format === 'pdf'
    ? document.getElementById('btn-download-pdf')
    : document.getElementById('btn-download-docx');

  const originalText = btn.textContent;
  btn.disabled  = true;
  btn.textContent = 'Preparing…';

  try {
    const res = await fetch(`/cv-builder/draft/${DRAFT_ID}/export`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ format }),
    });

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.error || 'Export failed.');
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `cv_draft_${DRAFT_ID}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

  } catch (err) {
    showToast('Download failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  wireActions();

  try {
    const data = await loadPreviewData();

    renderCv(data.sections || {});
    renderWarning(data.generation_errors);

    // Clear the cache entry — it's served its purpose
    sessionStorage.removeItem(`generated_resume_${DRAFT_ID}`);

  } catch (err) {
    showToast('Could not load your resume: ' + err.message, 'error');
  }
});