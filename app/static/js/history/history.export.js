/* ==========================================================
   history.export.js
   Client-side PDF export using html2canvas + jsPDF.
   Depends on: history.state.js, history.api.js
   Exposes:    window.HSTExport
========================================================== */

window.HSTExport = (function () {
  'use strict';

  const {
    CRITERIA,
    getBand, getBandLabel, getBandEmoji,
    getMajorEmoji, barColor, ringColor,
    ringOffset, fmtDate, showToast,
  } = window.HST;

  const { fetchDetail } = window.HSTAPI;

  /* ════════════════════════════
     EXPORT ENTRY POINT
  ════════════════════════════ */
  async function exportPdf(id, filename) {
    const data = await fetchDetail(id).catch(() => null);
    if (!data) { showToast('Could not load analysis for export.', 'error'); return; }

    showToast('Generating PDF…', 'info');

    const wrap = buildReportDOM(data);
    document.body.appendChild(wrap);

    try {
      const canvas  = await html2canvas(wrap, {
        scale: 2, useCORS: true,
        backgroundColor: '#F0F4FF',
        logging: false,
        windowWidth: 794,
      });

      const { jsPDF }  = window.jspdf;
      const imgData    = canvas.toDataURL('image/jpeg', 0.95);
      const imgW       = 210;
      const imgH       = (canvas.height / canvas.width) * imgW;
      const pdf        = new jsPDF({ orientation:'portrait', unit:'mm', format:'a4' });

      if (imgH <= 297) {
        pdf.addImage(imgData, 'JPEG', 0, 0, imgW, imgH, '', 'FAST');
      } else {
        let yOff = 0;
        while (yOff < imgH) {
          if (yOff > 0) pdf.addPage();
          pdf.addImage(imgData, 'JPEG', 0, -yOff, imgW, imgH, '', 'FAST');
          yOff += 297;
        }
      }

      const safeName = (filename || `Analysis_${id}`)
        .replace(/[^a-zA-Z0-9_-]/g, '_')
        .replace(/\.pdf$/i, '');
      pdf.save(`ClickCV_Report_${safeName}.pdf`);
      showToast('PDF downloaded.', 'success');

    } catch (err) {
      console.error('exportPdf:', err);
      showToast('Export failed. Please try again.', 'error');
    } finally {
      document.body.removeChild(wrap);
    }
  }

  /* ════════════════════════════
     BUILD HIDDEN A4 DOM
  ════════════════════════════ */
  function buildReportDOM(data) {
    const band  = data.score_band || getBand(data.overall_score);
    const score = Math.round(data.overall_score || 0);
    const rc    = ringColor(band);
    const CIRC  = 251.2;   // r=40
    const off   = ringOffset(score, CIRC);

    const criteriaRows = CRITERIA.map(c => {
      const val = Math.round(data[c.key] || 0);
      const col = barColor(val);
      return `
        <div style="margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;
                      align-items:center;margin-bottom:4px">
            <span style="font-size:11px;font-weight:700;color:#0f1624">${c.label}</span>
            <div style="display:flex;align-items:center;gap:8px">
              <span style="font-size:10px;color:#888;font-weight:600">${c.weight}</span>
              <span style="font-size:12px;font-weight:800;color:${col}">${val}</span>
            </div>
          </div>
          <div style="height:7px;background:rgba(37,99,235,.08);
                      border-radius:999px;overflow:hidden">
            <div style="height:100%;width:${val}%;background:${col};
                        border-radius:999px"></div>
          </div>
        </div>`;
    }).join('');

    const missing     = (data.missing_keywords || []).slice(0, 20);
    const missingHTML = missing.map(k =>
      `<span style="display:inline-flex;padding:3px 10px;border-radius:999px;
                   font-size:10px;font-weight:600;
                   background:rgba(220,38,38,.07);color:#DC2626;
                   border:1px solid rgba(220,38,38,.18);margin:2px">${k}</span>`
    ).join('') || '<span style="font-size:11px;color:#888">None missing.</span>';

    const today = new Date().toLocaleDateString('en-MY', {
      day:'numeric', month:'long', year:'numeric'
    });

    const wrap = document.createElement('div');
    wrap.style.cssText = [
      'position:fixed', 'left:-9999px', 'top:0',
      'width:794px',    'background:#F0F4FF',
      "font-family:'Plus Jakarta Sans',Arial,sans-serif",
      'padding:0',      'margin:0', 'z-index:-1',
    ].join(';');

    wrap.innerHTML = `
      <!-- Header band -->
      <div style="background:linear-gradient(135deg,#2563EB,#06B6D4);
                  padding:28px 36px 24px">
        <div style="display:flex;align-items:center;justify-content:space-between">
          <div style="display:flex;align-items:center;gap:12px">
            <div style="width:38px;height:38px;background:rgba(255,255,255,.2);
                        border-radius:10px;display:flex;align-items:center;
                        justify-content:center;font-size:18px;font-weight:900;
                        color:#fff">C</div>
            <div>
              <span style="font-size:20px;font-weight:800;color:#fff;
                           letter-spacing:-.02em">ClickCV</span>
              <p style="font-size:11px;color:rgba(255,255,255,.7);
                        margin:2px 0 0">AI-Powered Resume Analysis Report</p>
            </div>
          </div>
          <div style="text-align:right">
            <p style="font-size:11px;color:rgba(255,255,255,.7);margin:0">Generated</p>
            <p style="font-size:12px;color:#fff;font-weight:700;margin:2px 0 0">${today}</p>
          </div>
        </div>
      </div>

      <!-- Body -->
      <div style="padding:24px 32px;background:#F0F4FF">

        <!-- Score hero card -->
        <div style="background:#fff;border-radius:16px;padding:22px 26px;
                    margin-bottom:16px;box-shadow:0 2px 12px rgba(37,99,235,.08);
                    border:1px solid rgba(37,99,235,.10);
                    display:flex;align-items:center;gap:24px">
          <div style="flex-shrink:0;width:100px;height:100px;position:relative">
            <svg width="100" height="100" viewBox="0 0 100 100"
                 style="transform:rotate(-90deg)">
              <circle cx="50" cy="50" r="40" fill="none"
                stroke="rgba(37,99,235,.08)" stroke-width="8"/>
              <circle cx="50" cy="50" r="40" fill="none"
                stroke="${rc}" stroke-width="8" stroke-linecap="round"
                stroke-dasharray="${CIRC}" stroke-dashoffset="${off}"/>
            </svg>
            <div style="position:absolute;inset:0;display:flex;flex-direction:column;
                        align-items:center;justify-content:center">
              <span style="font-size:28px;font-weight:800;color:${rc};
                           letter-spacing:-.05em;line-height:1">${score}</span>
              <span style="font-size:10px;color:#888;font-weight:600">/100</span>
            </div>
          </div>
          <div style="flex:1;min-width:0">
            <h2 style="font-size:15px;font-weight:800;color:#0f1624;
                        margin:0 0 5px;white-space:nowrap;overflow:hidden;
                        text-overflow:ellipsis">${data.filename}</h2>
            <div style="display:inline-flex;align-items:center;gap:5px;
                        padding:4px 12px;border-radius:999px;
                        background:${rc}18;border:1px solid ${rc}40;
                        margin-bottom:8px">
              <span style="font-size:12px;font-weight:700;color:${rc}">
                ${getBandEmoji(band)} ${getBandLabel(band)}
              </span>
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <span style="display:inline-flex;align-items:center;gap:4px;
                           padding:3px 10px;border-radius:999px;font-size:10px;
                           font-weight:600;background:rgba(37,99,235,.08);
                           color:#2563EB;border:1px solid rgba(37,99,235,.16)">
                ${getMajorEmoji(data.major)}
                ${data.major.charAt(0).toUpperCase() + data.major.slice(1)}
              </span>
              <span style="display:inline-flex;align-items:center;gap:4px;
                           padding:3px 10px;border-radius:999px;font-size:10px;
                           font-weight:600;background:rgba(37,99,235,.08);
                           color:#2563EB;border:1px solid rgba(37,99,235,.16)">
                📅 ${fmtDate(data.created_at)}
              </span>
            </div>
          </div>
        </div>

        <!-- Criteria breakdown -->
        <div style="background:#fff;border-radius:16px;padding:20px 24px;
                    margin-bottom:16px;box-shadow:0 2px 12px rgba(37,99,235,.08);
                    border:1px solid rgba(37,99,235,.10)">
          <p style="font-size:11px;font-weight:800;text-transform:uppercase;
                    letter-spacing:.08em;color:#888;margin:0 0 14px">
            10-Criteria ATS Breakdown
          </p>
          ${criteriaRows}
        </div>

        <!-- Missing keywords -->
        <div style="background:#fff;border-radius:16px;padding:18px 22px;
                    margin-bottom:16px;box-shadow:0 2px 12px rgba(37,99,235,.08);
                    border:1px solid rgba(37,99,235,.10)">
          <p style="font-size:11px;font-weight:800;text-transform:uppercase;
                    letter-spacing:.08em;color:#888;margin:0 0 10px">
            Missing Keywords
          </p>
          <div style="display:flex;flex-wrap:wrap;gap:4px">${missingHTML}</div>
        </div>

        <!-- Footer -->
        <p style="text-align:center;font-size:10px;color:#aaa;margin:8px 0 0">
          Generated by <strong style="color:#2563EB">ClickCV</strong>
          — AI-Powered Resume Analysis · ${today}
        </p>
      </div>`;

    return wrap;
  }

  /* ── Public ── */
  return { exportPdf };
})();