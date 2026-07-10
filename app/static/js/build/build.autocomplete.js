/* ==========================================================
   build.autocomplete.js  — v3

   Architecture change from v2:
   Instead of a mirror-div behind the textarea (which caused
   text overlap), we now use a SUFFIX GHOST approach:

   - The textarea stays completely unchanged visually
   - A read-only styled div appears BELOW the textarea
     showing ONLY the remaining suggestion (what the user
     hasn't typed yet), with a clear "continue →" style
   - Tab appends ONLY the remainder to el.value — never
     overwrites what the user already typed
   - Loading: small 3-dot badge in bottom-right of field
     appears after 400ms while waiting for the AI

   Fix summary:
   1. No more text overlap — ghost is below, not behind
   2. Tab appends correctly — reads el.value at press time
   3. Loading badge with bouncing dots + "AI thinking"
========================================================== */

/* ── State ── */
const AC = {
  timer:      null,
  loadTimer:  null,
  cache:      {},
  busy:       false,
  ghostEl:    null,   /* suffix ghost div */
  hintEl:     null,   /* Tab/Esc hint pill */
  loaderEl:   null,   /* bouncing dots badge */
  ghostFor:   null,   /* which input owns the ghost */
  suggestion: '',     /* full suggestion from API */
};

/* ══════════════════════════════════════════════════════
   GHOST — suffix-only display
   Shows ONLY the part the user hasn't typed, in a
   styled div below the textarea. No overlap possible.
══════════════════════════════════════════════════════ */
function acShowGhost(el, suggestion, typedAtFetchTime) {
  acHideGhost();
  if (!suggestion || !el) return;

  /* Show ONLY what will be APPENDED so user sees what Tab will add.
     If suggestion includes user's text -> show the new part only.
     If suggestion is already a suffix  -> show it directly.        */
  const currentVal = el.value;
  let display;

  if (suggestion.toLowerCase().startsWith(currentVal.toLowerCase()) && currentVal.length > 0) {
    display = suggestion.slice(currentVal.length);
  } else {
    display = suggestion;
  }

  if (!display.trim()) return; /* nothing new to add */

  AC.suggestion = suggestion;
  AC.ghostFor   = el;

  /* Ensure wrapper */
  const wrapper = ensureWrapper(el);

  /* Ghost suffix div — below the field */
  const ghost = document.createElement('div');
  ghost.className = 'ac-ghost';
  ghost.setAttribute('aria-hidden', 'true');
  ghost.setAttribute('role', 'presentation');

  /* Icon */
  const icon = document.createElement('span');
  icon.className = 'ac-ghost__icon';
  icon.textContent = '✦';

  /* Text */
  const text = document.createElement('span');
  text.className = 'ac-ghost__text';
  text.textContent = display.length > 120 ? display.slice(0, 120) + '…' : display;

  ghost.appendChild(icon);
  ghost.appendChild(text);
  wrapper.appendChild(ghost);
  AC.ghostEl = ghost;

  /* Hint pill */
  acShowHint(wrapper);
}

function acHideGhost() {
  AC.suggestion = '';
  AC.ghostFor   = null;
  if (AC.ghostEl)  { AC.ghostEl.remove();  AC.ghostEl = null; }
  if (AC.hintEl)   { AC.hintEl.remove();   AC.hintEl  = null; }
  /* Clean up any orphaned hints */
  document.querySelectorAll('.ac-ghost, .ac-hint').forEach(e => e.remove());
}

/* ══════════════════════════════════════════════════════
   HINT PILL — Tab / Esc instruction
══════════════════════════════════════════════════════ */
function acShowHint(wrapper) {
  if (AC.hintEl) { AC.hintEl.remove(); AC.hintEl = null; }
  const hint = document.createElement('div');
  hint.className = 'ac-hint';
  hint.innerHTML =
    '<kbd>↹ Tab</kbd> to accept &nbsp;·&nbsp; <kbd>Esc</kbd> to dismiss';
  wrapper.appendChild(hint);
  AC.hintEl = hint;
}

