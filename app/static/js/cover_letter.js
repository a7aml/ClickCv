/**
 * Cover Letter Generator - Frontend Logic
 * Handles UI interactions, file upload, validation, and display
 * API calls handled by cover_letter_api.js
 */

// ═══════════════════════════════════════════════════════════════════════
// STATE MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════

let state = {
    cvFile: null,
    jobDescription: '',
    companyName: '',
    positionTitle: '',
    generatedLetter: null,
    currentCoverLetterId: null  // Store generated cover letter ID
};

// ═══════════════════════════════════════════════════════════════════════
// DOM ELEMENTS
// ═══════════════════════════════════════════════════════════════════════

const elements = {
    // Upload Zone
    cvUploadZone: document.getElementById('cv-upload-zone'),
    cvFileInput: document.getElementById('cv-file-input'),
    browseCv: document.getElementById('browse-cv'),
    uploadedCv: document.getElementById('uploaded-cv'),
    cvFileName: document.getElementById('cv-file-name'),
    cvFileSize: document.getElementById('cv-file-size'),
    removeCv: document.getElementById('remove-cv'),
    
    // Job Description
    jobDescription: document.getElementById('job-description'),
    jdCharCount: document.getElementById('jd-char-count'),
    
    // Company Details
    companyName: document.getElementById('company-name'),
    positionTitle: document.getElementById('position-title'),
    
    // Generate Button
    generateBtn: document.getElementById('generate-btn'),
    
    // States
    emptyState: document.getElementById('empty-state'),
    loadingState: document.getElementById('loading-state'),
    resultState: document.getElementById('result-state'),
    
    // Result Actions
    coverLetterContent: document.getElementById('cover-letter-content'),
    copyBtn: document.getElementById('copy-btn'),
    downloadBtn: document.getElementById('download-btn'),
    regenerateBtn: document.getElementById('regenerate-btn'),
    
    // Toast
    toast: document.getElementById('toast')
};

// ═══════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function() {
    initializeEventListeners();
    checkGenerateButtonState();
});

function initializeEventListeners() {
    // File Upload Events
    elements.cvUploadZone.addEventListener('click', () => elements.cvFileInput.click());
    elements.browseCv.addEventListener('click', (e) => {
        e.stopPropagation();
        elements.cvFileInput.click();
    });
    elements.cvFileInput.addEventListener('change', handleFileSelect);
    elements.removeCv.addEventListener('click', removeFile);
    
    // Drag & Drop Events
    elements.cvUploadZone.addEventListener('dragover', handleDragOver);
    elements.cvUploadZone.addEventListener('dragleave', handleDragLeave);
    elements.cvUploadZone.addEventListener('drop', handleDrop);
    
    // Job Description Events
    elements.jobDescription.addEventListener('input', handleJdInput);
    
    // Company Details Events
    elements.companyName.addEventListener('input', (e) => {
        state.companyName = e.target.value.trim();
    });
    elements.positionTitle.addEventListener('input', (e) => {
        state.positionTitle = e.target.value.trim();
    });
    
    // Generate Button
    elements.generateBtn.addEventListener('click', handleGenerate);
    
    // Result Actions
    elements.copyBtn.addEventListener('click', handleCopy);
    elements.downloadBtn.addEventListener('click', handleDownload);
    elements.regenerateBtn.addEventListener('click', handleRegenerate);
}

// ═══════════════════════════════════════════════════════════════════════
// FILE UPLOAD HANDLING
// ═══════════════════════════════════════════════════════════════════════

function handleFileSelect(e) {
    const file = e.target.files[0];
    if (file) {
        validateAndSetFile(file);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    elements.cvUploadZone.classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    elements.cvUploadZone.classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    elements.cvUploadZone.classList.remove('dragover');
    
    const file = e.dataTransfer.files[0];
    if (file) {
        validateAndSetFile(file);
    }
}

function validateAndSetFile(file) {
    // Validate file type
    const validTypes = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
    const validExtensions = ['.pdf', '.docx'];
    const fileName = file.name.toLowerCase();
    const hasValidExtension = validExtensions.some(ext => fileName.endsWith(ext));
    
    if (!validTypes.includes(file.type) && !hasValidExtension) {
        showToast('Please upload a PDF or DOCX file only.', 'error');
        return;
    }
    
    // Validate file size (max 5MB)
    const maxSize = 5 * 1024 * 1024;
    if (file.size > maxSize) {
        showToast('File size must be less than 5MB.', 'error');
        return;
    }
    
    // Store file in state
    state.cvFile = file;
    
    // Display file info
    displayUploadedFile(file);
    
    // Check if generate button should be enabled
    checkGenerateButtonState();
    
    showToast('CV uploaded successfully!', 'success');
}

function displayUploadedFile(file) {
    elements.cvUploadZone.style.display = 'none';
    elements.uploadedCv.style.display = 'flex';
    elements.cvFileName.textContent = file.name;
    elements.cvFileSize.textContent = formatFileSize(file.size);
}

function removeFile() {
    state.cvFile = null;
    elements.cvFileInput.value = '';
    elements.uploadedCv.style.display = 'none';
    elements.cvUploadZone.style.display = 'block';
    checkGenerateButtonState();
    showToast('CV removed.', 'success');
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i)) + ' ' + sizes[i];
}

