/* ==========================================================================
   profile_settings.js  —  ClickCV Profile Settings
   ========================================================================== */

function getToken()  { return localStorage.getItem("access_token"); }
function clearToken(){ localStorage.removeItem("access_token"); }

async function apiFetch(url, method = "GET", body = null) {
  const token = getToken();
  if (!token) { window.location.href = "/signin"; return { ok: false, data: {} }; }
  const headers = { Authorization: `Bearer ${token}` };
  if (body && !(body instanceof FormData)) headers["Content-Type"] = "application/json";
  const options = { method, headers, credentials: "same-origin" };
  if (body) options.body = body instanceof FormData ? body : JSON.stringify(body);
  try {
    const res = await fetch(url, options);
    if (res.status === 401 || res.status === 422) { clearToken(); window.location.href = "/signin"; return { ok: false, data: {} }; }
    const data = await res.json();
    return { ok: res.ok, status: res.status, data };
  } catch { return { ok: false, status: 0, data: { error: "Network error. Please try again." } }; }
}

function showToast(message, type = "success") {
  document.querySelector(".cv-toast")?.remove();
  const toast = document.createElement("div");
  toast.className = "cv-toast";
  toast.style.cssText = `position:fixed;bottom:28px;right:28px;z-index:9999;display:flex;align-items:center;gap:12px;padding:14px 20px;border-radius:14px;min-width:260px;max-width:380px;background:${type === "success" ? "#10b981" : "#ef4444"};color:#fff;font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;font-weight:600;box-shadow:0 8px 32px rgba(0,0,0,0.18);animation:cvToastIn .35s cubic-bezier(.21,1.02,.73,1) both;`;
  toast.innerHTML = `<span style="font-size:18px">${type === "success" ? "✓" : "✕"}</span><span>${message}</span>`;
  if (!document.getElementById("cv-toast-style")) {
    const s = document.createElement("style"); s.id = "cv-toast-style";
    s.textContent = `@keyframes cvToastIn{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}@keyframes cvToastOut{from{opacity:1;transform:translateY(0)}to{opacity:0;transform:translateY(16px)}}@keyframes cvSpin{to{transform:rotate(360deg)}}`;
    document.head.appendChild(s);
  }
  document.body.appendChild(toast);
  setTimeout(() => { toast.style.animation = "cvToastOut .3s ease forwards"; setTimeout(() => toast.remove(), 300); }, 3500);
}

function setLoading(btn, text = "Saving…") {
  if (!btn) return () => {};
  const original = btn.innerHTML; btn.disabled = true; btn.style.opacity = "0.7";
  btn.innerHTML = `<span style="display:inline-flex;align-items:center;gap:8px"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="animation:cvSpin .8s linear infinite"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>${text}</span>`;
  return () => { btn.disabled = false; btn.style.opacity = ""; btn.innerHTML = original; };
}

async function loadProfile() {
  const { ok, data } = await apiFetch("/api/profile");
  if (!ok) return;
  const firstEl = document.getElementById("first-name");
  const lastEl  = document.getElementById("last-name");
  if (firstEl) firstEl.value = data.first_name || "";
  if (lastEl)  lastEl.value  = data.last_name  || "";
  const emailEl = document.getElementById("email");
  if (emailEl) { emailEl.value = data.email || ""; emailEl.dataset.provider = data.auth_provider; }
  const isGoogle = data.auth_provider === "google";
  const badge     = document.getElementById("google-badge");
  const emailHint = document.getElementById("email-hint");
  if (badge)     badge.style.display     = isGoogle ? "" : "none";
  if (emailHint) emailHint.style.display = isGoogle ? "" : "none";
  refreshAvatarUI(data.first_name, data.avatar_url);
  const avatarNameEl  = document.getElementById("avatar-name");
  const avatarSinceEl = document.getElementById("avatar-since");
  const topbarNameEl  = document.getElementById("topbar-name");
  if (avatarNameEl)  avatarNameEl.textContent  = `${data.first_name || ""} ${data.last_name || ""}`.trim();
  if (avatarSinceEl) avatarSinceEl.textContent = `Member since ${data.created_at || "—"}`;
  if (topbarNameEl)  topbarNameEl.textContent  = data.first_name || data.email;
  if (isGoogle) lockPasswordSection(); else unlockPasswordSection();
}

