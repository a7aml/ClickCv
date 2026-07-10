/* ==========================================================
   compare.render.js  — v2
   3-column result layout:
     Left  — CV A rendered as document with highlights
     Center — score rings + criteria + verdict + SW
     Right  — CV B rendered as document with highlights
========================================================== */
window.CMPRender = (function () {
  'use strict';

  const CRITERIA = [
    { key: 'keyword_score',            label: 'Keyword Matching',  weight: '30%' },
    { key: 'keyword_placement_score',  label: 'Keyword Placement', weight: '15%' },
    { key: 'formatting_score',         label: 'Formatting',        weight: '12%' },
    { key: 'structure_score',          label: 'Sections',          weight: '12%' },
    { key: 'experience_recency_score', label: 'Recency',           weight: '8%'  },
    { key: 'achievements_score',       label: 'Achievements',      weight: '8%'  },
    { key: 'job_title_score',          label: 'Job Title',         weight: '7%'  },
    { key: 'education_score',          label: 'Education',         weight: '5%'  },
    { key: 'resume_length_score',      label: 'Length',            weight: '2%'  },
    { key: 'contact_info_score',       label: 'Contact',           weight: '1%'  },
  ];

  const CIRC = 263.9;

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

  const WEAK_PHRASES = [
    'responsible for','worked on','helped with','involved in',
    'assisted with','participated in','duties included','tasks included',
    'was responsible','helped to',
  ];

  /* ── Utility ── */
  function band(s) {
    if (s >= 75) return 'strong';
    if (s >= 65) return 'good';
    if (s >= 50) return 'borderline';
    return 'weak';
  }
  function bandLabel(b) {
    return { strong:'Strong Match', good:'Good Match',
             borderline:'Needs Work', weak:'Weak Match' }[b] || b;
  }
  function ringCol(b) {
    return { strong:'#059669', good:'#2563EB',
             borderline:'#D97706', weak:'#DC2626' }[b] || '#DC2626';
  }
  function barCol(v) {
    if (v >= 75) return '#059669';
    if (v >= 50) return '#2563EB';
    if (v >= 30) return '#D97706';
    return '#DC2626';
  }
  function ringOffset(score) {
    return (CIRC - (score / 100) * CIRC).toFixed(2);
  }
  function esc(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;')
              .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  /* ══════════════════════════════════════════════════
     CV DOCUMENT RENDERER
     Same logic as dashboard.cv-preview.js
  ══════════════════════════════════════════════════ */
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

  function _highlightLine(text, missingSet, foundSet) {
    if (!text) return esc(text);
    const lower  = text.toLowerCase();
    const ranges = [];

    function addHits(kw, type, label) {
      const escaped = kw.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const pattern = escaped.replace(/\s+/g, '\\s+');
      const re = new RegExp('(?<![a-z0-9])' + pattern + '(?![a-z0-9])', 'gi');
      let m;
      while ((m = re.exec(lower)) !== null) {
        const s = m.index, e = m.index + m[0].length;
        if (!ranges.some(r => s < r.end && e > r.start))
          ranges.push({ start: s, end: e, type, label });
      }
    }

    for (const kw of missingSet) addHits(kw, 'missing', `Missing: "${kw}"`);
    for (const kw of foundSet)   addHits(kw, 'found',   'Present ✓');
    for (const phrase of WEAK_PHRASES) {
      const idx = lower.indexOf(phrase);
      if (idx !== -1) {
        const e = idx + phrase.length;
        if (!ranges.some(r => idx < r.end && e > r.start))
          ranges.push({ start: idx, end: e, type: 'weak', label: 'Weak phrase' });
      }
    }

    ranges.sort((a, b) => a.start - b.start);
    const clean = [];
    for (const r of ranges) {
      if (!clean.length || r.start >= clean[clean.length-1].end) clean.push(r);
    }

    let html = '', cursor = 0;
    for (const r of clean) {
      if (r.start > cursor) html += esc(text.slice(cursor, r.start));
      html += `<mark class="cmp-mark cmp-mark--${r.type}" title="${esc(r.label)}">${esc(text.slice(r.start, r.end))}</mark>`;
      cursor = r.end;
    }
    if (cursor < text.length) html += esc(text.slice(cursor));
    return html;
  }

  function buildCvHtml(rawText, missingKeywords, foundKeywords) {
    if (!rawText) return '<p class="cmp-cv-empty">No text available.</p>';

    const missingSet    = new Set((missingKeywords || []).map(k => k.toLowerCase().trim()));
    const foundSet      = new Set((foundKeywords   || []).map(k => k.toLowerCase().trim()));
    const headerLineNums = _findHeaderLines(rawText);
    const lines          = rawText.split('\n');
    const parts          = [];

    const firstHeaderIdx = headerLineNums.size > 0
      ? Math.min(...headerLineNums) : lines.length;

    let nameEmitted      = false;
    let contactBlockDone = false;
    let addedDivider     = false;

    for (let i = 0; i < lines.length; i++) {
      const trimmed = lines[i].trim();
      if (!trimmed) { parts.push('<div class="cmp-cv-spacer"></div>'); continue; }

      // Section header
      if (headerLineNums.has(i)) {
        if (!addedDivider) {
          parts.push('<hr class="cmp-cv-divider">');
          addedDivider = true; contactBlockDone = true;
        }
        parts.push(`<div class="cmp-cv-section-header">
          <span class="cmp-cv-section-text">${esc(trimmed)}</span>
          <span class="cmp-cv-section-badge">✓</span>
        </div>`);
        continue;
      }

      // Contact block
      if (!contactBlockDone && i < firstHeaderIdx) {
        if (!nameEmitted && trimmed.length < 70 && !/^[\d@+]/.test(trimmed)) {
          nameEmitted = true;
          parts.push(`<div class="cmp-cv-name">${esc(trimmed)}</div>`);
          continue;
        }
        parts.push(`<div class="cmp-cv-contact">${_highlightLine(trimmed, missingSet, foundSet)}</div>`);
        continue;
      }

      // Bullet
      if (/^[•\-\*►▸▪◆·–—]/.test(trimmed)) {
        const text = trimmed.replace(/^[•\-\*►▸▪◆·–—]\s*/, '');
        parts.push(`<div class="cmp-cv-bullet"><span class="cmp-cv-bullet-dot">•</span><span>${_highlightLine(text, missingSet, foundSet)}</span></div>`);
        continue;
      }

      // Date line
      if (/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4}|present|current)\b/i.test(trimmed) && trimmed.length < 80) {
        parts.push(`<div class="cmp-cv-date">${_highlightLine(trimmed, missingSet, foundSet)}</div>`);
        continue;
      }

      // Job title
      const prevIsHeader = headerLineNums.has(i-1) || headerLineNums.has(i-2);
      if (trimmed.length < 100 && (prevIsHeader || /—|–|\|/.test(trimmed) ||
          /\b(engineer|developer|analyst|manager|officer|intern|director|lead|specialist)\b/i.test(trimmed))) {
        parts.push(`<div class="cmp-cv-jobtitle">${_highlightLine(trimmed, missingSet, foundSet)}</div>`);
        continue;
      }

      parts.push(`<div class="cmp-cv-line">${_highlightLine(trimmed, missingSet, foundSet)}</div>`);
    }

    return parts.join('');
  }

  /* ══════════════════════════════════════════════════
     MAIN RENDER FUNCTION
  ══════════════════════════════════════════════════ */
  function render(data, fileA, fileB, DOM) {
    const scoreA = Math.round(data.score_a || 0);
    const scoreB = Math.round(data.score_b || 0);
    const bandA  = band(scoreA);
    const bandB  = band(scoreB);
    const winner = data.winner || (scoreA >= scoreB ? 'a' : 'b');
    const colA   = ringCol(bandA);
    const colB   = ringCol(bandB);

    const fnameA = data.filename_a || fileA?.name || 'CV A';
    const fnameB = data.filename_b || fileB?.name || 'CV B';

    // ── Winner banner ────────────────────────────────
    DOM.winnerLabel.textContent = winner === 'a' ? 'CV A' : 'CV B';
    DOM.winnerLabel.className   = `cmp-winner-label cmp-cv-label cmp-cv-label--${winner}`;
    DOM.winnerTitle.textContent = `${winner === 'a' ? 'CV A' : 'CV B'} is the stronger match`;
    DOM.winnerSub.textContent   = data.summary || 'Based on 10-criteria ATS algorithm.';

    // ── Build 3-column results layout ───────────────
    const scoresA  = data.scores_a  || {};
    const scoresB  = data.scores_b  || {};
    const rawA     = data.raw_text_a || '';
    const rawB     = data.raw_text_b || '';
    const missingA = data.jd_missing_a || data.missing_keywords_a || [];
    const missingB = data.jd_missing_b || data.missing_keywords_b || [];
    const foundA   = data.jd_matched_a  || [];
    const foundB   = data.jd_matched_b  || [];

    // Build criteria bars HTML
    const criteriaHTML = CRITERIA.map(c => {
      const vA = Math.round(scoresA[c.key] || 0);
      const vB = Math.round(scoresB[c.key] || 0);
      const cA = barCol(vA), cB = barCol(vB);
      const winner_crit = vA >= vB ? 'a' : 'b';
      return `
        <div class="cmp3-crit-row">
          <span class="cmp3-crit-val" style="color:${cA}">${vA}</span>
          <div class="cmp3-crit-center">
            <div class="cmp3-crit-label">${c.label} <span class="cmp3-crit-weight">${c.weight}</span></div>
            <div class="cmp3-bars">
              <div class="cmp3-bar-wrap cmp3-bar-wrap--a">
                <div class="cmp3-bar-fill" style="width:${vA}%;background:${cA}"></div>
              </div>
              <div class="cmp3-bar-wrap cmp3-bar-wrap--b">
                <div class="cmp3-bar-fill" style="width:${vB}%;background:${cB}"></div>
              </div>
            </div>
          </div>
          <span class="cmp3-crit-val" style="color:${cB}">${vB}</span>
        </div>`;
    }).join('');

    // Build SW items
    const swItem = (text, type) => {
      const icon = type === 'strength'
        ? `<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`
        : `<svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
      return `<div class="cmp3-sw-item cmp3-sw-item--${type}"><span class="cmp3-sw-dot">${icon}</span><span>${esc(text)}</span></div>`;
    };

    const verdictHTML = (data.verdict || '')
      .split('\n\n').filter(p => p.trim())
      .map(p => `<p class="cmp3-verdict-para">${esc(p.trim())}</p>`).join('');

    // Convert long verdict into concise bullet points for the center column.
    // Split on sentences, take the most informative ones, cap at 5 bullets.
    const verdictBulletsHTML = (() => {
      const raw = (data.verdict || '').trim();
      if (!raw) return '<p class="cmp3-verdict-empty">No verdict available.</p>';

      // Split into sentences on period/exclamation, filter noise
      const sentences = raw
        .replace(/\n+/g, ' ')
        .split(/(?<=[.!])\s+/)
        .map(s => s.trim())
        .filter(s => s.length > 30 && s.length < 220);

      // Pick up to 5 most informative sentences
      // Priority: sentences mentioning CV A/B, scores, specific keywords
      const priority = sentences.filter(s =>
        /cv [ab]|score|keyword|match|missing|experience|skill/i.test(s)
      ).slice(0, 5);

      const bullets = priority.length >= 2 ? priority : sentences.slice(0, 5);

      return '<ul class="cmp3-verdict-bullets">' +
        bullets.map(b => `<li class="cmp3-verdict-bullet">${esc(b)}</li>`).join('') +
        '</ul>';
    })();

    // Inject new 3-column layout into results phase
    const resultsPhase = document.getElementById('cmp-results-phase');
    resultsPhase.innerHTML = `

      <!-- Winner banner -->
      <div class="cmp-winner-banner" id="cmp-winner-banner">
        <div class="cmp-winner-banner__left">
          <div class="cmp-winner-label cmp-cv-label cmp-cv-label--${winner}" id="cmp-winner-label">${winner === 'a' ? 'CV A' : 'CV B'}</div>
          <div>
            <h2 class="cmp-winner-title" id="cmp-winner-title">${esc(winner === 'a' ? 'CV A' : 'CV B')} is the stronger match</h2>
            <p class="cmp-winner-sub" id="cmp-winner-sub">${esc(data.summary || '')}</p>
          </div>
        </div>
        <button class="btn btn--ghost" id="cmp-new-comparison" type="button">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
          New Comparison
        </button>
      </div>

      <!-- 3-column body -->
      <div class="cmp3-body">

        <!-- LEFT: CV A document -->
        <div class="cmp3-col cmp3-col--left">
          <div class="cmp3-col-header">
            <div class="cmp-cv-label cmp-cv-label--a">CV A</div>
            <span class="cmp3-col-fname">${esc(fnameA)}</span>
            <div class="cmp3-score-pill" style="background:${colA}15;color:${colA};border-color:${colA}40">
              ${scoreA}/100 · ${bandLabel(bandA)}
            </div>
          </div>
          <div class="cmp3-legend">
            <span class="cmp3-leg-item"><span class="cmp3-leg-swatch cmp3-leg-swatch--found"></span>Present</span>
            <span class="cmp3-leg-item"><span class="cmp3-leg-swatch cmp3-leg-swatch--missing"></span>Missing</span>
            <span class="cmp3-leg-item"><span class="cmp3-leg-swatch cmp3-leg-swatch--weak"></span>Weak</span>
          </div>
          <div class="cmp3-cv-scroll">
            <div class="cmp3-cv-paper">
              ${buildCvHtml(rawA, missingA, foundA)}
            </div>
          </div>
        </div>

        <!-- CENTER: Analysis -->
        <div class="cmp3-col cmp3-col--center">
          <div class="cmp3-center-scroll">

            <!-- Score rings -->
            <div class="cmp3-rings">
              <div class="cmp3-ring-wrap">
                <svg viewBox="0 0 100 100" width="90" height="90">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(37,99,235,.08)" stroke-width="7"/>
                  <circle class="cmp3-arc" cx="50" cy="50" r="42" fill="none"
                    stroke="${colA}" stroke-width="7" stroke-linecap="round"
                    stroke-dasharray="263.9" stroke-dashoffset="${ringOffset(scoreA)}"
                    style="transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1.4s cubic-bezier(.4,0,.2,1)"/>
                </svg>
                <div class="cmp3-ring-inner">
                  <span class="cmp3-ring-num" style="color:${colA}">${scoreA}</span>
                  <span class="cmp3-ring-sub">/100</span>
                </div>
              </div>
              <div class="cmp3-vs-badge">VS</div>
              <div class="cmp3-ring-wrap">
                <svg viewBox="0 0 100 100" width="90" height="90">
                  <circle cx="50" cy="50" r="42" fill="none" stroke="rgba(37,99,235,.08)" stroke-width="7"/>
                  <circle class="cmp3-arc" cx="50" cy="50" r="42" fill="none"
                    stroke="${colB}" stroke-width="7" stroke-linecap="round"
                    stroke-dasharray="263.9" stroke-dashoffset="${ringOffset(scoreB)}"
                    style="transform:rotate(-90deg);transform-origin:center;transition:stroke-dashoffset 1.4s cubic-bezier(.4,0,.2,1)"/>
                </svg>
                <div class="cmp3-ring-inner">
                  <span class="cmp3-ring-num" style="color:${colB}">${scoreB}</span>
                  <span class="cmp3-ring-sub">/100</span>
                </div>
              </div>
            </div>

            <!-- Criteria bars -->
            <div class="cmp3-criteria">
              <div class="cmp3-criteria-title">
                <span class="cmp3-criteria-cv" style="color:${colA}">CV A</span>
                <span>10-Criteria Breakdown</span>
                <span class="cmp3-criteria-cv" style="color:${colB}">CV B</span>
              </div>
              ${criteriaHTML}
            </div>

            <!-- Verdict -->
            <div class="cmp3-verdict">
              <div class="cmp3-verdict-header">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#7C3AED" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                AI Verdict
                <span class="cmp3-verdict-badge">Algorithm-backed</span>
              </div>
              <div class="cmp3-verdict-body">${verdictBulletsHTML}</div>
            </div>

            <!-- Strengths & Weaknesses -->
            <div class="cmp3-sw">
              <div class="cmp3-sw-col">
                <div class="cmp3-sw-header">
                  <div class="cmp-cv-label cmp-cv-label--a cmp-cv-label--sm">CV A</div>
                  <span>${esc(fnameA)}</span>
                </div>
                <div class="cmp3-sw-list">
                  ${(data.strengths_a  || []).map(s => swItem(s,'strength')).join('')}
                  ${(data.weaknesses_a || []).map(w => swItem(w,'weakness')).join('')}
                </div>
              </div>
              <div class="cmp3-sw-col">
                <div class="cmp3-sw-header">
                  <div class="cmp-cv-label cmp-cv-label--b cmp-cv-label--sm">CV B</div>
                  <span>${esc(fnameB)}</span>
                </div>
                <div class="cmp3-sw-list">
                  ${(data.strengths_b  || []).map(s => swItem(s,'strength')).join('')}
                  ${(data.weaknesses_b || []).map(w => swItem(w,'weakness')).join('')}
                </div>
              </div>
            </div>

          </div>
        </div>

        <!-- RIGHT: CV B document -->
        <div class="cmp3-col cmp3-col--right">
          <div class="cmp3-col-header">
            <div class="cmp-cv-label cmp-cv-label--b">CV B</div>
            <span class="cmp3-col-fname">${esc(fnameB)}</span>
            <div class="cmp3-score-pill" style="background:${colB}15;color:${colB};border-color:${colB}40">
              ${scoreB}/100 · ${bandLabel(bandB)}
            </div>
          </div>
          <div class="cmp3-legend">
            <span class="cmp3-leg-item"><span class="cmp3-leg-swatch cmp3-leg-swatch--found"></span>Present</span>
            <span class="cmp3-leg-item"><span class="cmp3-leg-swatch cmp3-leg-swatch--missing"></span>Missing</span>
            <span class="cmp3-leg-item"><span class="cmp3-leg-swatch cmp3-leg-swatch--weak"></span>Weak</span>
          </div>
          <div class="cmp3-cv-scroll">
            <div class="cmp3-cv-paper">
              ${buildCvHtml(rawB, missingB, foundB)}
            </div>
          </div>
        </div>

      </div>`;

    // Wire new comparison button
    document.getElementById('cmp-new-comparison')?.addEventListener('click', () => {
      if (typeof window._cmpReset === 'function') window._cmpReset();
    });
  }

  return { render };
})();