// ═══════════════════════════════════════════════════════════════════════
// JOB DESCRIPTION HANDLING
// ═══════════════════════════════════════════════════════════════════════

function handleJdInput(e) {
    const text = e.target.value;
    state.jobDescription = text;
    elements.jdCharCount.textContent = text.length;
    checkGenerateButtonState();
}

// ═══════════════════════════════════════════════════════════════════════
// VALIDATION & BUTTON STATE
// ═══════════════════════════════════════════════════════════════════════

function checkGenerateButtonState() {
    const isValid = state.cvFile !== null && state.jobDescription.trim().length > 50;
    elements.generateBtn.disabled = !isValid;
}

// ═══════════════════════════════════════════════════════════════════════
// GENERATE COVER LETTER (REAL API CALL)
// ═══════════════════════════════════════════════════════════════════════

async function handleGenerate() {
    // Validation
    if (!state.cvFile) {
        showToast('Please upload your CV first.', 'error');
        return;
    }
    
    if (state.jobDescription.trim().length < 50) {
        showToast('Job description is too short. Please provide more details.', 'error');
        return;
    }
    
    // Show loading state
    showState('loading');
    
    try {
        // Call backend API
        const response = await apiGenerateCoverLetter(
            state.cvFile,
            state.jobDescription,
            state.companyName,
            state.positionTitle
        );
        
        // Store cover letter ID for future reference
        state.currentCoverLetterId = response.cover_letter_id;
        
        // Display generated cover letter
        displayGeneratedLetter(response.cover_letter);
        
        showToast('Cover letter generated successfully!', 'success');
        
    } catch (error) {
        console.error('Generation error:', error);
        showToast(error.message || 'Failed to generate cover letter. Please try again.', 'error');
        showState('empty');
    }
}

function displayGeneratedLetter(letterText) {
    state.generatedLetter = letterText;
    elements.coverLetterContent.textContent = letterText;
    showState('result');
}

// ═══════════════════════════════════════════════════════════════════════
// STATE MANAGEMENT (EMPTY/LOADING/RESULT)
// ═══════════════════════════════════════════════════════════════════════

function showState(stateName) {
    elements.emptyState.style.display = 'none';
    elements.loadingState.style.display = 'none';
    elements.resultState.style.display = 'none';
    
    switch(stateName) {
        case 'empty':
            elements.emptyState.style.display = 'flex';
            break;
        case 'loading':
            elements.loadingState.style.display = 'flex';
            break;
        case 'result':
            elements.resultState.style.display = 'flex';
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════════
// RESULT ACTIONS (COPY, DOWNLOAD, REGENERATE)
// ═══════════════════════════════════════════════════════════════════════

function handleCopy() {
    if (!state.generatedLetter) {
        showToast('No cover letter to copy.', 'error');
        return;
    }
    
    navigator.clipboard.writeText(state.generatedLetter)
        .then(() => {
            showToast('Cover letter copied to clipboard!', 'success');
            
            const originalText = elements.copyBtn.innerHTML;
            elements.copyBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
                Copied!
            `;
            
            setTimeout(() => {
                elements.copyBtn.innerHTML = originalText;
            }, 2000);
        })
        .catch(err => {
            console.error('Copy failed:', err);
            showToast('Failed to copy. Please try again.', 'error');
        });
}

function handleDownload() {
    if (!state.generatedLetter) {
        showToast('No cover letter to download.', 'error');
        return;
    }
    
    const blob = new Blob([state.generatedLetter], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    const company = state.companyName || 'Company';
    const position = state.positionTitle || 'Position';
    const filename = `Cover_Letter_${company}_${position}.txt`.replace(/\s+/g, '_');
    
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showToast('Cover letter downloaded!', 'success');
}

function handleRegenerate() {
    if (!confirm('Are you sure you want to regenerate the cover letter? The current version will be replaced.')) {
        return;
    }
    
    handleGenerate();
}

// ═══════════════════════════════════════════════════════════════════════
// TOAST NOTIFICATIONS
// ═══════════════════════════════════════════════════════════════════════

function showToast(message, type = 'success') {
    const toast = elements.toast;
    toast.textContent = message;
    toast.className = 'toast';
    
    if (type === 'success') {
        toast.classList.add('success');
    } else if (type === 'error') {
        toast.classList.add('error');
    }
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 100);
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}