/* ══════════════════════════════════════════════════════
   LOADING BADGE — bottom-right of field
   Appears after 400ms delay so fast responses
   never show it (cache hits, fast network).
══════════════════════════════════════════════════════ */
function acShowLoader(el) {
  acHideLoader();
  AC.loadTimer = setTimeout(() => {
    if (document.activeElement !== el) return; /* user left field */
    const wrapper = ensureWrapper(el);
    const loader = document.createElement('div');
    loader.className = 'ac-loader';
    loader.setAttribute('aria-label', 'AI generating suggestion');
    loader.innerHTML = `
      <span class="ac-loader__dot"></span>
      <span class="ac-loader__dot"></span>
      <span class="ac-loader__dot"></span>
      <span class="ac-loader__label">AI thinking</span>`;
    wrapper.appendChild(loader);
    AC.loaderEl = loader;
  }, 400);
}

function acHideLoader() {
  clearTimeout(AC.loadTimer);
  AC.loadTimer = null;
  if (AC.loaderEl) { AC.loaderEl.remove(); AC.loaderEl = null; }
  document.querySelectorAll('.ac-loader').forEach(e => e.remove());
}

/* ══════════════════════════════════════════════════════
   WRAPPER HELPER
   Ensures the field is inside a .ac-wrap div
   (needed for absolute positioning of ghost/loader).
══════════════════════════════════════════════════════ */
function ensureWrapper(el) {
  let wrapper = el.parentElement;
  if (wrapper && wrapper.classList.contains('ac-wrap')) return wrapper;
  const w = document.createElement('div');
  w.className = 'ac-wrap';
  el.parentNode.insertBefore(w, el);
  w.appendChild(el);
  return w;
}

/* ══════════════════════════════════════════════════════
   WIRE ONE FIELD
══════════════════════════════════════════════════════ */
function acWireField(el, fieldName, getContext) {
  /* Focus → trigger suggestion after short delay */
  el.addEventListener('focus', () => {
    clearTimeout(AC.timer);
    AC.timer = setTimeout(() => acFetch(el, fieldName, getContext), 700);
  });

  /* Blur → hide everything (with delay so Tab fires first) */
  el.addEventListener('blur', () => {
    clearTimeout(AC.timer);
    acHideLoader();
    setTimeout(acHideGhost, 180);
  });

  /* Input → reset and re-trigger */
  el.addEventListener('input', () => {
    acHideGhost();
    acHideLoader();
    clearTimeout(AC.timer);
    if (el.value.length > 200) return;
    AC.timer = setTimeout(() => acFetch(el, fieldName, getContext), 850);
  });

  /* Keyboard shortcuts */
  el.addEventListener('keydown', e => {
    /* ── Tab: append remainder only ── */
    if (e.key === 'Tab' && AC.suggestion && AC.ghostFor === el) {
      e.preventDefault();

      const currentVal = el.value;
      const sug        = AC.suggestion;

      /* ALWAYS append the suggestion to what the user typed.
         The AI returns a completion/suffix, not the full text.
         Three cases:

         Case A: suggestion IS the full sentence starting from the
                 beginning (e.g. user typed "I am" and AI sent back
                 "I am a software engineer with...") → strip overlap.

         Case B: suggestion is a pure suffix (e.g. user typed "I am"
                 and AI sent " a software engineer with...") → just append.

         Case C: suggestion is unrelated / field was empty → append as-is.

         In ALL cases we NEVER discard currentVal. */

      let toAppend;
      if (sug.toLowerCase().startsWith(currentVal.toLowerCase()) && currentVal.length > 0) {
        /* Case A — suggestion includes what user typed → take only the new part */
        toAppend = sug.slice(currentVal.length);
      } else {
        /* Case B / C — suggestion is already a suffix or standalone → append directly */
        toAppend = sug;
      }

      el.value = currentVal + toAppend;

      acHideGhost();
      acHideLoader();

      /* Notify syncPreview and any other listeners */
      el.dispatchEvent(new Event('input', { bubbles: true }));

      /* Advance focus to next field */
      const focusables = [
        ...document.querySelectorAll(
          'input:not([type=hidden]):not([disabled]),' +
          'textarea:not([disabled]),' +
          'select:not([disabled])'
        )
      ];
      const idx = focusables.indexOf(el);
      if (idx >= 0 && focusables[idx + 1]) focusables[idx + 1].focus();
      return;
    }

    /* Esc: dismiss */
    if (e.key === 'Escape' && AC.suggestion) {
      e.preventDefault();
      acHideGhost();
      acHideLoader();
    }
  });
}

