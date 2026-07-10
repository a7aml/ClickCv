/* ==========================================================
   rebuild.js — handles both:
   1. Upload mode  — user uploads CV directly (independent page)
   2. History mode — analysis_id passed via URL ?analysis_id=X
========================================================== */
(function () {
  'use strict';

  function getToken() {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  }
  if (!getToken()) { window.location.href = '/login'; return; }

  let DATA        = null;
  let ANALYSIS_ID = null;

  const $ = id => document.getElementById(id);
  const DOM = {
    uploadScreen: $('rbd-upload-screen'),
    loading:      $('rbd-loading'),
    error:        $('rbd-error'),
    errorText:    $('rbd-error-text'),
    result:       $('rbd-result'),
    step:         $('rbd-step'),
    bar:          $('rbd-bar'),
    subtitle:     $('rbd-subtitle'),
    arcOrig:      $('rbd-arc-orig'),
    arcRebuilt:   $('rbd-arc-rebuilt'),
    numOrig:      $('rbd-num-orig'),
    numRebuilt:   $('rbd-num-rebuilt'),
    bandOrig:     $('rbd-band-orig'),
    bandRebuilt:  $('rbd-band-rebuilt'),
    deltaNum:     $('rbd-delta-num'),
    delta:        $('rbd-delta'),
    criteria:     $('rbd-criteria'),
    gapsCard:     $('rbd-gaps-card'),
    gaps:         $('rbd-gaps'),
    cvDoc:        $('rbd-cv-doc'),
    toasts:       $('rbd-toasts'),
    dlPdf:        $('rbd-dl-pdf'),
    dlDocx:       $('rbd-dl-docx'),
    avatar:       $('rbd-avatar'),
    username:     $('rbd-username'),
    fileInput:    $('rbd-file-input'),
    dropzone:     $('rbd-dropzone'),
    fileName:     $('rbd-file-name'),
    submitBtn:    $('rbd-submit-btn'),
  };

  /* ── Helpers ── */
  const CIRC = 163.4;
  function band(s) { return s>=75?'strong':s>=65?'good':s>=50?'borderline':'weak'; }
  function bandLabel(b) { return {strong:'Strong Match',good:'Good Match',borderline:'Needs Work',weak:'Weak Match'}[b]||b; }
  function ringCol(b) { return {strong:'#059669',good:'#2563EB',borderline:'#D97706',weak:'#DC2626'}[b]||'#DC2626'; }
  function barCol(v) { return v>=75?'#059669':v>=50?'#2563EB':v>=30?'#D97706':'#DC2626'; }
  function offset(s) { return (CIRC-(s/100)*CIRC).toFixed(2); }

  function toast(msg, type='info') {
    const t = document.createElement('div');
    t.className = `rbd-toast rbd-toast--${type}`;
    t.textContent = msg;
    DOM.toasts.appendChild(t);
    setTimeout(()=>t.classList.add('rbd-toast--show'),10);
    setTimeout(()=>{t.classList.remove('rbd-toast--show');setTimeout(()=>t.remove(),400);},3500);
  }

  /* ── Screen management ── */
  function showUploadScreen() {
    DOM.uploadScreen.style.display = 'flex';
    DOM.loading.style.display      = 'none';
    DOM.error.style.display        = 'none';
    DOM.result.style.display       = 'none';
  }

  function showLoading() {
    DOM.uploadScreen.style.display = 'none';
    DOM.loading.style.display      = 'flex';
    DOM.error.style.display        = 'none';
    DOM.result.style.display       = 'none';
  }

  function showError(msg) {
    stopLoading();
    DOM.uploadScreen.style.display = 'none';
    DOM.loading.style.display      = 'none';
    DOM.error.style.display        = 'flex';
    DOM.result.style.display       = 'none';
    DOM.errorText.textContent      = msg || 'Something went wrong. Please try again.';
  }

  /* ── Loading animation ── */
  const STEPS = [
    {text:'Extracting CV content…',     pct:10},
    {text:'Analysing sections…',        pct:22},
    {text:'Identifying keyword gaps…',  pct:35},
    {text:'Sending to AI engine…',      pct:48},
    {text:'Rewriting with your data…',  pct:64},
    {text:'Re-scoring rebuilt CV…',     pct:80},
    {text:'Calculating improvement…',   pct:92},
    {text:'Finalising result…',         pct:97},
  ];
  let stepTimer = null;

  function startLoading() {
    showLoading();
    let i = 0;
    function next() {
      if (i >= STEPS.length) return;
      DOM.step.style.opacity = '0';
      setTimeout(()=>{
        DOM.step.textContent   = STEPS[i].text;
        DOM.step.style.opacity = '1';
        DOM.bar.style.width    = STEPS[i].pct + '%';
        i++;
        stepTimer = setTimeout(next, 3600);
      },250);
    }
    next();
  }

  function stopLoading() {
    clearTimeout(stepTimer);
    DOM.bar.style.width = '100%';
  }

  /* ── API ── */
  async function apiFetch(url, opts={}) {
    const res  = await fetch(url, {
      ...opts,
      headers: {
        'Authorization': `Bearer ${getToken()}`,
        ...(opts.headers||{}),
      },
    });
    // For multipart responses don't set Content-Type (browser sets boundary)
    let data;
    const ct = res.headers.get('content-type')||'';
    if (ct.includes('application/json')) {
      data = await res.json();
    } else {
      data = {error: `HTTP ${res.status}`};
    }
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  }

  /* ── Drop zone wiring ── */
  if (DOM.dropzone) {
    DOM.dropzone.addEventListener('dragover', e=>{e.preventDefault();DOM.dropzone.classList.add('drag-over');});
    DOM.dropzone.addEventListener('dragleave', ()=>DOM.dropzone.classList.remove('drag-over'));
    DOM.dropzone.addEventListener('drop', e=>{
      e.preventDefault();
      DOM.dropzone.classList.remove('drag-over');
      const file = e.dataTransfer?.files?.[0];
      if (file) setFile(file);
    });
    DOM.fileInput?.addEventListener('change', e=>{
      const file = e.target.files?.[0];
      if (file) setFile(file);
    });
  }

  function setFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf','docx'].includes(ext)) { toast('Only PDF or DOCX files are supported.','error'); return; }
    if (file.size > 5*1024*1024) { toast('File is too large. Max 5MB.','error'); return; }
    DOM.fileInput._selectedFile = file;
    if (DOM.fileName) {
      DOM.fileName.textContent = `📎 ${file.name}`;
      DOM.fileName.style.display = 'block';
    }
  }

  /* ── Upload rebuild flow ── */
  window.startUploadRebuild = async function() {
    const file  = DOM.fileInput?._selectedFile || DOM.fileInput?.files?.[0];
    const major = $('rbd-major')?.value;
    const jd    = $('rbd-jd')?.value?.trim() || '';

    if (!file)  { toast('Please select a CV file.','error'); return; }
    if (!major) { toast('Please select your industry.','error'); return; }

    if (DOM.submitBtn) { DOM.submitBtn.disabled = true; DOM.submitBtn.textContent = 'Uploading…'; }

    const fd = new FormData();
    fd.append('file', file);
    fd.append('major', major);
    if (jd) fd.append('job_description', jd);

    startLoading();

    try {
      const data = await apiFetch('/build/rebuild-upload', { method:'POST', body: fd });
      renderAll(data);
    } catch(err) {
      showError(err.message || 'Rebuild failed. Please try again.');
    } finally {
      if (DOM.submitBtn) { DOM.submitBtn.disabled = false; DOM.submitBtn.textContent = '✦ Rebuild My CV'; }
    }
  };

  /* ── History / analysis_id flow ── */
  async function bootFromAnalysis(id) {
    startLoading();
    try {
      const data = await apiFetch('/build/rebuild', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({analysis_id: id}),
      });
      renderAll(data);
    } catch(err) {
      showError(err.message || 'Rebuild failed. Please try again.');
    }
  }

  /* ── Render all ── */
  function renderAll(data) {
    DATA = data;
    stopLoading();
    DOM.loading.style.display      = 'none';
    DOM.uploadScreen.style.display = 'none';
    DOM.error.style.display        = 'none';
    DOM.result.style.display       = 'block';

    const delta = Math.round(data.score_delta||0);
    DOM.subtitle.textContent =
      `Score: ${Math.round(data.original_score)} → ${Math.round(data.rebuilt_score)} ` +
      `(${delta>=0?'+':''}${delta} pts) · Rebuilt using only your original content.`;

    renderBanner(data);
    renderCriteria(data);
    renderCvDoc(data.sections||{});
    renderGaps(data);
    if (data.already_exists) toast('Showing your previously rebuilt CV.','info');
  }

  /* ── Score banner ── */
  function renderBanner(data) {
    const oScore = Math.round(data.original_score||0);
    const rScore = Math.round(data.rebuilt_score||0);
    const delta  = Math.round(data.score_delta||0);
    const oBand  = band(oScore), rBand = band(rScore);
    const oCol   = ringCol(oBand), rCol = ringCol(rBand);

    DOM.numOrig.textContent    = oScore; DOM.numOrig.style.color    = oCol;
    DOM.bandOrig.textContent   = bandLabel(oBand); DOM.bandOrig.style.color = oCol;
    DOM.arcOrig.style.stroke   = oCol;
    DOM.numRebuilt.textContent = rScore; DOM.numRebuilt.style.color = rCol;
    DOM.bandRebuilt.textContent= bandLabel(rBand); DOM.bandRebuilt.style.color = rCol;
    DOM.arcRebuilt.style.stroke= rCol;
    DOM.deltaNum.textContent   = (delta>=0?'+':'')+delta;
    if (delta<0) DOM.delta.classList.add('rbd-delta--neg');

    requestAnimationFrame(()=>{
      setTimeout(()=>{
        DOM.arcOrig.style.strokeDashoffset    = offset(oScore);
        DOM.arcRebuilt.style.strokeDashoffset = offset(rScore);
      },80);
    });
  }

  /* ── Criteria ── */
  const CRITERIA_META = [
    {key:'keyword_score',label:'Keywords',weight:'35%'},
    {key:'keyword_placement_score',label:'Placement',weight:'18%'},
    {key:'formatting_score',label:'Formatting',weight:'17%'},
    {key:'structure_score',label:'Sections',weight:'12%'},
    {key:'experience_recency_score',label:'Recency',weight:'10%'},
    {key:'achievements_score',label:'Achieve.',weight:'10%'},
    {key:'job_title_score',label:'Job Title',weight:'8%'},
    {key:'education_score',label:'Education',weight:'7%'},
    {key:'resume_length_score',label:'Length',weight:'4%'},
    {key:'contact_info_score',label:'Contact',weight:'3%'},
  ];

  function renderCriteria(data) {
    const orig=data.original_scores||{}, rebuilt=data.rebuilt_scores||{};
    DOM.criteria.innerHTML = CRITERIA_META.map(c=>{
      const oVal=Math.round(orig[c.key]||0), rVal=Math.round(rebuilt[c.key]||0);
      const oCol=barCol(oVal), rCol=barCol(rVal);
      return `<div class="rbd-crit">
        <div class="rbd-crit__head">
          <span class="rbd-crit__name">${c.label}</span>
          <span class="rbd-crit__weight">${c.weight}</span>
        </div>
        <div class="rbd-crit__bars">
          <div class="rbd-bar-row">
            <span class="rbd-bar-row__tag">Before</span>
            <div class="rbd-bar-track"><div class="rbd-bar-fill rbd-bar-fill--orig" data-w="${oVal}%" style="background:${oCol}"></div></div>
            <span class="rbd-bar-row__score" style="color:${oCol}">${oVal}</span>
          </div>
          <div class="rbd-bar-row">
            <span class="rbd-bar-row__tag" style="color:#059669">After</span>
            <div class="rbd-bar-track"><div class="rbd-bar-fill rbd-bar-fill--rebuilt" data-w="${rVal}%" style="background:${rCol}"></div></div>
            <span class="rbd-bar-row__score" style="color:${rCol}">${rVal}</span>
          </div>
        </div>
      </div>`;
    }).join('');
    requestAnimationFrame(()=>{
      document.querySelectorAll('.rbd-bar-fill[data-w]').forEach(el=>el.style.width=el.dataset.w);
    });
  }

  /* ── CV document render ── */
  const SECTION_ORDER = ['contact','summary','experience','education','skills','certifications','projects','achievements','languages','interests'];

  function renderCvDoc(sections) {
    const ordered=[
      ...SECTION_ORDER.filter(k=>sections[k]),
      ...Object.keys(sections).filter(k=>!SECTION_ORDER.includes(k)&&sections[k]),
    ];
    if (!ordered.length) { DOM.cvDoc.innerHTML='<p style="color:var(--color-muted);text-align:center;padding:48px">No sections to display.</p>'; return; }
    DOM.cvDoc.innerHTML = ordered.map(key=>key==='contact'?renderContact(sections[key]):renderSection(key,sections[key])).join('');
  }

  function renderContact(text) {
    const lines=(text||'').split('\n').map(l=>l.trim()).filter(Boolean);
    const name=lines[0]||'';
    const parts=lines.slice(1).join(' | ').split('|').map(p=>p.trim()).filter(Boolean);
    const detailHtml=parts.map((p,i)=>`<span>${esc(p)}</span>${i<parts.length-1?'<span class="cv-contact__sep">|</span>':''}`).join('');
    return `<div class="cv-contact"><h1 class="cv-contact__name">${esc(name)}</h1><div class="cv-contact__details">${detailHtml}</div></div>`;
  }

  function renderSection(key, text) {
    const heading=key.charAt(0).toUpperCase()+key.slice(1);
    const content=key==='experience'?renderExperience(text):key==='skills'?renderSkills(text):key==='education'?renderEducation(text):textToHtml(text);
    return `<div class="cv-section"><h2 class="cv-section__heading">${heading}</h2><div class="cv-section__body">${content}</div></div>`;
  }

  function renderExperience(text) {
    const normalised=text.replace(/\n{3,}/g,'\n\n');
    const blocks=normalised.split(/\n\n+/).map(b=>b.trim()).filter(Boolean);
    const entries=blocks.length>1?blocks:[text];
    return entries.map(block=>{
      const lines=block.split('\n').map(l=>l.trim()).filter(Boolean);
      if(!lines.length) return '';
      const titleIdx=lines.findIndex(l=>!/^[-•*–]\s/.test(l));
      const title=titleIdx>=0?lines[titleIdx]:lines[0];
      const remaining=lines.slice(titleIdx+1);
      const metaLines=[],bulletLines=[];
      for(const line of remaining){
        if(/^[-•*–]\s/.test(line)) bulletLines.push(line);
        else if(!bulletLines.length) metaLines.push(line);
        else bulletLines.push(line);
      }
      const bulletsHtml=bulletLines.length?`<ul class="cv-exp-entry__bullets">${bulletLines.map(b=>`<li>${esc(b.replace(/^[-•*–]\s*/,''))}</li>`).join('')}</ul>`:'';
      return `<div class="cv-exp-entry"><p class="cv-exp-entry__title">${esc(title)}</p>${metaLines.length?`<p class="cv-exp-entry__meta">${esc(metaLines.join(' · '))}</p>`:''}${bulletsHtml}</div>`;
    }).join('');
  }

  function renderEducation(text) {
    const lines=text.split('\n').map(l=>l.trim()).filter(Boolean);
    return `<div class="cv-edu-block">${lines.map(l=>`<p class="cv-edu-line">${esc(l)}</p>`).join('')}</div>`;
  }

  function renderSkills(text) {
    const lines=text.split('\n').map(l=>l.trim()).filter(Boolean);
    return `<div class="cv-skills-grid">${lines.map(line=>{
      const ci=line.indexOf(':');
      if(ci>0){const lbl=line.slice(0,ci).trim(),val=line.slice(ci+1).trim();return `<div class="cv-skill-row"><strong>${esc(lbl)}:</strong> ${esc(val)}</div>`;}
      return `<div class="cv-skill-row">${esc(line)}</div>`;
    }).join('')}</div>`;
  }

  function textToHtml(text) {
    const cleaned=text.replace(/\n{3,}/g,'\n\n');
    const lines=cleaned.split('\n');
    let html='',inList=false;
    for(const line of lines){
      const t=line.trim();
      if(!t){if(inList){html+='</ul>';inList=false;}html+='<br>';continue;}
      if(/^[-•*]\s/.test(t)){if(!inList){html+='<ul>';inList=true;}html+=`<li>${esc(t.replace(/^[-•*]\s*/,''))}</li>`;}
      else{if(inList){html+='</ul>';inList=false;}html+=`<p style="margin:0 0 4px">${esc(t)}</p>`;}
    }
    if(inList) html+='</ul>';
    return html;
  }

  function esc(str) {
    return (str||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function renderGaps(data) {
    const gaps=(data.missing_keywords||[]).slice(0,20);
    if(!gaps.length){DOM.gapsCard.style.display='none';return;}
    DOM.gapsCard.style.display='block';
    DOM.gaps.innerHTML=gaps.map(k=>`<span class="rbd-gap-pill">${k}</span>`).join('');
  }

  /* ── Downloads ── */
  DOM.dlPdf?.addEventListener('click',  ()=>window.RBDDownload?.pdf(DATA, DOM));
  DOM.dlDocx?.addEventListener('click', ()=>window.RBDDownload?.docx(DATA));

  /* ── User ── */
  async function loadUser() {
    try {
      const d=await apiFetch('/auth/me',{headers:{'Content-Type':'application/json'}});
      const n=d.name||d.username||'User';
      if(DOM.username) DOM.username.textContent=n;
      if(DOM.avatar)   DOM.avatar.textContent=n.charAt(0).toUpperCase();
    } catch(_){}
  }

  /* ── Expose showUploadScreen globally ── */
  window.showUploadScreen = showUploadScreen;

  /* ── Boot ── */
  const params = new URLSearchParams(window.location.search);
  ANALYSIS_ID  = parseInt(params.get('analysis_id'));
  loadUser();

  if (ANALYSIS_ID && !isNaN(ANALYSIS_ID)) {
    // Came from History page — run rebuild directly
    bootFromAnalysis(ANALYSIS_ID);
  } else {
    // Independent page — show upload screen
    showUploadScreen();
  }

})();