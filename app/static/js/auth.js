// ============================================================
// CONFIG
// ============================================================
const API_BASE = 'http://127.0.0.1:5000';


// ============================================================
// HELPERS
// ============================================================

function saveToken(token) {
    localStorage.setItem('access_token', token);
}

function getToken() {
    return localStorage.getItem('access_token');
}

function removeToken() {
    localStorage.removeItem('access_token');
}

function showError(message) {
    const existing = document.querySelector('.form__error');
    if (existing) existing.remove();

    const error = document.createElement('p');
    error.className = 'form__error';
    error.style.cssText = 'color:#e53e3e;font-size:0.875rem;margin-top:0.5rem;text-align:center;';
    error.textContent = message;

    const btn = document.querySelector('.btn--primary');
    if (btn) btn.insertAdjacentElement('beforebegin', error);
}

function showSuccess(message) {
    const existing = document.querySelector('.form__error');
    if (existing) existing.remove();

    const success = document.createElement('p');
    success.className = 'form__error';
    success.style.cssText = 'color:#38a169;font-size:0.875rem;margin-top:0.5rem;text-align:center;';
    success.textContent = message;

    const btn = document.querySelector('.btn--primary');
    if (btn) btn.insertAdjacentElement('beforebegin', success);
}

function setButtonLoading(btn, isLoading, originalText) {
    btn.disabled = isLoading;
    btn.textContent = isLoading ? 'Please wait...' : originalText;
}


// ============================================================
// SIGN IN
// ============================================================

async function handleSignIn(e) {
    e.preventDefault();

    const email    = document.getElementById('email').value.trim();
    const password = document.getElementById('password').value;
    const btn      = document.querySelector('.btn--primary');

    if (!email || !password) {
        showError('Please fill in all fields.');
        return;
    }

    setButtonLoading(btn, true, 'Log In');

    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            showError(data.error || 'Login failed. Please try again.');
            return;
        }

        saveToken(data.access_token);
        showSuccess('Login successful! Redirecting...');

        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 1000);

    } catch (err) {
        showError('Unable to connect to server. Please try again.');
        console.error('Login error:', err);
    } finally {
        setButtonLoading(btn, false, 'Log In');
    }
}


// ============================================================
// SIGN UP
// ============================================================

async function handleSignUp(e) {
    e.preventDefault();

    const name            = document.getElementById('fullName').value.trim();
    const email           = document.getElementById('email').value.trim();
    const password        = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    const btn             = document.querySelector('.btn--primary');

    if (!name || !email || !password || !confirmPassword) {
        showError('Please fill in all fields.');
        return;
    }

    if (password.length < 6) {
        showError('Password must be at least 6 characters.');
        return;
    }

    if (password !== confirmPassword) {
        showError('Passwords do not match.');
        return;
    }

    setButtonLoading(btn, true, 'Create Account');

    try {
        const response = await fetch(`${API_BASE}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email, password })
        });

        const data = await response.json();

        if (!response.ok) {
            showError(data.error || 'Registration failed. Please try again.');
            return;
        }

        saveToken(data.access_token);
        showSuccess('Account created! Redirecting...');

        setTimeout(() => {
            window.location.href = '/dashboard';
        }, 1000);

    } catch (err) {
        showError('Unable to connect to server. Please try again.');
        console.error('Register error:', err);
    } finally {
        setButtonLoading(btn, false, 'Create Account');
    }
}


// ============================================================
// GOOGLE OAUTH
// ============================================================

function handleGoogleLogin() {
    window.location.href = `${API_BASE}/auth/google/login`;
}


// ============================================================
// HANDLE TOKEN FROM URL
// After Google OAuth, Flask redirects to /dashboard?token=xxx
// ============================================================

function handleTokenFromURL() {
    const params = new URLSearchParams(window.location.search);
    const token  = params.get('token');
    const error  = params.get('error');

    if (token) {
        saveToken(token);
        window.history.replaceState({}, document.title, '/dashboard');
    }

    if (error) {
        window.location.href = `/signin?error=${error}`;
    }
}


// ============================================================
// HANDLE ERROR FROM URL
// ============================================================

function handleErrorFromURL() {
    const params = new URLSearchParams(window.location.search);
    const error  = params.get('error');

    if (error) {
        const messages = {
            'google_failed':           'Google sign-in failed. Please try again.',
            'google_account_no_email': 'Your Google account has no email address.',
        };
        showError(messages[error] || 'Something went wrong. Please try again.');
        window.history.replaceState({}, document.title, window.location.pathname);
    }
}


// ============================================================
// LOGOUT
// ============================================================

function logout() {
    removeToken();
    window.location.href = '/signin';
}


// ============================================================
// AUTO REDIRECT
// ============================================================

function redirectIfLoggedIn() {
    const token = getToken();
    if (token) {
        window.location.href = '/dashboard';
    }
}


// ============================================================
// INIT
// ============================================================

document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path.includes('signin')) {
        redirectIfLoggedIn();
        handleErrorFromURL();
        const form = document.querySelector('.form');
        if (form) form.addEventListener('submit', handleSignIn);
        const googleBtn = document.querySelector('.btn--google');
        if (googleBtn) googleBtn.addEventListener('click', handleGoogleLogin);
    }

    if (path.includes('signup')) {
        redirectIfLoggedIn();
        handleErrorFromURL();
        const form = document.querySelector('.form');
        if (form) form.addEventListener('submit', handleSignUp);
        const googleBtn = document.querySelector('.btn--google');
        if (googleBtn) googleBtn.addEventListener('click', handleGoogleLogin);
    }

    if (path.includes('dashboard')) {
        handleTokenFromURL();
    }

    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) logoutBtn.addEventListener('click', logout);
});