/* ══════════════════════════════════════════════════════
   FETCH SUGGESTION FROM API
══════════════════════════════════════════════════════ */
async function acFetch(el, fieldName, getContext) {
  /* Wait for draftId */
  if (typeof draftId === 'undefined' || !draftId) {
    setTimeout(() => {
      if (draftId && document.activeElement === el) {
        acFetch(el, fieldName, getContext);
      }
    }, 1500);
    return;
  }

  if (AC.busy) return;
  if (document.activeElement !== el) return;

  const typed   = el.value.trim();
  const context = getContext();
  const cacheKey = `${fieldName}|${typed.slice(0, 60)}|${JSON.stringify(context).slice(0, 120)}`;

  /* Cache hit → instant, no loader */
  if (AC.cache[cacheKey] !== undefined) {
    if (AC.cache[cacheKey] && document.activeElement === el) {
      acShowGhost(el, AC.cache[cacheKey], typed);
    }
    return;
  }

  /* Show loader after 400ms */
  acShowLoader(el);
  AC.busy = true;

  try {
    const res = await api('POST', `/cv-builder/draft/${draftId}/autocomplete`, {
      field_name:      fieldName,
      current_value:   typed,
      section_context: context,
    });

    const sug = (res.suggestion || '').trim();
    AC.cache[cacheKey] = sug;

    acHideLoader();
    if (sug && document.activeElement === el) {
      acShowGhost(el, sug, typed);
    }
  } catch (err) {
    acHideLoader();
    console.debug('AC fetch failed (non-critical):', err.message);
  } finally {
    AC.busy = false;
  }
}

/* ══════════════════════════════════════════════════════
   INIT + DYNAMIC WIRING
══════════════════════════════════════════════════════ */
function initAutocomplete() {
  const summary = document.getElementById('s-text');
  if (summary) {
    acWireField(summary, 'summary_text', () => ({
      name:     document.getElementById('c-name')?.value     || '',
      location: document.getElementById('c-location')?.value || '',
    }));
  }

  const root = document.getElementById('sections-list');
  if (root) {
    const observer = new MutationObserver(acWireDynamic);
    observer.observe(root, { childList: true, subtree: true });
  }
  acWireDynamic();
}

function acWireDynamic() {
  document.querySelectorAll('.exp-desc:not([data-ac])').forEach(el => {
    el.dataset.ac = '1';
    acWireField(el, 'exp_description', () => ({
      job_title: el.closest('.entry')?.querySelector('.exp-title')?.value   || '',
      company:   el.closest('.entry')?.querySelector('.exp-company')?.value || '',
    }));
  });

  document.querySelectorAll('.exp-title:not([data-ac])').forEach(el => {
    el.dataset.ac = '1';
    acWireField(el, 'exp_job_title', () => ({
      company: el.closest('.entry')?.querySelector('.exp-company')?.value || '',
    }));
  });

  document.querySelectorAll('.proj-desc:not([data-ac])').forEach(el => {
    el.dataset.ac = '1';
    acWireField(el, 'proj_description', () => ({
      title:      el.closest('.entry')?.querySelector('.proj-title')?.value || '',
      tech_stack: el.closest('.entry')?.querySelector('.proj-tech')?.value  || '',
    }));
  });

  document.querySelectorAll('.edu-degree:not([data-ac])').forEach(el => {
    el.dataset.ac = '1';
    acWireField(el, 'edu_degree', () => ({
      institution: el.closest('.entry')?.querySelector('.edu-inst')?.value || '',
    }));
  });

  document.querySelectorAll('.edu-field:not([data-ac])').forEach(el => {
    el.dataset.ac = '1';
    acWireField(el, 'edu_field_of_study', () => ({
      degree:      el.closest('.entry')?.querySelector('.edu-degree')?.value || '',
      institution: el.closest('.entry')?.querySelector('.edu-inst')?.value  || '',
    }));
  });

  document.querySelectorAll('.cert-name:not([data-ac])').forEach(el => {
    el.dataset.ac = '1';
    acWireField(el, 'cert_name', () => ({
      issuer: el.closest('.entry')?.querySelector('.cert-issuer')?.value || '',
    }));
  });
}

