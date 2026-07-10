/* ==========================================================
   build.ui.js — direct builder, AI-assisted, one template.
   Depends on: build.core.js (defines currentTpl, draftId,
   api, showToast, scheduleSaveAll), build.form.js
   (collectData, addSkillTag), build.preview.js (renderPreview,
   escHtml), build.import.js (_fillAllFields — used when
   loading an existing draft)
========================================================== */

const ACTIVE_DRAFT_KEY = 'clickcv_active_draft_id';

/* ══════════════════════════════════════
   INIT
   Priority for which draft to load:
     1. ?draft=<id> in the URL (e.g. "Edit in Builder" from
        the AI-generated resume preview page)
     2. A draft ID saved in localStorage from a previous visit
        (fixes data loss when navigating away and back)
     3. Neither — first-time visit, show the mode-choice modal
        (handled in build.html's inline script)
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  currentTpl = 1;

  const params    = new URLSearchParams(window.location.search);
  const urlDraft  = params.get('draft');
  const saved     = localStorage.getItem(ACTIVE_DRAFT_KEY);
  const draftToLoad = urlDraft || saved;

  if (draftToLoad) {
    loadExistingDraft(parseInt(draftToLoad, 10));
  } else {
    syncPreview();        /* render placeholder immediately */
    createDraft();        /* create backend draft in background */
  }
});

async function createDraft() {
  try {
    const res = await api('POST', '/cv-builder/draft', {
      mode: 'assisted', template_id: 1
    });
    draftId = res.draft_id;
    localStorage.setItem(ACTIVE_DRAFT_KEY, draftId);
  } catch (e) { /* silent — retry on first AI hint */ }
}

/* ══════════════════════════════════════
   LOAD EXISTING DRAFT
   Fetches all saved sections and pre-fills the form (same
   mechanism as Import CV's _fillAllFields), without creating
   a new draft. Remembers this draft for future visits.
══════════════════════════════════════ */
async function loadExistingDraft(id) {
  try {
    const res = await api('GET', `/cv-builder/draft/${id}`);
    draftId = res.draft_id;
    localStorage.setItem(ACTIVE_DRAFT_KEY, draftId);

    const sections = {};
    (res.sections || []).forEach(s => {
      sections[s.section_type] = s.content_json;
    });

    _fillAllFields(sections);
    syncPreview();

  } catch (e) {
    showToast('Could not load your saved CV — starting fresh.', 'error');
    localStorage.removeItem(ACTIVE_DRAFT_KEY);
    /* Fall back to a normal new draft so the page is still usable */
    syncPreview();
    createDraft();
  }
}

/* ══════════════════════════════════════
   CLEAR ALL FIELDS
   Resets the entire form back to empty —
   used by the "Clear All" button.
══════════════════════════════════════ */
function clearAllFields() {
  if (!confirm('Clear all fields? This cannot be undone.')) return;

  /* Contact + Summary */
  ['c-name', 'c-email', 'c-phone', 'c-location', 'c-linkedin', 'c-website', 's-text']
    .forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });

  /* Repeatable entry lists */
  document.getElementById('exp-list').innerHTML  = ''; expCount  = 0;
  document.getElementById('edu-list').innerHTML  = ''; eduCount  = 0;
  document.getElementById('proj-list').innerHTML = ''; projCount = 0;
  document.getElementById('cert-list').innerHTML = ''; certCount = 0;
  document.getElementById('lang-list').innerHTML = ''; langCount = 0;

  /* Skills — reset to a single empty category */
  document.getElementById('skills-list').innerHTML = `
    <div class="skills-cat" data-cat="0">
      <div class="field-row" style="margin-bottom:6px">
        <div class="field">
          <label>Category</label>
          <input type="text" class="cat-name" placeholder="e.g. Programming Languages" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="skill-input-row">
        <input type="text" class="skill-input" placeholder="Add skill, press Enter" onkeydown="addSkillTag(event,this)"/>
        <button class="btn btn--secondary btn--sm" onclick="addSkillTag(null,this.previousElementSibling)">Add</button>
      </div>
      <div class="skill-tags" data-cat-tags="0"></div>
    </div>`;
  catCount = 1;

  /* Collapse all sections except Contact */
  document.querySelectorAll('.section-block').forEach(b => b.classList.remove('active'));
  document.querySelector('[data-section="contact"]')?.classList.add('active');

  /* Clear any open AI hint panels */
  document.querySelectorAll('.ai-hint-panel').forEach(p => {
    p.classList.remove('visible');
    p.innerHTML = '';
  });

  syncPreview();
  showToast('✓ All fields cleared.', 'success');
}

