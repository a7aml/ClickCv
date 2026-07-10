/* ==========================================================
   build.form.js
   Repeatable entry adders (experience, education, projects,
   certifications, languages), skill tag system, and the
   collectData() function that reads all form values.
   Depends on: build.core.js, build.ui.js
========================================================== */

/* ── Entry ID counters (module-scoped) ── */
let expCount  = 0;
let eduCount  = 0;
let projCount = 0;
let certCount = 0;
let langCount = 0;
let catCount  = 1;   /* starts at 1 — first category exists in HTML */

/* ══════════════════════════════════════
   EXPERIENCE
══════════════════════════════════════ */
function addExperience() {
  const id = expCount++;
  document.getElementById('exp-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="exp-${id}">
      <button class="entry__remove" onclick="removeEntry('exp-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Job Title</label>
          <input type="text" class="exp-title" placeholder="Software Engineer" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>Company</label>
          <input type="text" class="exp-company" placeholder="Company Name" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>Start Date</label>
          <input type="text" class="exp-start" placeholder="Jan 2023" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>End Date</label>
          <input type="text" class="exp-end" placeholder="Present" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="field">
        <label>Description</label>
        <textarea class="exp-desc" rows="3"
          placeholder="• Developed REST APIs using Flask and PostgreSQL..."
          oninput="syncPreview()"></textarea>
      </div>
    </div>`);
  syncPreview();
}

/* ══════════════════════════════════════
   EDUCATION
══════════════════════════════════════ */
function addEducation() {
  const id = eduCount++;
  document.getElementById('edu-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="edu-${id}">
      <button class="entry__remove" onclick="removeEntry('edu-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Degree</label>
          <input type="text" class="edu-degree" placeholder="Bachelor of Software Engineering" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>Institution</label>
          <input type="text" class="edu-inst" placeholder="Universiti Teknikal Malaysia Melaka" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>Field of Study</label>
          <input type="text" class="edu-field" placeholder="Software Engineering" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>Graduation Date</label>
          <input type="text" class="edu-date" placeholder="2024" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>GPA (optional)</label>
          <input type="text" class="edu-gpa" placeholder="3.8 / 4.0" oninput="syncPreview()"/>
        </div>
      </div>
    </div>`);
  syncPreview();
}

/* ══════════════════════════════════════
   PROJECTS
══════════════════════════════════════ */
function addProject() {
  const id = projCount++;
  document.getElementById('proj-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="proj-${id}">
      <button class="entry__remove" onclick="removeEntry('proj-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Project Title</label>
          <input type="text" class="proj-title" placeholder="ClickCV Platform" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>Tech Stack</label>
          <input type="text" class="proj-tech" placeholder="Flask, PostgreSQL, Python" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="field">
        <label>Description</label>
        <textarea class="proj-desc" rows="2"
          placeholder="Brief description of what you built and its impact..."
          oninput="syncPreview()"></textarea>
      </div>
      <div class="field">
        <label>URL (optional)</label>
        <input type="text" class="proj-url" placeholder="github.com/..." oninput="syncPreview()"/>
      </div>
    </div>`);
  syncPreview();
}

/* ══════════════════════════════════════
   CERTIFICATIONS
══════════════════════════════════════ */
function addCertification() {
  const id = certCount++;
  document.getElementById('cert-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="cert-${id}">
      <button class="entry__remove" onclick="removeEntry('cert-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Certification Name</label>
          <input type="text" class="cert-name"
            placeholder="AWS Certified Solutions Architect" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>Issuer</label>
          <input type="text" class="cert-issuer" placeholder="Amazon Web Services" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>Date</label>
          <input type="text" class="cert-date" placeholder="Jun 2023" oninput="syncPreview()"/>
        </div>
      </div>
    </div>`);
  syncPreview();
}

