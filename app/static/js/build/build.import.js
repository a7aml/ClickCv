/* ==========================================================
   build.import.js — Import existing CV to pre-fill builder
   
   Depends on: build.core.js (api, showToast, token)
               build.form.js (addExperience, addEducation,
                              addProject, addCertification,
                              addLanguage, addSkillCategory)
               build.ui.js   (syncPreview)
   
   Flow:
     1. User clicks "Import CV" button
     2. Hidden file input opens
     3. File sent to POST /cv-builder/import-cv
     4. Response JSON populates every form field
     5. syncPreview() called — live preview updates instantly
========================================================== */

/* ══════════════════════════════════════
   INIT — wire the import button + input
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  const btn   = document.getElementById('import-cv-btn');
  const input = document.getElementById('import-cv-input');

  if (btn && input) {
    btn.addEventListener('click', () => input.click());
    input.addEventListener('change', () => {
      if (input.files.length > 0) {
        handleImport(input.files[0]);
        input.value = ''; /* reset so same file can be re-imported */
      }
    });
  }
});

/* ══════════════════════════════════════
   HANDLE IMPORT
   Sends file to backend, fills fields.
══════════════════════════════════════ */
async function handleImport(file) {
  const btn = document.getElementById('import-cv-btn');

  /* Validate client-side first */
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['pdf', 'docx'].includes(ext)) {
    showToast('Only PDF and DOCX files are supported.', 'error');
    return;
  }
  if (file.size > 5 * 1024 * 1024) {
    showToast('File too large. Maximum is 5 MB.', 'error');
    return;
  }

  /* Show loading state on button */
  if (btn) {
    btn.disabled   = true;
    btn.innerHTML  = '<span class="spinner" style="border-top-color:var(--c-primary);border-color:rgba(37,99,235,.2)"></span> Importing...';
  }

  showToast('📄 Parsing your CV — this takes a few seconds...', '');

  try {
    /* Send as multipart/form-data — NOT JSON */
    const formData = new FormData();
    formData.append('file', file);

    const res = await fetch('/cv-builder/import-cv', {
      method:  'POST',
      headers: { 'Authorization': 'Bearer ' + token },
      body:    formData,
      /* Do NOT set Content-Type — browser sets it with boundary */
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.error || 'Import failed');
    }

    /* Fill all fields from the structured response */
    _fillAllFields(data);
    syncPreview();

    /* Count how many sections were filled */
    const filled = [
      data.contact?.name || data.contact?.email,
      data.summary?.text,
      data.experience?.length > 0,
      data.education?.length  > 0,
      data.skills?.length     > 0,
      data.projects?.length   > 0,
      data.certifications?.length > 0,
    ].filter(Boolean).length;

    showToast(`✓ CV imported — ${filled} sections filled. Review and edit below.`, 'success');

  } catch (err) {
    showToast('Import failed: ' + err.message, 'error');
  } finally {
    if (btn) {
      btn.disabled  = false;
      btn.innerHTML = `
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="17 8 12 3 7 8"/>
          <line x1="12" y1="3" x2="12" y2="15"/>
        </svg>
        Import CV`;
    }
  }
}

/* ══════════════════════════════════════
   FILL ALL FIELDS
   Maps structured JSON → every form input.
   Clears existing entries before filling
   so re-importing doesn't duplicate data.
══════════════════════════════════════ */
function _fillAllFields(d) {
  _fillContact(d.contact  || {});
  _fillSummary(d.summary  || {});
  _fillExperience(d.experience     || []);
  _fillEducation(d.education       || []);
  _fillSkills(d.skills             || []);
  _fillProjects(d.projects         || []);
  _fillCertifications(d.certifications || []);
  _fillLanguages(d.languages       || []);

  /* Open all filled sections so user can review */
  _openFilledSections(d);
}

/* ── Contact ── */
function _fillContact(c) {
  _setVal('c-name',     c.name);
  _setVal('c-email',    c.email);
  _setVal('c-phone',    c.phone);
  _setVal('c-location', c.location);
  _setVal('c-linkedin', c.linkedin);
  _setVal('c-website',  c.website);
}

/* ── Summary ── */
function _fillSummary(s) {
  _setVal('s-text', s.text);
}

/* ── Experience ── */
function _fillExperience(list) {
  /* Clear existing entries */
  document.getElementById('exp-list').innerHTML = '';
  expCount = 0;

  list.forEach(item => {
    addExperience(); /* adds a new entry block and increments expCount */
    const entry = document.querySelector('#exp-list .entry:last-child');
    if (!entry) return;
    _setField(entry, '.exp-title',   item.job_title);
    _setField(entry, '.exp-company', item.company);
    _setField(entry, '.exp-start',   item.start_date);
    _setField(entry, '.exp-end',     item.end_date);
    _setField(entry, '.exp-desc',    item.description);
  });
}

