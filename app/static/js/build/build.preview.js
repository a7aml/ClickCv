/* ==========================================================
   build.preview.js
   Live CV preview renderer.
   Reads collectData() output and writes HTML into #cv-preview
   based on the currently selected template (currentTpl).
   Depends on: build.core.js, build.form.js
========================================================== */

/* ══════════════════════════════════════
   MAIN RENDERER
   Entry point — called by syncPreview()
   on every input event.
══════════════════════════════════════ */
function renderPreview(d) {
  const paper = document.getElementById('cv-preview');
  if (!paper) return;
  const t = currentTpl;

  const contactLine = [
    d.contact.email,
    d.contact.phone,
    d.contact.location,
    d.contact.linkedin,
    d.contact.website
  ].filter(Boolean).join('  ·  ');

  let html = '';

  if (t === 1) html = renderClassic(d, contactLine);
  else if (t === 2) html = renderSidebar(d);
  else html = renderGeneric(d, contactLine);   /* tpl 3, 4, 5 share same structure */

  paper.innerHTML = html;
}

/* ══════════════════════════════════════
   TEMPLATE 1 — Classic
   Blue gradient header, single column.
══════════════════════════════════════ */
function renderClassic(d, contactLine) {
  let html = `
    <div class="cv-header">
      <div class="cv-header__name">${esc(d.contact.name) || 'Your Name'}</div>
      <div class="cv-header__contact">${esc(contactLine) || '&nbsp;'}</div>
    </div>
    <div class="cv-body">`;

  if (d.summary.text) html += cvSection('Summary',
    `<p style="font-size:11.5px;line-height:1.65;color:#374151">${esc(d.summary.text)}</p>`);

  html += expHtml(d.experience)
       + eduHtml(d.education)
       + skillsHtml(d.skills)
       + projHtml(d.projects)
       + certHtml(d.certifications)
       + langHtml(d.languages);

  return html + '</div>';
}

/* ══════════════════════════════════════
   TEMPLATE 2 — Sidebar
   Dark header with initials avatar,
   two-column body (sidebar + main).
══════════════════════════════════════ */
function renderSidebar(d) {
  const initials = (d.contact.name || '?')
    .split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();

  let html = `
    <div class="cv-header">
      <div class="cv-header__avatar">${initials}</div>
      <div>
        <div class="cv-header__name">${esc(d.contact.name) || 'Your Name'}</div>
        <div class="cv-header__contact">
          ${[d.contact.email, d.contact.phone, d.contact.location]
              .filter(Boolean)
              .map(x => `<span>${esc(x)}</span>`)
              .join('')}
        </div>
      </div>
    </div>
    <div class="cv-body">
      <div class="cv-sidebar">`;

  if (d.skills.length)         html += sidebarSkillsHtml(d.skills);
  if (d.languages.length)      html += sidebarLangHtml(d.languages);
  if (d.certifications.length) html += sidebarCertHtml(d.certifications);

  html += `</div><div class="cv-main">`;

  if (d.summary.text) html += cvSection('Summary',
    `<p style="font-size:11px;line-height:1.65;color:#374151">${esc(d.summary.text)}</p>`);

  html += expHtml(d.experience)
       + eduHtml(d.education)
       + projHtml(d.projects);

  return html + '</div></div>';
}

/* ══════════════════════════════════════
   TEMPLATES 3, 4, 5 — Generic
   All share the same single-column
   structure; CSS classes on .cv-paper
   handle the visual differences.
══════════════════════════════════════ */
function renderGeneric(d, contactLine) {
  let html = `
    <div class="cv-header">
      <div class="cv-header__name">${esc(d.contact.name) || 'Your Name'}</div>
      <div class="cv-header__contact">${esc(contactLine) || '&nbsp;'}</div>
    </div>
    <div class="cv-body">`;

  if (d.summary.text) html += cvSection('Summary',
    `<p style="font-size:11.5px;line-height:1.65;color:#374151">${esc(d.summary.text)}</p>`);

  html += expHtml(d.experience)
       + eduHtml(d.education)
       + skillsHtml(d.skills)
       + projHtml(d.projects)
       + certHtml(d.certifications)
       + langHtml(d.languages);

  return html + '</div>';
}

/* ══════════════════════════════════════
   SECTION BLOCK HELPER
   Wraps content with the section title
   div that CSS styles per template.
══════════════════════════════════════ */
function cvSection(title, content) {
  return `<div><div class="cv-section-title">${title}</div>${content}</div>`;
}

