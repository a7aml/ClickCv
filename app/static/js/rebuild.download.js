/* ==========================================================
   rebuild.download.js — PDF + DOCX export for rebuilt CV
   Exposes: window.RBDDownload = { pdf, docx }
========================================================== */
window.RBDDownload = (function () {
  'use strict';

  function toast(msg, type) {
    const rack = document.getElementById('rbd-toasts');
    if (!rack) return;
    const t = document.createElement('div');
    t.className = `rbd-toast rbd-toast--${type}`;
    t.textContent = msg;
    rack.appendChild(t);
    setTimeout(() => t.classList.add('rbd-toast--show'), 10);
    setTimeout(() => { t.classList.remove('rbd-toast--show'); setTimeout(() => t.remove(), 400); }, 3500);
  }

  const SECTION_ORDER = ['contact','summary','experience','education',
    'skills','certifications','projects','achievements','languages','interests'];

  /* ── PDF DOWNLOAD ── */
  async function pdf(DATA, DOM) {
    if (!DATA) return;
    toast('Generating PDF…', 'info');

    const wrap = document.createElement('div');
    wrap.style.cssText = [
      'position:fixed', 'left:-9999px', 'top:0',
      'width:794px', 'background:#fff',
      "font-family:'Plus Jakarta Sans',Arial,sans-serif",
      'padding:48px 56px', 'color:#0f1624',
    ].join(';');
    wrap.innerHTML = DOM.cvDoc.innerHTML;
    document.body.appendChild(wrap);

    try {
      const canvas = await html2canvas(wrap, {
        scale: 2, useCORS: true, backgroundColor: '#fff',
        logging: false, windowWidth: 794,
      });
      const { jsPDF } = window.jspdf;
      const img       = canvas.toDataURL('image/jpeg', 0.95);
      const imgW      = 210;
      const imgH      = (canvas.height / canvas.width) * imgW;
      const pdf       = new jsPDF({ unit:'mm', format:'a4' });

      if (imgH <= 297) {
        pdf.addImage(img, 'JPEG', 0, 0, imgW, imgH, '', 'FAST');
      } else {
        let y = 0;
        while (y < imgH) {
          if (y > 0) pdf.addPage();
          pdf.addImage(img, 'JPEG', 0, -y, imgW, imgH, '', 'FAST');
          y += 297;
        }
      }
      pdf.save('ClickCV_Rebuilt_CV.pdf');
      toast('PDF downloaded.', 'success');
    } catch (e) {
      console.error(e);
      toast('PDF export failed.', 'error');
    } finally {
      document.body.removeChild(wrap);
    }
  }

  /* ── DOCX DOWNLOAD ── */
  async function downloadDocx(DATA) {
    if (!DATA) { toast('No data to export.', 'error'); return; }

    // docx.js UMD bundle may register itself under different globals
    // depending on version — check all known variants
    const docxLib = window.docx || window.DocxJS || window.DOCX;

    if (!docxLib || !docxLib.Document || !docxLib.Packer) {
      // Library loaded but global not found — log what IS available
      console.warn('docx global not found. Available globals with "doc":', 
        Object.keys(window).filter(k => k.toLowerCase().includes('doc'))
      );
      toast('DOCX library not ready. Please refresh the page.', 'error');
      return;
    }

    toast('Generating DOCX…', 'info');

    try {
      const { Document, Packer, Paragraph, TextRun,
              HeadingLevel, BorderStyle } = docxLib;

      const sections = DATA.sections || {};
      const SECTION_ORDER_DOCX = [
        'contact','summary','experience','education',
        'skills','certifications','projects','achievements','languages','interests',
      ];
      const ordered = [
        ...SECTION_ORDER_DOCX.filter(k => sections[k]),
        ...Object.keys(sections).filter(k => !SECTION_ORDER_DOCX.includes(k) && sections[k]),
      ];

      const children = [];

      for (const key of ordered) {
        const text  = sections[key] || '';
        const lines = text.split('\n').map(l => l.trim()).filter(Boolean);

        if (key === 'contact') {
          children.push(new Paragraph({
            text:    lines[0] || '',
            heading: HeadingLevel.TITLE,
            spacing: { after: 100 },
          }));
          if (lines.length > 1) {
            children.push(new Paragraph({
              children: [new TextRun({
                text:  lines.slice(1).join(' | '),
                size:  20,
                color: '2563EB',
              })],
              spacing: { after: 300 },
            }));
          }
          continue;
        }

        // Section heading with blue bottom border
        children.push(new Paragraph({
          text:    key.toUpperCase(),
          heading: HeadingLevel.HEADING_1,
          spacing: { before: 280, after: 80 },
          border:  {
            bottom: { style: BorderStyle.SINGLE, size: 6, color: '2563EB' },
          },
        }));

        // Section content lines
        for (const line of lines) {
          const isBullet = /^[-•*–]\s/.test(line);
          children.push(new Paragraph({
            children: [new TextRun({
              text: isBullet ? line.replace(/^[-•*–]\s*/, '') : line,
              size: 22,
            })],
            bullet:  isBullet ? { level: 0 } : undefined,
            spacing: { after: 60 },
          }));
        }
      }

      const doc  = new Document({ sections: [{ children }] });
      const blob = await Packer.toBlob(doc);
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = 'ClickCV_Rebuilt_CV.docx';
      a.click();
      URL.revokeObjectURL(url);
      toast('DOCX downloaded.', 'success');

    } catch (e) {
      console.error('DOCX export error:', e);
      toast('DOCX export failed. Please try again.', 'error');
    }
  }


  return { pdf, docx: downloadDocx };
})();