/* Hide ghost on scroll */
document.addEventListener('scroll', acHideGhost, true);

/* Boot */
document.addEventListener('DOMContentLoaded', initAutocomplete);


/* ══════════════════════════════════════════════════════
   STYLES — injected at runtime
   (copy to build.css if you prefer a separate file)
══════════════════════════════════════════════════════ */
(function injectAcStyles() {
  if (document.getElementById('ac-styles')) return;
  const s = document.createElement('style');
  s.id = 'ac-styles';
  s.textContent = `

/* ── Wrapper: needed for loader absolute positioning ── */
.ac-wrap {
  position: relative;
  display: block;
}

/* ════════════════════════════════════════
   GHOST SUGGESTION BOX
   Appears BELOW the textarea/input.
   Shows only the remaining suffix text.
════════════════════════════════════════ */
.ac-ghost {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 4px;
  padding: 7px 11px;
  border-radius: 8px;
  background: rgba(37, 99, 235, 0.04);
  border: 1px solid rgba(37, 99, 235, 0.15);
  border-left: 3px solid rgba(37, 99, 235, 0.35);
  animation: acGhostIn 0.18s ease both;
  cursor: default;
  user-select: none;
}

@keyframes acGhostIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.ac-ghost__icon {
  font-size: 9px;
  color: rgba(37, 99, 235, 0.45);
  margin-top: 2px;
  flex-shrink: 0;
  line-height: 1;
}

.ac-ghost__text {
  font-size: 12.5px;
  line-height: 1.55;
  color: rgba(37, 99, 235, 0.55);
  font-style: italic;
  font-family: inherit;
  word-break: break-word;
}

/* ════════════════════════════════════════
   HINT PILL — Tab / Esc
════════════════════════════════════════ */
.ac-hint {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  margin-top: 5px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.05);
  border: 1px solid rgba(37, 99, 235, 0.14);
  font-size: 11px;
  font-weight: 500;
  color: rgba(37, 99, 235, 0.65);
  animation: acHintIn 0.2s ease both;
  animation-delay: 0.05s;
}

@keyframes acHintIn {
  from { opacity: 0; transform: translateY(3px); }
  to   { opacity: 1; transform: translateY(0); }
}

.ac-hint kbd {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.09);
  border: 1px solid rgba(37, 99, 235, 0.18);
  font-size: 10px;
  font-family: inherit;
  font-weight: 700;
  color: #2563EB;
  letter-spacing: 0.01em;
}

/* ════════════════════════════════════════
   LOADING BADGE
   Bottom-right corner inside the field wrapper.
   3 bouncing dots + "AI thinking" label.
════════════════════════════════════════ */
.ac-loader {
  position: absolute;
  bottom: 8px;
  right: 10px;
  z-index: 10;
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 9px 4px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(37, 99, 235, 0.20);
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.12);
  pointer-events: none;
  animation: acLoaderIn 0.2s ease both;
}

@keyframes acLoaderIn {
  from { opacity: 0; transform: scale(0.8); }
  to   { opacity: 1; transform: scale(1); }
}

.ac-loader__dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #2563EB;
  animation: acDotBounce 1.2s ease-in-out infinite;
  flex-shrink: 0;
}
.ac-loader__dot:nth-child(1) { animation-delay: 0s; }
.ac-loader__dot:nth-child(2) { animation-delay: 0.18s; }
.ac-loader__dot:nth-child(3) { animation-delay: 0.36s; }

@keyframes acDotBounce {
  0%, 80%, 100% { transform: translateY(0);   opacity: 0.35; }
  40%           { transform: translateY(-4px); opacity: 1;   }
}

.ac-loader__label {
  font-size: 10.5px;
  font-weight: 600;
  color: #2563EB;
  letter-spacing: 0.02em;
  margin-left: 3px;
  opacity: 0.8;
}

  `;
  document.head.appendChild(s);
})();