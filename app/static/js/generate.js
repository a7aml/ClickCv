/* ==========================================================
   generate.js — "Generate Full Resume with AI" wizard
   Depends on: build.core.js (api, showToast, token)
========================================================== */

/* ── State ── */
const WZ = {
  step: 1,
  totalSteps: 5,
};

let wEduCount  = 0;
let wExpCount  = 0;
let wProjCount = 0;

/* ══════════════════════════════════════
   STEP NAVIGATION
══════════════════════════════════════ */
function showStep(n) {
  document.querySelectorAll('.wizard-step').forEach(el => {
    el.classList.toggle('active', Number(el.dataset.step) === n);
  });

  document.querySelectorAll('.stepper__item').forEach(el => {
    const s = Number(el.dataset.step);
    el.classList.remove('active', 'done');
    if (s < n) el.classList.add('done');
    else if (s === n) el.classList.add('active');
  });

  document.querySelectorAll('.stepper__line').forEach((el, idx) => {
    el.classList.toggle('done', (idx + 1) < n);
  });

  const backBtn     = document.getElementById('wizard-back');
  const nextBtn     = document.getElementById('wizard-next');
  const generateBtn = document.getElementById('wizard-generate');

  backBtn.style.visibility = (n === 1) ? 'hidden' : 'visible';

  if (n === WZ.totalSteps) {
    nextBtn.style.display     = 'none';
    generateBtn.style.display = 'inline-flex';
  } else {
    nextBtn.style.display     = 'inline-flex';
    generateBtn.style.display = 'none';
    nextBtn.textContent = (n === WZ.totalSteps - 1) ? 'Next →' : 'Next →';
  }

  WZ.step = n;

  /* Scroll wizard card into view at top */
  document.querySelector('.wizard-card')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function wizardNext() {
  if (!validateStep(WZ.step)) return;
  if (WZ.step < WZ.totalSteps) showStep(WZ.step + 1);
}

function wizardBack() {
  if (WZ.step > 1) showStep(WZ.step - 1);
}

/* ══════════════════════════════════════
   VALIDATION
══════════════════════════════════════ */
function validateStep(step) {
  if (step === 1) {
    const name  = document.getElementById('w-name').value.trim();
    const email = document.getElementById('w-email').value.trim();
    if (!name) {
      showToast('Please enter your full name.', 'error');
      document.getElementById('w-name').focus();
      return false;
    }
    if (!email) {
      showToast('Please enter your email.', 'error');
      document.getElementById('w-email').focus();
      return false;
    }
  }

  if (step === 5) {
    const jd = document.getElementById('w-jd').value.trim();
    if (!jd) {
      showToast('Please paste a job description — AI needs it to tailor your resume.', 'error');
      document.getElementById('w-jd').focus();
      return false;
    }
  }

  return true;
}

/* ══════════════════════════════════════
   EDUCATION ENTRIES
══════════════════════════════════════ */
function addEduEntry() {
  const id = wEduCount++;
  document.getElementById('w-edu-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="w-edu-${id}">
      <button class="entry__remove" type="button" onclick="removeWizardEntry('w-edu-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Degree</label>
          <input type="text" class="wedu-degree" placeholder="Bachelor of Software Engineering"/>
        </div>
        <div class="field">
          <label>Institution</label>
          <input type="text" class="wedu-inst" placeholder="Universiti Teknikal Malaysia Melaka"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>Field of Study</label>
          <input type="text" class="wedu-field" placeholder="Software Engineering"/>
        </div>
        <div class="field">
          <label>Graduation Date</label>
          <input type="text" class="wedu-date" placeholder="2024"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>GPA (optional)</label>
          <input type="text" class="wedu-gpa" placeholder="3.8 / 4.0"/>
        </div>
      </div>
    </div>`);
}

/* ══════════════════════════════════════
   EXPERIENCE ENTRIES
══════════════════════════════════════ */
function addExpEntry() {
  const id = wExpCount++;
  document.getElementById('w-exp-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="w-exp-${id}">
      <button class="entry__remove" type="button" onclick="removeWizardEntry('w-exp-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Job Title</label>
          <input type="text" class="wexp-title" placeholder="Software Engineer"/>
        </div>
        <div class="field">
          <label>Company</label>
          <input type="text" class="wexp-company" placeholder="Company Name"/>
        </div>
      </div>
      <div class="field-row">
        <div class="field">
          <label>Start Date</label>
          <input type="text" class="wexp-start" placeholder="Jan 2023"/>
        </div>
        <div class="field">
          <label>End Date</label>
          <input type="text" class="wexp-end" placeholder="Present"/>
        </div>
      </div>
      <div class="field">
        <label>What did you do? (brief notes — AI will write the bullet points)</label>
        <textarea class="wexp-notes" rows="3"
          placeholder="e.g. Built REST APIs for the company's main product, worked with a small team, used Flask and PostgreSQL, improved page load times..."></textarea>
      </div>
    </div>`);
}

/* ══════════════════════════════════════
   PROJECT ENTRIES
══════════════════════════════════════ */
function addProjEntry() {
  const id = wProjCount++;
  document.getElementById('w-proj-list').insertAdjacentHTML('beforeend', `
    <div class="entry" id="w-proj-${id}">
      <button class="entry__remove" type="button" onclick="removeWizardEntry('w-proj-${id}')">✕</button>
      <div class="field-row">
        <div class="field">
          <label>Project Title</label>
          <input type="text" class="wproj-title" placeholder="ClickCV Platform"/>
        </div>
        <div class="field">
          <label>Tech Stack</label>
          <input type="text" class="wproj-tech" placeholder="Flask, PostgreSQL, Python"/>
        </div>
      </div>
      <div class="field">
        <label>Brief notes (AI will write the description)</label>
        <textarea class="wproj-notes" rows="2"
          placeholder="What does it do? What was your role? Any results?"></textarea>
      </div>
      <div class="field">
        <label>URL (optional)</label>
        <input type="text" class="wproj-url" placeholder="github.com/..."/>
      </div>
    </div>`);
}

/* ══════════════════════════════════════
   REMOVE ENTRY (shared)
══════════════════════════════════════ */
function removeWizardEntry(id) {
  document.getElementById(id)?.remove();
}

/* ══════════════════════════════════════
   SKILLS — TAG INPUT (flat list)
══════════════════════════════════════ */
function addSkillTagWizard(event) {
  if (event && event.key !== 'Enter') return;
  if (event) event.preventDefault();

  const input = document.getElementById('w-skill-input');
  const val   = input.value.trim();
  if (!val) return;

  const tags = document.getElementById('w-skill-tags');
  const tag  = document.createElement('span');
  tag.className = 'skill-tag';
  tag.innerHTML = `${escWizard(val)} <button type="button" class="skill-tag__remove" onclick="this.parentElement.remove()">✕</button>`;
  tags.appendChild(tag);

  input.value = '';
  input.focus();
}

function escWizard(str) {
  return (str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

/* ══════════════════════════════════════
   COLLECT WIZARD DATA
   Returns object matching the
   POST /cv-builder/draft/generate-full
   request body schema.
══════════════════════════════════════ */
function collectWizardData() {
  const contact = {
    name:     document.getElementById('w-name').value.trim(),
    email:    document.getElementById('w-email').value.trim(),
    phone:    document.getElementById('w-phone').value.trim(),
    location: document.getElementById('w-location').value.trim(),
    linkedin: document.getElementById('w-linkedin').value.trim(),
    website:  document.getElementById('w-website').value.trim(),
  };

  const education = [...document.querySelectorAll('#w-edu-list .entry')].map(e => ({
    degree:         e.querySelector('.wedu-degree')?.value.trim()  || '',
    institution:    e.querySelector('.wedu-inst')?.value.trim()    || '',
    field_of_study: e.querySelector('.wedu-field')?.value.trim()   || '',
    end_date:       e.querySelector('.wedu-date')?.value.trim()    || '',
    gpa:            e.querySelector('.wedu-gpa')?.value.trim()     || '',
  })).filter(e => e.degree);

  const experience = [...document.querySelectorAll('#w-exp-list .entry')].map(e => ({
    job_title:  e.querySelector('.wexp-title')?.value.trim()   || '',
    company:    e.querySelector('.wexp-company')?.value.trim() || '',
    start_date: e.querySelector('.wexp-start')?.value.trim()   || '',
    end_date:   e.querySelector('.wexp-end')?.value.trim()     || '',
    notes:      e.querySelector('.wexp-notes')?.value.trim()   || '',
  })).filter(e => e.job_title);

  const skills = [...document.querySelectorAll('#w-skill-tags .skill-tag')]
    .map(t => t.childNodes[0].textContent.trim())
    .filter(Boolean);

  const projects = [...document.querySelectorAll('#w-proj-list .entry')].map(e => ({
    title:      e.querySelector('.wproj-title')?.value.trim() || '',
    tech_stack: e.querySelector('.wproj-tech')?.value.trim()  || '',
    notes:      e.querySelector('.wproj-notes')?.value.trim() || '',
    url:        e.querySelector('.wproj-url')?.value.trim()   || '',
  })).filter(p => p.title);

  return {
    major:           document.getElementById('w-major').value,
    target_title:    document.getElementById('w-target-title').value.trim(),
    job_description: document.getElementById('w-jd').value.trim(),
    contact,
    education,
    experience,
    skills,
    projects,
    certifications: [],
    languages: [],
  };
}

/* ══════════════════════════════════════
   GENERATE — submit to backend
══════════════════════════════════════ */
const GEN_STEP_ORDER = ['contact', 'experience', 'skills', 'projects', 'summary', 'score'];
const GEN_STEP_LABELS = {
  contact:    'Setting up contact & education…',
  experience: 'Writing experience bullet points…',
  skills:     'Organizing your skills…',
  projects:   'Writing project descriptions…',
  summary:    'Writing your professional summary…',
  score:      'Calculating your ATS score…',
};

let _genTimer  = null;
let _genStepIx = 0;

function _genActivateStep(ix) {
  GEN_STEP_ORDER.forEach((key, i) => {
    const el = document.querySelector(`.gen-step[data-step="${key}"]`);
    if (!el) return;
    el.classList.remove('active', 'done');
    if (i < ix) el.classList.add('done');
    else if (i === ix) el.classList.add('active');
  });

  const status = document.getElementById('gen-status');
  if (status && GEN_STEP_ORDER[ix]) {
    status.textContent = GEN_STEP_LABELS[GEN_STEP_ORDER[ix]];
  }
}

function _genFinishAllSteps() {
  GEN_STEP_ORDER.forEach(key => {
    const el = document.querySelector(`.gen-step[data-step="${key}"]`);
    if (el) { el.classList.remove('active'); el.classList.add('done'); }
  });
  const status = document.getElementById('gen-status');
  if (status) status.textContent = 'Done! Redirecting to your resume…';
}

function _genStartProgress() {
  _genStepIx = 0;
  _genActivateStep(0);

  /* Advance one step roughly every 5s — purely cosmetic timing,
     since the backend call is a single synchronous request.
     If the response arrives first, _genFinishAllSteps() takes over. */
  _genTimer = setInterval(() => {
    if (_genStepIx < GEN_STEP_ORDER.length - 1) {
      _genStepIx++;
      _genActivateStep(_genStepIx);
    }
  }, 5000);
}

function _genStopProgress() {
  if (_genTimer) {
    clearInterval(_genTimer);
    _genTimer = null;
  }
}

async function generateResume() {
  if (!validateStep(5)) return;

  const payload = collectWizardData();

  const overlay = document.getElementById('gen-overlay');
  const errorEl = document.getElementById('gen-error');
  errorEl.classList.remove('visible');
  errorEl.textContent = '';

  overlay.classList.add('visible');
  _genStartProgress();

  try {
    const res = await api('POST', '/cv-builder/draft/generate-full', payload);

    _genStopProgress();
    _genFinishAllSteps();

    /* Stash the result so the preview page can render instantly
       without an extra round-trip (cleared after first read there). */
    sessionStorage.setItem(`generated_resume_${res.draft_id}`, JSON.stringify({
      sections:          res.sections,
      score:             res.score,
      major:             payload.major,
      generation_errors: res.generation_errors,
    }));

    /* Brief pause so the user sees the "done" state before redirecting */
    setTimeout(() => {
      window.location.href = `/cv-builder/draft/${res.draft_id}/preview`;
    }, 700);

  } catch (err) {
    _genStopProgress();

    errorEl.textContent = 'Generation failed: ' + err.message + ' — please try again.';
    errorEl.classList.add('visible');

    /* Let the user dismiss and retry */
    setTimeout(() => {
      overlay.classList.remove('visible');
    }, 100);

    showToast('Resume generation failed. Please try again.', 'error');
  }
}

/* ══════════════════════════════════════
   INIT
══════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {
  showStep(1);
  /* Start with one empty entry in each repeatable section for convenience */
  addEduEntry();
  addExpEntry();
});