/* ══════════════════════════════════════
   SECTION RENDERERS
   Each returns an HTML string or ''
   if the data array is empty.
══════════════════════════════════════ */
function expHtml(exp) {
  if (!exp.length) return '';
  const items = exp.map(x => !x.job_title ? '' : `
    <div class="cv-entry-item">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <span class="cv-entry-title">${esc(x.job_title)}</span>
        <span style="font-size:10.5px;color:var(--c-muted)">
          ${esc(x.start_date)}${x.end_date ? ' – ' + esc(x.end_date) : ''}
        </span>
      </div>
      ${x.company     ? `<div class="cv-entry-sub">${esc(x.company)}</div>` : ''}
      ${x.description ? `<div class="cv-entry-desc">${esc(x.description)}</div>` : ''}
    </div>`).join('');
  return items ? cvSection('Experience', items) : '';
}

function eduHtml(edu) {
  if (!edu.length) return '';
  const items = edu.map(x => !x.degree ? '' : `
    <div class="cv-entry-item">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <span class="cv-entry-title">${esc(x.degree)}</span>
        <span style="font-size:10.5px;color:var(--c-muted)">${esc(x.end_date)}</span>
      </div>
      ${x.institution ? `
        <div class="cv-entry-sub">
          ${esc(x.institution)}${x.field_of_study ? ' · ' + esc(x.field_of_study) : ''}
        </div>` : ''}
      ${x.gpa ? `<div class="cv-entry-sub">GPA: ${esc(x.gpa)}</div>` : ''}
    </div>`).join('');
  return items ? cvSection('Education', items) : '';
}

function skillsHtml(skills) {
  if (!skills.length) return '';
  const items = skills.map(cat => !cat.skills.length ? '' : `
    <div style="margin-bottom:6px">
      ${cat.category
        ? `<span style="font-size:10px;font-weight:700;color:var(--c-muted);
                        text-transform:uppercase;letter-spacing:.05em">
             ${esc(cat.category)}:
           </span>`
        : ''}
      <div class="cv-skills-wrap" style="display:inline-flex;flex-wrap:wrap;gap:4px">
        ${cat.skills.map(s => `<span class="cv-skill">${esc(s)}</span>`).join('')}
      </div>
    </div>`).join('');
  return items ? cvSection('Skills', items) : '';
}

function projHtml(proj) {
  if (!proj.length) return '';
  const items = proj.map(x => !x.title ? '' : `
    <div class="cv-entry-item">
      <div style="display:flex;justify-content:space-between;align-items:baseline">
        <span class="cv-entry-title">${esc(x.title)}</span>
        ${x.tech_stack
          ? `<span style="font-size:10px;color:var(--c-muted)">${esc(x.tech_stack)}</span>`
          : ''}
      </div>
      ${x.description ? `<div class="cv-entry-desc">${esc(x.description)}</div>` : ''}
    </div>`).join('');
  return items ? cvSection('Projects', items) : '';
}

function certHtml(certs) {
  if (!certs.length) return '';
  const items = certs.map(x => !x.name ? '' : `
    <div class="cv-entry-item">
      <div style="display:flex;justify-content:space-between">
        <span class="cv-entry-title">${esc(x.name)}</span>
        <span style="font-size:10.5px;color:var(--c-muted)">${esc(x.date)}</span>
      </div>
      ${x.issuer ? `<div class="cv-entry-sub">${esc(x.issuer)}</div>` : ''}
    </div>`).join('');
  return items ? cvSection('Certifications', items) : '';
}

function langHtml(langs) {
  if (!langs.length) return '';
  const items = `
    <div style="display:flex;flex-wrap:wrap;gap:8px">
      ${langs.filter(x => x.language)
             .map(x => `<span class="cv-skill">${esc(x.language)} — ${esc(x.proficiency)}</span>`)
             .join('')}
    </div>`;
  return cvSection('Languages', items);
}

/* ══════════════════════════════════════
   SIDEBAR SECTION RENDERERS
   Used only by Template 2 sidebar column.
══════════════════════════════════════ */
function sidebarSkillsHtml(skills) {
  return cvSection('Skills', skills.map(cat => `
    ${cat.category
      ? `<div style="font-size:9px;font-weight:700;color:#64748b;
                     text-transform:uppercase;margin:4px 0 2px">
           ${esc(cat.category)}
         </div>`
      : ''}
    ${cat.skills.map(s => `<span class="cv-skill">${esc(s)}</span>`).join('')}
  `).join(''));
}

function sidebarLangHtml(langs) {
  return cvSection('Languages', langs.filter(x => x.language).map(x => `
    <div style="font-size:10.5px;margin-bottom:3px">
      <span style="font-weight:600">${esc(x.language)}</span>
      <span style="color:#64748b"> ${esc(x.proficiency)}</span>
    </div>`).join(''));
}

function sidebarCertHtml(certs) {
  return cvSection('Certifications', certs.filter(x => x.name).map(x => `
    <div style="font-size:10px;margin-bottom:4px;font-weight:600">
      ${esc(x.name)}
    </div>`).join(''));
}

/* ══════════════════════════════════════
   HTML ESCAPE UTILITY
   Prevents XSS from user input rendered
   directly into the CV preview.
══════════════════════════════════════ */
function esc(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* alias used in build.ui.js hint panel */
const escHtml = esc;