/* ══════════════════════════════════════
   LANGUAGES
══════════════════════════════════════ */
function addLanguage() {
  const id = langCount++;
  document.getElementById('lang-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="lang-${id}">
      <button class="entry__remove" onclick="removeEntry('lang-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Language</label>
          <input type="text" class="lang-name" placeholder="English" oninput="syncPreview()"/>
        </div>
        <div class="field">
          <label>Proficiency</label>
          <select class="lang-prof" onchange="syncPreview()">
            <option>Native</option>
            <option>Fluent</option>
            <option>Professional</option>
            <option>Intermediate</option>
            <option>Basic</option>
          </select>
        </div>
      </div>
    </div>`);
  syncPreview();
}

/* ══════════════════════════════════════
   REMOVE ANY REPEATABLE ENTRY
══════════════════════════════════════ */
function removeEntry(id) {
  document.getElementById(id)?.remove();
  syncPreview();
}

/* ══════════════════════════════════════
   SKILLS — TAG INPUT
   Adds a skill tag on Enter or button click.
   Tags are stored in the DOM and read by
   collectData().
══════════════════════════════════════ */
function addSkillTag(event, input) {
  if (event && event.key !== 'Enter') return;
  const val = input.value.trim();
  if (!val) return;

  const cat = input.closest('.skills-cat');
  const idx = cat.dataset.cat;
  const tags = cat.querySelector(`[data-cat-tags="${idx}"]`);

  const tag = document.createElement('span');
  tag.className = 'skill-tag';
  tag.innerHTML = `${val} <button class="skill-tag__remove"
    onclick="this.parentElement.remove();syncPreview()">✕</button>`;
  tags.appendChild(tag);

  input.value = '';
  syncPreview();
}

/* ══════════════════════════════════════
   SKILLS — ADD CATEGORY
   Each category has its own name field,
   tag input, and tag list.
══════════════════════════════════════ */
function addSkillCategory() {
  const idx = catCount++;
  document.getElementById('skills-list').insertAdjacentHTML('beforeend', `
    <div class="skills-cat" data-cat="${idx}"
         style="margin-top:10px;padding-top:10px;border-top:1px solid var(--c-border)">
      <div class="field-row" style="margin-bottom:6px">
        <div class="field">
          <label>Category</label>
          <input type="text" class="cat-name" placeholder="e.g. Frameworks" oninput="syncPreview()"/>
        </div>
      </div>
      <div class="skill-input-row">
        <input type="text" class="skill-input"
          placeholder="Add skill, press Enter" onkeydown="addSkillTag(event,this)"/>
        <button class="btn btn--secondary btn--sm"
          onclick="addSkillTag(null,this.previousElementSibling)">Add</button>
      </div>
      <div class="skill-tags" data-cat-tags="${idx}"></div>
    </div>`);
}

/* ══════════════════════════════════════
   COLLECT DATA
   Reads all form inputs and returns a
   structured object matching the backend
   content_json schemas.
══════════════════════════════════════ */
function collectData() {
  return {
    contact: {
      name:     val('c-name'),
      email:    val('c-email'),
      phone:    val('c-phone'),
      location: val('c-location'),
      linkedin: val('c-linkedin'),
      website:  val('c-website')
    },

    summary: {
      text: val('s-text')
    },

    experience: [...document.querySelectorAll('#exp-list .entry')].map(e => ({
      job_title:   e.querySelector('.exp-title')?.value   || '',
      company:     e.querySelector('.exp-company')?.value || '',
      start_date:  e.querySelector('.exp-start')?.value   || '',
      end_date:    e.querySelector('.exp-end')?.value     || '',
      description: e.querySelector('.exp-desc')?.value    || ''
    })),

    education: [...document.querySelectorAll('#edu-list .entry')].map(e => ({
      degree:         e.querySelector('.edu-degree')?.value || '',
      institution:    e.querySelector('.edu-inst')?.value   || '',
      field_of_study: e.querySelector('.edu-field')?.value  || '',
      end_date:       e.querySelector('.edu-date')?.value   || '',
      gpa:            e.querySelector('.edu-gpa')?.value    || ''
    })),

    skills: [...document.querySelectorAll('.skills-cat')].map(cat => ({
      category: cat.querySelector('.cat-name')?.value || '',
      skills:   [...cat.querySelectorAll('.skill-tag')]
                  .map(t => t.childNodes[0].textContent.trim())
    })).filter(s => s.skills.length > 0 || s.category),

    projects: [...document.querySelectorAll('#proj-list .entry')].map(e => ({
      title:       e.querySelector('.proj-title')?.value || '',
      tech_stack:  e.querySelector('.proj-tech')?.value  || '',
      description: e.querySelector('.proj-desc')?.value  || '',
      url:         e.querySelector('.proj-url')?.value   || ''
    })),

    certifications: [...document.querySelectorAll('#cert-list .entry')].map(e => ({
      name:   e.querySelector('.cert-name')?.value   || '',
      issuer: e.querySelector('.cert-issuer')?.value || '',
      date:   e.querySelector('.cert-date')?.value   || ''
    })),

    languages: [...document.querySelectorAll('#lang-list .entry')].map(e => ({
      language:    e.querySelector('.lang-name')?.value || '',
      proficiency: e.querySelector('.lang-prof')?.value || ''
    }))
  };
}

/* ── Shorthand for trimmed input value ── */
function val(id) {
  return document.getElementById(id)?.value?.trim() || '';
}