/**
 * Cover Letter API Integration
 * Handles all backend API calls for cover letter generation
 */

// ═══════════════════════════════════════════════════════════════════════
// API ENDPOINTS
// ═══════════════════════════════════════════════════════════════════════

const COVER_LETTER_API_BASE = '/api/cover-letter';  // ← RENAMED

const COVER_LETTER_API_ENDPOINTS = {  // ← RENAMED
    GENERATE: `${COVER_LETTER_API_BASE}/generate`,
    GET: (id) => `${COVER_LETTER_API_BASE}/${id}`,
    HISTORY: `${COVER_LETTER_API_BASE}/history`,
    DELETE: (id) => `${COVER_LETTER_API_BASE}/${id}`
};

// ═══════════════════════════════════════════════════════════════════════
// HELPER: GET AUTH TOKEN
// ═══════════════════════════════════════════════════════════════════════

function getAuthToken() {
    return localStorage.getItem('access_token');
}

// ═══════════════════════════════════════════════════════════════════════
// API CALL: GENERATE COVER LETTER
// ═══════════════════════════════════════════════════════════════════════

async function apiGenerateCoverLetter(cvFile, jobDescription, companyName, positionTitle) {
    /**
     * Generate a cover letter via backend API.
     * 
     * @param {File} cvFile - CV file (PDF or DOCX)
     * @param {string} jobDescription - Job description text
     * @param {string} companyName - Company name (optional)
     * @param {string} positionTitle - Position title (optional)
     * @returns {Promise<Object>} Response data or throws error
     */
    
    const token = getAuthToken();
    
    if (!token) {
        throw new Error('Not authenticated. Please log in.');
    }
    
    // Build FormData
    const formData = new FormData();
    formData.append('cv_file', cvFile);
    formData.append('job_description', jobDescription);
    
    if (companyName && companyName.trim()) {
        formData.append('company_name', companyName.trim());
    }
    
    if (positionTitle && positionTitle.trim()) {
        formData.append('position_title', positionTitle.trim());
    }
    
    // Make API call
    const response = await fetch(COVER_LETTER_API_ENDPOINTS.GENERATE, {  // ← UPDATED
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${token}`
            // Note: Do NOT set Content-Type for FormData - browser sets it automatically with boundary
        },
        body: formData
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        // Extract error message from response
        const errorMessage = data.error || data.message || 'Failed to generate cover letter';
        throw new Error(errorMessage);
    }
    
    return data;
}

// ═══════════════════════════════════════════════════════════════════════
// API CALL: GET COVER LETTER BY ID
// ═══════════════════════════════════════════════════════════════════════

async function apiGetCoverLetter(coverLetterId) {
    /**
     * Retrieve a cover letter by ID.
     * 
     * @param {number} coverLetterId - Cover letter ID
     * @returns {Promise<Object>} Cover letter data or throws error
     */
    
    const token = getAuthToken();
    
    if (!token) {
        throw new Error('Not authenticated. Please log in.');
    }
    
    const response = await fetch(COVER_LETTER_API_ENDPOINTS.GET(coverLetterId), {  // ← UPDATED
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        const errorMessage = data.error || 'Failed to retrieve cover letter';
        throw new Error(errorMessage);
    }
    
    return data;
}

// ═══════════════════════════════════════════════════════════════════════
// API CALL: GET COVER LETTER HISTORY
// ═══════════════════════════════════════════════════════════════════════

async function apiGetCoverLetterHistory() {
    /**
     * Get all cover letters for current user.
     * 
     * @returns {Promise<Object>} History data with array of cover letters
     */
    
    const token = getAuthToken();
    
    if (!token) {
        throw new Error('Not authenticated. Please log in.');
    }
    
    const response = await fetch(COVER_LETTER_API_ENDPOINTS.HISTORY, {  // ← UPDATED
        method: 'GET',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        const errorMessage = data.error || 'Failed to retrieve history';
        throw new Error(errorMessage);
    }
    
    return data;
}

// ═══════════════════════════════════════════════════════════════════════
// API CALL: DELETE COVER LETTER
// ═══════════════════════════════════════════════════════════════════════

async function apiDeleteCoverLetter(coverLetterId) {
    /**
     * Delete a cover letter by ID.
     * 
     * @param {number} coverLetterId - Cover letter ID to delete
     * @returns {Promise<Object>} Success message or throws error
     */
    
    const token = getAuthToken();
    
    if (!token) {
        throw new Error('Not authenticated. Please log in.');
    }
    
    const response = await fetch(COVER_LETTER_API_ENDPOINTS.DELETE(coverLetterId), {  // ← UPDATED
        method: 'DELETE',
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        const errorMessage = data.error || 'Failed to delete cover letter';
        throw new Error(errorMessage);
    }
    
    return data;
}