async function loadStats() {
  const { ok, data } = await apiFetch("/api/profile/stats");
  const totalEl = document.getElementById("stat-total");
  const avgEl   = document.getElementById("stat-avg");
  const lastEl  = document.getElementById("stat-last");
  const sinceEl = document.getElementById("stat-since");
  const sidebarVal  = document.getElementById("sidebar-analyses");
  const sidebarDesc = document.getElementById("sidebar-score");
  const remove = el => el?.classList.remove("stat-loading");

  if (!ok) {
    if (totalEl) { totalEl.textContent = "0"; remove(totalEl); }
    if (avgEl)   { avgEl.textContent   = "—"; remove(avgEl); }
    if (lastEl)  { lastEl.textContent  = "—"; remove(lastEl); }
    if (sinceEl) { sinceEl.textContent = "—"; remove(sinceEl); }
    if (sidebarVal)  sidebarVal.textContent  = "0 analyses";
    if (sidebarDesc) sidebarDesc.textContent = "No analyses yet. Upload your first CV!";
    return;
  }
  if (totalEl) { totalEl.textContent = data.total_analyses ?? 0; remove(totalEl); }
  if (avgEl)   { avgEl.textContent   = data.avg_score ? `${data.avg_score}/100` : "—"; remove(avgEl); }
  if (lastEl)  { lastEl.textContent  = data.last_analysis  || "—"; remove(lastEl); }
  if (sinceEl) { sinceEl.textContent = data.member_since   || "—"; remove(sinceEl); }
  if (sidebarVal)  sidebarVal.textContent  = `${data.total_analyses ?? 0} analyses`;
  if (sidebarDesc) sidebarDesc.textContent = data.avg_score ? `Your average CV score is ${data.avg_score}/100.` : "No analyses yet. Upload your first CV!";
}

/* ══════════════════════════════════════
   AVATAR DISPLAY (read-only)
   Renders the user's initial or an existing
   avatar_url from the server. No upload UI.
══════════════════════════════════════ */
function refreshAvatarUI(firstName, avatarUrl) {
  const bigAvatar    = document.getElementById("avatar-img");
  const topbarAvatar = document.getElementById("topbar-avatar");
  const initial      = (firstName || "?")[0].toUpperCase();
  if (avatarUrl) {
    if (bigAvatar)    bigAvatar.innerHTML    = `<img src="${avatarUrl}" style="width:100%;height:100%;border-radius:50%;object-fit:cover;" alt="avatar">`;
    if (topbarAvatar) topbarAvatar.innerHTML = `<img src="${avatarUrl}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;" alt="avatar">`;
  } else {
    if (bigAvatar)    bigAvatar.textContent    = initial;
    if (topbarAvatar) topbarAvatar.textContent = initial;
  }
}