/* ── Education ── */
function _fillEducation(list) {
  document.getElementById('edu-list').innerHTML = '';
  eduCount = 0;

  list.forEach(item => {
    addEducation();
    const entry = document.querySelector('#edu-list .entry:last-child');
    if (!entry) return;
    _setField(entry, '.edu-degree', item.degree);
    _setField(entry, '.edu-inst',   item.institution);
    _setField(entry, '.edu-field',  item.field_of_study);
    _setField(entry, '.edu-date',   item.end_date);
    _setField(entry, '.edu-gpa',    item.gpa);
  });
}

/* ── Skills ── */
function _fillSkills(list) {
  /* Clear existing skill categories */
  document.getElementById('skills-list').innerHTML = '';
  catCount = 0;

  if (!list.length) {
    /* Restore at least one empty category */
    _addFirstSkillCategory();
    return;
  }

  list.forEach((cat, idx) => {
    if (idx === 0) {
      _addFirstSkillCategory();
    } else {
      addSkillCategory();
    }

    /* Find the last .skills-cat added */
    const cats   = document.querySelectorAll('.skills-cat');
    const catEl  = cats[cats.length - 1];
    if (!catEl) return;

    /* Set category name */
    const nameInput = catEl.querySelector('.cat-name');
    if (nameInput) nameInput.value = cat.category || '';

    /* Add skill tags */
    const tagsContainer = catEl.querySelector('.skill-tags');
    const catIndex      = catEl.dataset.cat;
    if (!tagsContainer) return;

    (cat.skills || []).forEach(skill => {
      if (!skill.trim()) return;
      const tag = document.createElement('span');
      tag.className = 'skill-tag';
      tag.innerHTML = `${_escapeHtml(skill)} <button class="skill-tag__remove"
        onclick="this.parentElement.remove();syncPreview()">✕</button>`;
      tagsContainer.appendChild(tag);
    });
  });
}

/* Helper — creates the first skill category (idx 0) */
function _addFirstSkillCategory() {
  const idx = catCount++;
  document.getElementById('skills-list').insertAdjacentHTML('beforeend', `
    <div class="skills-cat" data-cat="${idx}">
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
      <div class="skill-tags" data-cat-tags="${idx}"></div>
    </div>`);
}

/* ── Projects ── */
function _fillProjects(list) {
  document.getElementById('proj-list').innerHTML = '';
  projCount = 0;

  list.forEach(item => {
    addProject();
    const entry = document.querySelector('#proj-list .entry:last-child');
    if (!entry) return;
    _setField(entry, '.proj-title', item.title);
    _setField(entry, '.proj-tech',  item.tech_stack);
    _setField(entry, '.proj-desc',  item.description);
    _setField(entry, '.proj-url',   item.url);
  });
}

/* ── Certifications ── */
function _fillCertifications(list) {
  document.getElementById('cert-list').innerHTML = '';
  certCount = 0;

  list.forEach(item => {
    addCertification();
    const entry = document.querySelector('#cert-list .entry:last-child');
    if (!entry) return;
    _setField(entry, '.cert-name',   item.name);
    _setField(entry, '.cert-issuer', item.issuer);
    _setField(entry, '.cert-date',   item.date);
  });
}

/* ── Languages ── */
function _fillLanguages(list) {
  document.getElementById('lang-list').innerHTML = '';
  langCount = 0;

  list.forEach(item => {
    addLanguage();
    const entry = document.querySelector('#lang-list .entry:last-child');
    if (!entry) return;
    _setField(entry, '.lang-name', item.language);

    /* Match proficiency to select options */
    const prof  = (item.proficiency || '').trim();
    const select = entry.querySelector('.lang-prof');
    if (select && prof) {
      const options = [...select.options].map(o => o.value.toLowerCase());
      const match   = options.find(o => o.includes(prof.toLowerCase()) || prof.toLowerCase().includes(o));
      if (match) select.value = select.options[[...select.options].findIndex(o => o.value.toLowerCase() === match)].value;
    }
  });
}

/* ══════════════════════════════════════
   OPEN FILLED SECTIONS
   Expand accordion sections that have data
   so user can immediately review them.
══════════════════════════════════════ */
function _openFilledSections(d) {
  const toOpen = [];
  if (d.contact?.name || d.contact?.email)  toOpen.push('contact');
  if (d.summary?.text)                       toOpen.push('summary');
  if (d.experience?.length > 0)              toOpen.push('experience');
  if (d.education?.length  > 0)              toOpen.push('education');
  if (d.skills?.length     > 0)              toOpen.push('skills');
  if (d.projects?.length   > 0)              toOpen.push('projects');
  if (d.certifications?.length > 0)          toOpen.push('certifications');
  if (d.languages?.length  > 0)              toOpen.push('languages');

  toOpen.forEach(section => {
    const block = document.querySelector(`[data-section="${section}"]`);
    if (block) block.classList.add('active');
  });

  /* Scroll to top of form */
  document.getElementById('sections-list')?.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ══════════════════════════════════════
   HELPERS
══════════════════════════════════════ */

/** Set value of an input/textarea by element ID */
function _setVal(id, value) {
  const el = document.getElementById(id);
  if (el && value) el.value = value;
}

/** Set value of a field inside an entry block by CSS class */
function _setField(entry, selector, value) {
  const el = entry.querySelector(selector);
  if (el && value) el.value = value;
}

function _escapeHtml(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}