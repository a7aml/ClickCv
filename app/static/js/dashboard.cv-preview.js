/* ==========================================================
   dashboard.cv-preview.js  — v4
   CV document preview matching rebuild.css style.
   
   Fixes:
   - Stats use actual backend counts (not text-scan counts)
   - missingSections shown as red "not found" banners
   - Keyword highlighting uses whole-word case-insensitive match
========================================================== */
(function () {
  'use strict';

  const WEAK_PHRASES = [
    'responsible for','worked on','helped with','involved in',
    'assisted with','participated in','duties included',
    'tasks included','was responsible','helped to',
  ];

  const HEADER_WORDS = new Set([
    'summary','professional summary','career summary','profile','objective',
    'about me','about','overview','personal statement',
    'experience','work experience','professional experience','employment history',
    'employment','work history','career history','internship','internships',
    'industrial training','professional background','internship experience',
    'education','educational background','academic background','qualifications',
    'skills','technical skills','core skills','key skills','competencies',
    'expertise','technologies','tools','programming languages','technical expertise',
    'projects','personal projects','academic projects','portfolio',
    'certifications','certification','certificates','courses',
    'achievements','accomplishments','awards','honors','honours',
    'languages','language skills','interests','hobbies','activities',
    'references','referees','contact','contact information',
    'contact details','personal information','core competencies',
  ]);

  /* ══════════════════════════════════════════════════
     MODAL
  ══════════════════════════════════════════════════ */
  function _ensureModal() {
    if (document.getElementById('cv-preview-modal')) return;
    const modal = document.createElement('div');
    modal.id        = 'cv-preview-modal';
    modal.className = 'cvp-backdrop';
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.style.display = 'none';

    modal.innerHTML = `
      <div class="cvp-modal">
        <div class="cvp-header">
          <div class="cvp-header__left">
            <span class="cvp-header__icon">📄</span>
            <div>
              <h2 class="cvp-header__title">CV Preview</h2>
              <p class="cvp-header__sub">Rendered as your actual CV — highlights show ATS analysis</p>
            </div>
          </div>
          <button class="cvp-close" id="cvp-close-btn" aria-label="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="cvp-legend">
          <span class="cvp-legend__item"><span class="cvp-swatch cvp-swatch--section"></span>Section detected</span>
          <span class="cvp-legend__item"><span class="cvp-swatch cvp-swatch--missing-sec"></span>Section missing</span>
          <span class="cvp-legend__item"><span class="cvp-swatch cvp-swatch--found"></span>Keyword present ✓</span>
          <span class="cvp-legend__item"><span class="cvp-swatch cvp-swatch--missing"></span>Missing keyword ✗</span>
          <span class="cvp-legend__item"><span class="cvp-swatch cvp-swatch--weak"></span>Weak phrase</span>
        </div>
        <div class="cvp-stats" id="cvp-stats"></div>
        <div class="cvp-body">
          <div class="cvp-paper" id="cvp-content"></div>
        </div>
        <div class="cvp-footer">
          <button class="btn btn--ghost btn--sm" id="cvp-close-footer-btn">Close</button>
          <button class="btn btn--primary btn--sm" id="cvp-rebuild-btn">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <polyline points="23 4 23 10 17 10"/>
              <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            Rebuild CV
          </button>
        </div>
      </div>`;

    document.body.appendChild(modal);
    document.getElementById('cvp-close-btn').addEventListener('click', closePreview);
    document.getElementById('cvp-close-footer-btn').addEventListener('click', closePreview);
    modal.addEventListener('click', e => { if (e.target === modal) closePreview(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && modal.style.display !== 'none') closePreview();
    });
    document.getElementById('cvp-rebuild-btn').addEventListener('click', () => {
      const d = window.__cvPreviewData;
      if (d && d.analysisId) window.location.href = `/rebuild?analysis_id=${d.analysisId}`;
    });
  }

  /* ══════════════════════════════════════════════════
     PUBLIC
  ══════════════════════════════════════════════════ */
  window.openCvPreview = function () {
    const data = window.__cvPreviewData;
    if (!data) { console.warn('CV Preview: no __cvPreviewData set'); return; }

    _ensureModal();

    const modal   = document.getElementById('cv-preview-modal');
    const content = document.getElementById('cvp-content');
    const stats   = document.getElementById('cvp-stats');

    const missingKeywords = data.missingKeywords  || [];
    const foundKeywords   = data.foundKeywords    || [];
    // missingSections = ALL absent sections (required + optional) — matches sidebar ✗ count
    const missingSections = data.missingSections  || [];
    // requiredMissing = only required sections that affect ATS score
    const requiredMissing = data.requiredMissing  || [];

    const { html, weakCount, detectedSections } = _buildCvDocument(
      data.rawText   || '',
      data.sections  || {},
      missingKeywords,
      foundKeywords,
      missingSections,
      requiredMissing,
    );

    content.innerHTML = html;

    // Stats match the results screen exactly:
    // - "Missing sections" = all absent (required + optional) = what sidebar ✗ shows
    // - "Missing keywords" = exact backend count
    stats.innerHTML = `
      <div class="cvp-stat">
        <span class="cvp-stat__num" style="color:#059669">${detectedSections}</span>
        <span class="cvp-stat__label">Sections detected</span>
      </div>
      <div class="cvp-stat__div"></div>
      <div class="cvp-stat">
        <span class="cvp-stat__num" style="color:${missingSections.length > 0 ? '#DC2626' : '#059669'}">${missingSections.length}</span>
        <span class="cvp-stat__label">Sections absent</span>
      </div>
      <div class="cvp-stat__div"></div>
      <div class="cvp-stat">
        <span class="cvp-stat__num" style="color:#2563EB">${foundKeywords.length}</span>
        <span class="cvp-stat__label">Keywords present</span>
      </div>
      <div class="cvp-stat__div"></div>
      <div class="cvp-stat">
        <span class="cvp-stat__num" style="color:${missingKeywords.length > 0 ? '#DC2626' : '#059669'}">${missingKeywords.length}</span>
        <span class="cvp-stat__label">Missing keywords</span>
      </div>
      <div class="cvp-stat__div"></div>
      <div class="cvp-stat">
        <span class="cvp-stat__num" style="color:#D97706">${weakCount}</span>
        <span class="cvp-stat__label">Weak phrases</span>
      </div>`;

    modal.style.display = 'flex';
    requestAnimationFrame(() => modal.classList.add('cvp-backdrop--visible'));

    content.addEventListener('mouseover', _handleTooltip);
    content.addEventListener('mouseout',  _clearTooltip);
  };

  function closePreview() {
    const modal = document.getElementById('cv-preview-modal');
    if (!modal) return;
    modal.classList.remove('cvp-backdrop--visible');
    setTimeout(() => { modal.style.display = 'none'; }, 280);
  }

  /* ══════════════════════════════════════════════════
     BUILD CV DOCUMENT
  ══════════════════════════════════════════════════ */
  function _buildCvDocument(rawText, sections, missingKeywords, foundKeywords, missingSections, requiredMissing) {
    if (!rawText) return {
      html: '<p class="cvp-empty">No CV text available.</p>',
      weakCount: 0, detectedSections: 0,
    };

    const missingSet    = new Set(missingKeywords.map(k => k.toLowerCase().trim()));
    const foundSet      = new Set(foundKeywords.map(k => k.toLowerCase().trim()));
    // All absent sections (required + optional)
    const missSecSet    = new Set((missingSections || []).map(s => s.toLowerCase().trim()));
    // Required missing sections (affect ATS score)
    const reqMissSet    = new Set((requiredMissing || []).map(s => s.toLowerCase().trim()));

    const headerLineNums = _findHeaderLines(rawText);
    const lines          = rawText.split('\n');

    let weakCount        = 0;
    let detectedSections = 0;
    const parts          = [];

    const firstHeaderIdx = headerLineNums.size > 0
      ? Math.min(...headerLineNums)
      : lines.length;

    let contactBlockDone = false;
    let addedDivider     = false;
    let nameEmitted      = false;

    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();

      if (!trimmed) {
        parts.push('<div class="cvp-spacer"></div>');
        continue;
      }

      // ── Section header ──────────────────────────────
      if (headerLineNums.has(i)) {
        if (!addedDivider) {
          parts.push('<hr class="cvp-contact-divider">');
          addedDivider     = true;
          contactBlockDone = true;
        }
        detectedSections++;
        parts.push(`
          <div class="cvp-section-header">
            <span class="cvp-section-header__text">${_esc(trimmed)}</span>
            <span class="cvp-section-header__badge cvp-section-header__badge--found">✓ Detected</span>
          </div>`);
        continue;
      }

      // ── Contact block ────────────────────────────────
      if (!contactBlockDone && i < firstHeaderIdx) {
        if (!nameEmitted && trimmed.length < 70 && !/^[\d@+]/.test(trimmed)) {
          nameEmitted = true;
          parts.push(`<div class="cvp-name">${_esc(trimmed)}</div>`);
          continue;
        }
        const { html: h, weak } = _highlightLine(trimmed, missingSet, foundSet);
        weakCount += weak;
        parts.push(`<div class="cvp-contact">${h}</div>`);
        continue;
      }

      // ── Bullet ──────────────────────────────────────
      if (/^[•\-\*►▸▪◆·–—]/.test(trimmed)) {
        const text = trimmed.replace(/^[•\-\*►▸▪◆·–—]\s*/, '');
        const { html: h, weak } = _highlightLine(text, missingSet, foundSet);
        weakCount += weak;
        parts.push(`
          <div class="cvp-bullet">
            <span class="cvp-bullet__dot">•</span>
            <span class="cvp-bullet__text">${h}</span>
          </div>`);
        continue;
      }

      // ── Date / location ──────────────────────────────
      const isDate = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4}|present|current)\b/i.test(trimmed)
        && trimmed.length < 80;
      if (isDate) {
        const { html: h, weak } = _highlightLine(trimmed, missingSet, foundSet);
        weakCount += weak;
        parts.push(`<div class="cvp-date">${h}</div>`);
        continue;
      }

      // ── Job title ────────────────────────────────────
      const prevIsHeader = headerLineNums.has(i - 1) || headerLineNums.has(i - 2);
      const looksLikeTitle = trimmed.length < 100 && !isDate && (
        prevIsHeader ||
        /—|–|\|/.test(trimmed) ||
        /\b(engineer|developer|analyst|manager|officer|intern|director|lead|head|specialist|consultant|associate|executive)\b/i.test(trimmed)
      );
      if (looksLikeTitle) {
        const { html: h, weak } = _highlightLine(trimmed, missingSet, foundSet);
        weakCount += weak;
        parts.push(`<div class="cvp-jobtitle">${h}</div>`);
        continue;
      }

      // ── Default ─────────────────────────────────────
      const { html: h, weak } = _highlightLine(trimmed, missingSet, foundSet);
      weakCount += weak;
      parts.push(`<div class="cvp-line">${h}</div>`);
    }

    // ── Append absent sections at the bottom ──────────
    // Shows ALL absent sections (required in red, optional in orange)
    // matching exactly what the sidebar ✗ list shows
    if (missSecSet.size > 0) {
      const hasRequired = [...missSecSet].some(s => reqMissSet.has(s));
      const hasOptional = [...missSecSet].some(s => !reqMissSet.has(s));

      parts.push(`
        <div class="cvp-missing-sections-block">
          <div class="cvp-missing-sections-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
              <line x1="12" y1="16" x2="12.01" y2="16"/>
            </svg>
            Sections Not Detected in Your CV
          </div>`);

      for (const sec of missSecSet) {
        const label      = sec.charAt(0).toUpperCase() + sec.slice(1);
        const isRequired = reqMissSet.has(sec);
        const borderCol  = isRequired ? '#DC2626' : '#D97706';
        const bgCol      = isRequired ? 'rgba(220,38,38,0.03)' : 'rgba(217,119,6,0.03)';
        const badgeClass = isRequired ? 'cvp-section-header__badge--missing' : 'cvp-section-header__badge--optional';
        const badgeText  = isRequired ? '✗ Required — missing' : '✗ Optional — missing';
        const hint       = isRequired
          ? 'Required section — absence hurts your ATS score.'
          : 'Optional section — adding it boosts your ATS score.';
        parts.push(`
          <div class="cvp-section-header" style="border-bottom-color:${borderCol};background:${bgCol}">
            <span class="cvp-section-header__text" style="color:${borderCol}">${_esc(label)}</span>
            <span class="cvp-section-header__badge ${badgeClass}">${badgeText}</span>
          </div>
          <div class="cvp-missing-hint" style="color:${borderCol}cc">${hint}</div>`);
      }

      parts.push(`</div>`);
    }

    return { html: parts.join(''), weakCount, detectedSections };
  }

  /* ── Find header line indices ── */
  function _findHeaderLines(rawText) {
    const set   = new Set();
    const lines = rawText.split('\n');
    for (let i = 0; i < lines.length; i++) {
      const t = lines[i].trim();
      if (!t || t.length > 70) continue;
      const norm = t.replace(/[:\-_•|]/g, '').trim().toLowerCase();
      if (HEADER_WORDS.has(norm)) set.add(i);
    }
    return set;
  }

  /* ── Highlight line — whole-word, case-insensitive ── */
  function _highlightLine(text, missingSet, foundSet) {
    const counts = { missing: 0, found: 0, weak: 0 };
    if (!text) return { html: _esc(text), ...counts };

    const lower  = text.toLowerCase();
    const ranges = [];

    function addHits(kw, type, label) {
      const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const pattern = escaped.replace(/\s+/g, '\\s+');
      const re = new RegExp('(?<![a-z0-9])' + pattern + '(?![a-z0-9])', 'gi');
      let m;
      while ((m = re.exec(lower)) !== null) {
        const s = m.index, e = m.index + m[0].length;
        if (!_overlaps(ranges, s, e)) ranges.push({ start: s, end: e, type, label });
      }
    }

    // Priority: missing > found > weak
    for (const kw of missingSet) addHits(kw, 'missing', `Missing keyword: "${kw}" — add to your CV`);
    for (const kw of foundSet)   addHits(kw, 'found',   'Keyword present ✓');
    for (const phrase of WEAK_PHRASES) {
      const idx = lower.indexOf(phrase);
      if (idx !== -1) {
        const e = idx + phrase.length;
        if (!_overlaps(ranges, idx, e))
          ranges.push({ start: idx, end: e, type: 'weak', label: 'Weak phrase — use a strong action verb' });
      }
    }

    ranges.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start));
    const clean = _merge(ranges);

    let html = '', cursor = 0;
    for (const r of clean) {
      if (r.start > cursor) html += _esc(text.slice(cursor, r.start));
      html += `<mark class="cvp-mark cvp-mark--${r.type}" data-tooltip="${_esc(r.label)}">${_esc(text.slice(r.start, r.end))}</mark>`;
      counts[r.type]++;
      cursor = r.end;
    }
    if (cursor < text.length) html += _esc(text.slice(cursor));
    return { html, weak: counts.weak };
  }

  function _overlaps(r, s, e) { return r.some(x => s < x.end && e > x.start); }
  function _merge(r) {
    const res = [];
    for (const x of r) {
      if (!res.length || x.start >= res[res.length-1].end) res.push(x);
    }
    return res;
  }

  /* ── Tooltip ── */
  function _handleTooltip(e) {
    const mark = e.target.closest('.cvp-mark');
    if (!mark || !mark.dataset.tooltip) return;
    _clearTooltip();
    const tip = document.createElement('div');
    tip.className = 'cvp-tooltip'; tip.textContent = mark.dataset.tooltip; tip.id = '__cvp_tip';
    document.body.appendChild(tip);
    const rect = mark.getBoundingClientRect();
    tip.style.left = `${rect.left + window.scrollX}px`;
    tip.style.top  = `${rect.top  + window.scrollY - tip.offsetHeight - 8}px`;
  }
  function _clearTooltip() { const o = document.getElementById('__cvp_tip'); if (o) o.remove(); }

  function _esc(s) {
    if (!s) return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

})();