/* ══════════════════════════════════════
   ACCORDION
══════════════════════════════════════ */
function toggleSection(head) {
  head.closest('.section-block').classList.toggle('active');
}

/* ══════════════════════════════════════
   STATUS BADGES
══════════════════════════════════════ */
function updateStatuses(d) {
  const set = (id, filled) => {
    const el = document.getElementById('status-' + id);
    if (!el) return;
    el.textContent = filled ? 'Filled' : 'Empty';
    el.className   = 'section-block__status ' + (filled ? 'status-filled' : 'status-empty');
  };
  set('contact',        d.contact.name || d.contact.email);
  set('summary',        d.summary.text);
  set('experience',     d.experience.length > 0);
  set('education',      d.education.length > 0);
  set('skills',         d.skills.some(s => s.skills.length > 0));
  set('projects',       d.projects.length > 0);
  set('certifications', d.certifications.length > 0);
  set('languages',      d.languages.length > 0);
}

/* ══════════════════════════════════════
   AI HINTS
══════════════════════════════════════ */
async function getAiHint(sectionType) {
  const d     = collectData();
  const panel = document.getElementById('hint-' + sectionType);
  if (!panel) return;

  panel.innerHTML = '<p class="ai-hint-panel__text" style="color:var(--c-muted)">✨ Generating ATS-optimized suggestion...</p>';
  panel.classList.add('visible');

  if (!draftId) {
    await createDraft();
    if (!draftId) {
      panel.innerHTML = '<p class="ai-hint-panel__text" style="color:var(--c-danger)">Could not connect. Please refresh.</p>';
      return;
    }
  }

  try {
    const res = await api('POST', `/cv-builder/draft/${draftId}/hint`, {
      section_type: sectionType,
      content_json: d[sectionType] || {}
    });

    const hint = res.hint;
    let hintHtml = '';
    let applyText = '';

    if (typeof hint === 'object') {
      hintHtml  = Object.entries(hint)
        .map(([k, v]) => `<div style="margin-bottom:5px"><strong style="color:var(--c-primary)">${k}:</strong> ${escHtml(String(v))}</div>`)
        .join('');
      applyText = hint.text || '';
    } else {
      hintHtml  = escHtml(String(hint));
      applyText = String(hint);
    }

    const applyBtn = (sectionType === 'summary' && applyText)
      ? `<button class="ai-apply-btn" onclick="applyHint('summary')">✓ Apply to Summary</button>`
      : '';

    panel.innerHTML = `
      <div class="ai-hint-panel__label">✨ AI Suggestion — ATS Optimized</div>
      <div class="ai-hint-panel__text">${hintHtml}</div>
      ${applyBtn}`;

    panel._applyText = applyText;   /* store on DOM node, avoids escaping issues */

  } catch (err) {
    panel.innerHTML = `<p class="ai-hint-panel__text" style="color:var(--c-danger)">Failed: ${escHtml(err.message)}</p>`;
  }
}

function applyHint(sectionType) {
  const panel = document.getElementById('hint-' + sectionType);
  const text  = panel?._applyText;
  if (!text) return;
  if (sectionType === 'summary') {
    const ta = document.getElementById('s-text');
    if (ta) { ta.value = text; syncPreview(); }
  }
  showToast('AI suggestion applied.', 'success');
}

/* ══════════════════════════════════════
   SYNC PREVIEW — master update function
══════════════════════════════════════ */
function syncPreview() {
  const d = collectData();
  updateStatuses(d);
  scheduleSaveAll(d);
  renderPreview(d);
}