function lockPasswordSection() {
  ["current-password","new-password","confirm-password"].forEach(id => {
    const el = document.getElementById(id); if (!el) return;
    el.disabled = true; el.value = ""; el.placeholder = "Managed by Google";
    el.style.background = "rgba(15,22,36,0.04)"; el.style.cursor = "not-allowed";
  });
  const btn = document.querySelector('[data-action="update-password"]');
  if (btn) { btn.disabled = true; btn.style.opacity = "0.4"; btn.style.cursor = "not-allowed"; }
  const securityBody = document.getElementById("section-security")?.closest(".card")?.querySelector(".card__body");
  if (securityBody && !securityBody.querySelector(".google-notice")) {
    const notice = document.createElement("div"); notice.className = "google-notice";
    notice.style.cssText = `padding:12px 16px;border-radius:10px;margin-bottom:16px;background:rgba(6,182,212,.08);border:1px solid rgba(6,182,212,.20);font-size:13px;color:#0891b2;font-weight:600;display:flex;align-items:center;gap:8px;`;
    notice.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>Your password is managed by your Google account.`;
    securityBody.prepend(notice);
  }
}

function unlockPasswordSection() {
  const placeholders = {"current-password":"Enter current password","new-password":"Minimum 6 characters","confirm-password":"Re-enter new password"};
  ["current-password","new-password","confirm-password"].forEach(id => {
    const el = document.getElementById(id); if (!el) return;
    el.disabled = false; el.placeholder = placeholders[id];
    el.style.background = ""; el.style.cursor = ""; el.style.color = "";
  });
  const btn = document.querySelector('[data-action="update-password"]');
  if (btn) { btn.disabled = false; btn.style.opacity = ""; btn.style.cursor = ""; }
  document.querySelector(".google-notice")?.remove();
}

async function saveProfileInfo() {
  const btn       = document.querySelector('[data-action="save-info"]');
  const firstName = document.getElementById("first-name")?.value.trim();
  const lastName  = document.getElementById("last-name")?.value.trim() || "";
  if (!firstName) { showToast("First name cannot be empty.", "error"); return; }
  const restore = setLoading(btn, "Saving…");
  const { ok, data } = await apiFetch("/api/profile/info", "PUT", { first_name: firstName, last_name: lastName });
  restore();
  if (ok) {
    showToast(data.message); refreshAvatarUI(firstName, null);
    const topbarNameEl = document.getElementById("topbar-name");
    const avatarNameEl = document.getElementById("avatar-name");
    if (topbarNameEl) topbarNameEl.textContent = firstName;
    if (avatarNameEl) avatarNameEl.textContent = `${firstName} ${lastName}`.trim();
  } else { showToast(data.error || "Failed to update profile.", "error"); }
}

async function updatePassword() {
  const btn      = document.querySelector('[data-action="update-password"]');
  const provider = document.getElementById("email")?.dataset.provider;
  if (provider === "google") { showToast("Password is managed by Google.", "error"); return; }
  const current = document.getElementById("current-password")?.value || "";
  const next    = document.getElementById("new-password")?.value     || "";
  const confirm = document.getElementById("confirm-password")?.value || "";
  if (!current || !next || !confirm) { showToast("Please fill in all password fields.", "error"); return; }
  if (next !== confirm) { showToast("New passwords do not match.", "error"); return; }
  if (next.length < 6) { showToast("Password must be at least 6 characters.", "error"); return; }
  const restore = setLoading(btn, "Updating…");
  const { ok, data } = await apiFetch("/api/profile/password", "PUT", { current_password: current, new_password: next, confirm_password: confirm });
  restore();
  if (ok) { showToast(data.message); ["current-password","new-password","confirm-password"].forEach(id => { const el = document.getElementById(id); if (el) el.value = ""; }); }
  else { showToast(data.error || "Failed to update password.", "error"); }
}

function confirmDeleteAccount() {
  document.getElementById("cv-delete-modal")?.remove();
  const isGoogle = document.getElementById("email")?.dataset.provider === "google";
  const modal = document.createElement("div"); modal.id = "cv-delete-modal";
  modal.style.cssText = `position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(15,22,36,0.55);backdrop-filter:blur(6px);animation:cvToastIn .25s ease both;`;
  modal.innerHTML = `<div style="background:#fff;border-radius:20px;padding:36px;max-width:440px;width:90%;box-shadow:0 24px 60px rgba(0,0,0,0.18);font-family:'Plus Jakarta Sans',sans-serif;">
    <div style="width:52px;height:52px;border-radius:14px;background:rgba(239,68,68,.10);border:1px solid rgba(239,68,68,.20);display:grid;place-items:center;margin-bottom:20px;"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>
    <h3 style="font-size:18px;font-weight:800;color:#0f1624;margin-bottom:8px;">Delete Account</h3>
    <p style="font-size:14px;color:rgba(15,22,36,0.60);line-height:1.65;margin-bottom:24px;">This will permanently delete your account and all your CV data. <strong>This cannot be undone.</strong></p>
    ${!isGoogle ? `<div style="margin-bottom:20px;"><label style="font-size:13px;font-weight:700;color:rgba(15,22,36,.75);display:block;margin-bottom:8px;">Confirm your password</label><input id="delete-pw-input" type="password" placeholder="Enter your password" style="width:100%;padding:11px 14px;border-radius:11px;outline:none;border:1px solid rgba(37,99,235,.18);font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;color:#0f1624;"></div>` : `<p style="font-size:13px;color:#0891b2;background:rgba(6,182,212,.08);border:1px solid rgba(6,182,212,.2);border-radius:10px;padding:12px 16px;margin-bottom:20px;">Your account is linked via Google. No password needed.</p>`}
    <div style="display:flex;gap:12px;justify-content:flex-end;">
      <button id="cancel-delete-btn" style="padding:10px 20px;border-radius:999px;border:1px solid rgba(37,99,235,.16);background:transparent;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;font-weight:700;color:#0f1624;">Cancel</button>
      <button id="confirm-delete-btn" style="padding:10px 20px;border-radius:999px;border:none;background:#ef4444;color:#fff;cursor:pointer;font-family:'Plus Jakarta Sans',sans-serif;font-size:14px;font-weight:700;">Yes, Delete My Account</button>
    </div></div>`;
  document.body.appendChild(modal);
  document.getElementById("cancel-delete-btn").addEventListener("click", () => modal.remove());
  modal.addEventListener("click", e => { if (e.target === modal) modal.remove(); });
  document.getElementById("confirm-delete-btn").addEventListener("click", async () => {
    const pwInput = document.getElementById("delete-pw-input");
    const password = pwInput?.value.trim() || null;
    if (!isGoogle && !password) { if (pwInput) pwInput.style.borderColor = "#ef4444"; return; }
    const confirmBtn = document.getElementById("confirm-delete-btn"); confirmBtn.disabled = true; confirmBtn.textContent = "Deleting…";
    const body = password ? { password } : {};
    const { ok, data } = await apiFetch("/api/profile/account", "DELETE", body);
    if (ok) { modal.remove(); clearToken(); showToast("Account deleted. Redirecting…"); setTimeout(() => { window.location.href = "/"; }, 1800); }
    else { confirmBtn.disabled = false; confirmBtn.textContent = "Yes, Delete My Account"; showToast(data.error || "Failed to delete account.", "error"); if (pwInput) pwInput.style.borderColor = "#ef4444"; }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  if (!getToken()) { window.location.href = "/signin"; return; }
  loadProfile();
  loadStats();   // <-- Fetches and displays account statistics
  document.querySelector('[data-action="save-info"]')?.addEventListener("click", saveProfileInfo);
  document.querySelector('[data-action="update-password"]')?.addEventListener("click", updatePassword);
  document.querySelector('[data-action="delete-account"]')?.addEventListener("click", confirmDeleteAccount);
});