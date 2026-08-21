/**
 * پنل VPN - Telegram Mini Web App
 * ──────────────────────────────────
 * Persian RTL interface with full Telegram WebApp API integration.
 *
 * API endpoints expected (adjust BASE_URL for your backend):
 *   GET  /api/plans      → { plans: [{id,name,gb,days,price,is_ultimate,currency,section_id}] }
 *   GET  /api/wallet     → { balance, currency }
 *   GET  /api/configs    → { configs: [{id,plan_name,sub_link,expire_date,is_active}] }
 *   GET  /api/config/:id → { config: {...}, traffic: {total_gb,used_gb,remaining_gb,...} }
 *   GET  /api/invite     → { enabled, link, count, reward }
 *   GET  /api/card-info  → { card_number, card_owner }
 *   POST /api/buy        → { plan_id, method:'wallet'|'c2c' } → { success, config? }
 */
(function () {
    'use strict';

    /* ═══ Config ═══ */
    // If your API is on a different server, set the full URL here:
    // const BASE = 'https://your-server.com';
    const BASE = '';

    /* ═══ Telegram ═══ */
    const tg = window.Telegram && window.Telegram.WebApp;

    function initTG() {
        if (!tg) return;
        try {
            tg.expand();
            tg.enableClosingConfirmation();
            setTheme(tg.colorScheme);
            tg.onEvent('themeChanged', function () { setTheme(tg.colorScheme); });
            tg.MainButton.hide();
        } catch (e) { console.warn('TG init:', e); }
    }

    function setTheme(scheme) {
        document.documentElement.classList.toggle('dark', scheme === 'dark');
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = scheme === 'dark' ? '#0a0612' : '#ffffff';
        if (tg) {
            try { tg.setHeaderColor(scheme === 'dark' ? '#0a0612' : '#ffffff'); } catch (e) {}
            try { tg.setBackgroundColor(scheme === 'dark' ? '#0a0612' : '#f8f7fc'); } catch (e) {}
        }
    }

    function haptic(type) { try { tg && tg.HapticFeedback && tg.HapticFeedback.impactOccurred(type || 'light'); } catch (e) {} }

    /* ═══ User ═══ */
    function getUser() {
        if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) return tg.initDataUnsafe.user;
        return { id: 123456789, first_name: 'کاربر', last_name: 'آزمایشی', username: 'test_user', photo_url: null };
    }

    function displayName(u) {
        var n = (u.first_name || '') + ' ' + (u.last_name || '');
        return n.trim() || 'کاربر';
    }

    function initials(u) {
        return ((u.first_name || '?')[0] + (u.last_name || '')[0]).toUpperCase();
    }

    /* ═══ API ═══ */
    function apiHeaders() {
        var h = {};
        if (tg && tg.initData) h['Authorization'] = 'Bearer ' + tg.initData;
        return h;
    }

    async function apiGet(path) {
        try {
            var r = await fetch(BASE + '/api' + path, { headers: apiHeaders() });
            if (!r.ok) throw new Error(r.status);
            return await r.json();
        } catch (e) { console.error('GET ' + path, e); return null; }
    }

    async function apiPost(path, body) {
        try {
            var r = await fetch(BASE + '/api' + path, {
                method: 'POST',
                headers: Object.assign({ 'Content-Type': 'application/json' }, apiHeaders()),
                body: JSON.stringify(body || {})
            });
            if (!r.ok) throw new Error(r.status);
            return await r.json();
        } catch (e) { console.error('POST ' + path, e); return null; }
    }

    /* ═══ State ═══ */
    var plans = [], configs = [], wallet = null, invite = null, selectedPlan = null;
    var currentTab = 'services';

    /* ═══ Tab Navigation ═══ */
    window.goTab = function (tab) {
        if (tab === currentTab) return;
        haptic();
        currentTab = tab;
        document.querySelectorAll('.page').forEach(function (p) { p.classList.remove('active'); });
        var el = document.getElementById('pg-' + tab);
        if (el) { el.classList.add('active'); }
        document.querySelectorAll('.bnav-item').forEach(function (b) {
            b.classList.toggle('active', b.dataset.tab === tab);
        });
        if (tab === 'my-services') loadConfigs();
        if (tab === 'profile') renderProfile();
    };

    /* ═══ Render: Plans (Services) ═══ */
    function renderPlans() {
        var el = document.getElementById('plansList');
        if (!plans.length) {
            el.innerHTML = '<div class="empty"><div class="empty-icon">📦</div><div class="empty-title">پلنی موجود نیست</div><div class="empty-desc">در حال حاضر پلن فعالی وجود ندارد</div></div>';
            return;
        }
        el.innerHTML = plans.map(function (p) {
            var isUlt = p.is_ultimate;
            return '<div class="card">' +
                '<div class="plan-header">' +
                    '<div><div class="plan-name">' + esc(p.name) + '</div>' +
                    '<div class="plan-duration">' + p.days + ' روز</div></div>' +
                    (isUlt ? '<div class="plan-badge">نامحدود</div>' : '') +
                '</div>' +
                (isUlt ? '<div style="font-size:28px;font-weight:900;background:linear-gradient(135deg,#f59e0b,#ef4444);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:8px 0 4px;">نامحدود</div>' :
                    '<div class="plan-volume"><span class="plan-gb">' + p.gb + '</span><span class="plan-gb-unit">گیگابایت</span></div>') +
                '<div class="plan-footer">' +
                    '<div class="plan-price">' + fmtNum(p.price) + '<span class="plan-currency">' + esc(p.currency || 'تومان') + '</span></div>' +
                    '<button class="btn-buy" onclick="openPay(' + p.id + ')">خرید</button>' +
                '</div></div>';
        }).join('');
    }

    /* ═══ Render: Configs (My Services) ═══ */
    async function loadConfigs() {
        var d = await apiGet('/configs');
        configs = (d && d.configs) || [];
        renderConfigs();
    }

    function renderConfigs() {
        var el = document.getElementById('configsList');
        var badge = document.getElementById('svcCount');
        var active = configs.filter(function (c) { return c.is_active; });

        badge.textContent = active.length;
        badge.style.display = active.length ? '' : 'none';

        if (!active.length) {
            el.innerHTML = '<div class="empty"><div class="empty-icon">📡</div><div class="empty-title">سرویسی فعال نیست</div><div class="empty-desc">از تب سرویس‌ها یک پلن خریداری کنید</div>' +
                '<button class="btn-buy" onclick="goTab(\'services\')" style="padding:12px 32px;">مشاهده پلن‌ها</button></div>';
            return;
        }

        el.innerHTML = active.map(function (c) {
            var st = svcStatus(c);
            var svcLabel = c.config_name || ('سرویس #' + c.id);
            return '<div class="card" onclick="openDetail(' + c.id + ')" style="cursor:pointer;">' +
                '<div class="svc-header">' +
                    '<div class="svc-icon ' + st.cls + '">' +
                        '<svg width="20" height="20" fill="none" stroke="' + st.color + '" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z"/></svg>' +
                    '</div>' +
                    '<div style="flex:1;min-width:0;">' +
                        '<div class="svc-name">' + esc(c.plan_name || 'VPN') + '</div>' +
                        '<div class="svc-id">سرویس #' + c.id + '</div>' +
                    '</div>' +
                    '<span class="svc-status ' + st.cls + '">' + st.text + '</span>' +
                '</div>' +
                '<div class="svc-expiry">' +
                    '<svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/></svg>' +
                    'انقضا: ' + (c.expire_date ? c.expire_date.slice(0, 10) : 'نامحدود') +
                '</div>' +
                '<div class="svc-actions">' +
                    '<button class="svc-btn" onclick="event.stopPropagation();copyLink(\'' + esc(c.sub_link || '') + '\')">کپی لینک</button>' +
                    '<button class="svc-btn primary" onclick="event.stopPropagation();openDetail(' + c.id + ')">جزئیات</button>' +
                '</div></div>';
        }).join('');
    }

    function svcStatus(c) {
        if (!c.expire_date) return { cls: 'active', text: 'فعال', color: 'var(--green)' };
        var days = Math.ceil((new Date(c.expire_date) - new Date()) / 86400000);
        if (days <= 0) return { cls: 'expired', text: 'منقضی', color: 'var(--red)' };
        if (days <= 3) return { cls: 'expiring', text: days + ' روز', color: 'var(--yellow)' };
        return { cls: 'active', text: days + ' روز', color: 'var(--green)' };
    }

    /* ═══ Config Detail ═══ */
    window.openDetail = async function (id) {
        haptic();
        var sheet = document.getElementById('detSheet');
        var content = document.getElementById('detContent');
        content.innerHTML = '<div style="text-align:center;padding:40px;"><div class="ld-spinner" style="margin:0 auto;"></div></div>';
        sheet.classList.add('open');
        document.getElementById('detOverlay').classList.add('open');

        // Find config from already-loaded data (no extra API call needed)
        var cfg = configs.find(function (c) { return c.id === id; });
        if (!cfg) {
            content.innerHTML = '<div class="empty"><div class="empty-title">سرویس یافت نشد</div></div>';
            return;
        }

        var qr = genQR(cfg.sub_link || 'https://example.com', 200);

        // Try to get traffic data (best effort, won't break if API fails)
        var tr = null;
        try {
            var data = await apiGet('/config/' + id);
            if (data && data.traffic) tr = data.traffic;
        } catch (e) { /* ignore */ }

        // Traffic section
        var trHtml = '';
        if (tr && tr.total_bytes > 0) {
            var pct = Math.min(100, Math.round((tr.used_bytes / tr.total_bytes) * 100));
            var cls = pct > 90 ? 'danger' : pct > 70 ? 'warn' : 'safe';

            trHtml =
                '<div class="card" style="text-align:center;">' +
                    '<div style="font-size:13px;font-weight:700;margin-bottom:14px;">مصرف حجم</div>' +
                    '<div style="position:relative;width:120px;height:120px;margin:0 auto 16px;">' +
                        '<svg width="120" height="120" viewBox="0 0 120 120" style="transform:rotate(-90deg);">' +
                            '<circle cx="60" cy="60" r="52" fill="none" stroke="var(--border)" stroke-width="8"/>' +
                            '<circle cx="60" cy="60" r="52" fill="none" stroke="var(--' + (cls === 'danger' ? 'red' : cls === 'warn' ? 'yellow' : 'green') + ')" stroke-width="8" stroke-linecap="round" stroke-dasharray="' + (pct * 3.267) + ' 326.7"/>' +
                        '</svg>' +
                        '<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;">' +
                            '<div style="font-size:28px;font-weight:900;">' + pct + '%</div>' +
                            '<div style="font-size:10px;color:var(--text3);">مصرف شده</div>' +
                        '</div>' +
                    '</div>' +
                    '<div style="display:flex;justify-content:space-around;">' +
                        '<div><div style="font-size:18px;font-weight:800;color:var(--red);">' + tr.used_gb + '</div><div style="font-size:10px;color:var(--text3);">GB مصرف</div></div>' +
                        '<div><div style="font-size:18px;font-weight:800;color:var(--green);">' + tr.remaining_gb + '</div><div style="font-size:10px;color:var(--text3);">GB باقی‌مانده</div></div>' +
                        '<div><div style="font-size:18px;font-weight:800;">' + tr.total_gb + '</div><div style="font-size:10px;color:var(--text3);">GB کل</div></div>' +
                    '</div>' +
                '</div>' +
                '<div class="card">' +
                    '<div style="display:flex;gap:12px;">' +
                        '<div style="flex:1;background:var(--accent-bg);border-radius:12px;padding:12px;text-align:center;">' +
                            '<svg width="18" height="18" fill="none" stroke="var(--accent)" stroke-width="2" viewBox="0 0 24 24" style="margin:0 auto 4px;"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>' +
                            '<div style="font-size:16px;font-weight:800;">' + (tr.up_bytes ? (tr.up_bytes / 1073741824).toFixed(2) : '0') + '</div>' +
                            '<div style="font-size:10px;color:var(--text3);">GB آپلود</div>' +
                        '</div>' +
                        '<div style="flex:1;background:var(--green-bg);border-radius:12px;padding:12px;text-align:center;">' +
                            '<svg width="18" height="18" fill="none" stroke="var(--green)" stroke-width="2" viewBox="0 0 24 24" style="margin:0 auto 4px;"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>' +
                            '<div style="font-size:16px;font-weight:800;">' + (tr.down_bytes ? (tr.down_bytes / 1073741824).toFixed(2) : '0') + '</div>' +
                            '<div style="font-size:10px;color:var(--text3);">GB دانلود</div>' +
                        '</div>' +
                    '</div>' +
                '</div>';
        } else if (tr) {
            trHtml = '<div class="card" style="text-align:center;">' +
                '<div style="font-size:13px;font-weight:700;margin-bottom:10px;">مصرف حجم</div>' +
                '<div style="font-size:24px;font-weight:900;">نامحدود</div>' +
                '<div style="font-size:12px;color:var(--text3);">حجم نامحدود</div></div>';
        } else {
            trHtml = '<div class="card" style="text-align:center;">' +
                '<div style="font-size:13px;font-weight:700;margin-bottom:6px;">مصرف حجم</div>' +
                '<div style="font-size:12px;color:var(--text3);">اطلاعات حجم در دسترس نیست</div></div>';
        }

        content.innerHTML =
            '<div class="text-center" style="margin-bottom:16px;">' +
                '<img src="' + qr + '" style="width:200px;height:200px;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,.12);margin:0 auto;display:block;" alt="QR">' +
                '<p style="font-size:12px;color:var(--text3);margin-top:8px;">برای ایمپورت اسکن کنید</p>' +
            '</div>' +
            trHtml +
            '<div class="card">' +
                '<div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span style="font-size:12px;color:var(--text3);">وضعیت</span><span style="font-size:13px;font-weight:700;color:' + (cfg.is_active ? 'var(--green)' : 'var(--red)') + ';">' + (cfg.is_active ? 'فعال' : 'غیرفعال') + '</span></div>' +
                '<div style="display:flex;justify-content:space-between;margin-bottom:8px;"><span style="font-size:12px;color:var(--text3);">پلن</span><span style="font-size:13px;font-weight:600;">' + esc(cfg.plan_name || 'نامشخص') + '</span></div>' +
                '<div style="display:flex;justify-content:space-between;"><span style="font-size:12px;color:var(--text3);">تاریخ انقضا</span><span style="font-size:13px;font-weight:600;">' + (cfg.expire_date ? cfg.expire_date.slice(0, 10) : 'نامحدود') + '</span></div>' +
            '</div>' +
            '<div class="card">' +
                '<div style="font-size:12px;color:var(--text3);margin-bottom:6px;">لینک اشتراک</div>' +
                '<div style="background:var(--bg);border-radius:10px;padding:10px;font-size:11px;font-family:monospace;direction:ltr;text-align:left;word-break:break-all;user-select:all;line-height:1.6;">' + esc(cfg.sub_link || 'ناموجود') + '</div>' +
            '</div>' +
            '<div style="display:flex;gap:8px;">' +
                '<button class="btn-buy" style="flex:1;padding:12px;" onclick="copyLink(\'' + esc(cfg.sub_link || '') + '\')">' +
                    '<svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" style="display:inline;vertical-align:middle;margin-left:4px;"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/></svg>' +
                    'کپی لینک' +
                '</button>' +
                '<button class="svc-btn" style="flex:0;padding:12px 20px;" onclick="closeSheet(\'det\')">بستن</button>' +
            '</div>';
    };

    /* ═══ Profile ═══ */
    function renderProfile() {
        var u = getUser();
        var bal = wallet ? wallet.balance : 0;
        var curr = wallet ? wallet.currency : 'تومان';
        var refCount = invite ? (invite.count || 0) : 0;
        var refLink = invite ? (invite.link || '') : '';
        var activeSvc = configs.filter(function (c) { return c.is_active; }).length;

        var html = '<div class="profile-header">' +
            '<div class="profile-avatar">' + (u.photo_url ? '<img src="' + u.photo_url + '">' : initials(u)) + '</div>' +
            '<div class="profile-name">' + esc(displayName(u)) + '</div>' +
            '<div class="profile-username">' + (u.username ? '@' + esc(u.username) : 'شناسه: ' + u.id) + '</div></div>' +

            '<div class="stats-grid">' +
                '<div class="stat-card"><div class="stat-icon" style="background:var(--green-bg);"><svg width="16" height="16" fill="none" stroke="var(--green)" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a2.25 2.25 0 00-2.25-2.25H15a3 3 0 11-6 0H5.25A2.25 2.25 0 003 12m18 0v6a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 18v-6m18 0V9M3 12V9m18 0a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 9m18 0V6a2.25 2.25 0 00-2.25-2.25H5.25A2.25 2.25 0 003 6v3"/></svg></div>' +
                '<div class="stat-label">موجودی کیف پول</div><div class="stat-value">' + fmtNum(bal) + '</div><div class="stat-sub">' + esc(curr) + '</div></div>' +
                '<div class="stat-card"><div class="stat-icon" style="background:var(--accent-bg);"><svg width="16" height="16" fill="none" stroke="var(--accent)" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg></div>' +
                '<div class="stat-label">سرویس‌های فعال</div><div class="stat-value">' + activeSvc + '</div><div class="stat-sub">اشتراک</div></div>' +
                '<div class="stat-card"><div class="stat-icon" style="background:var(--yellow-bg);"><svg width="16" height="16" fill="none" stroke="var(--yellow)" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/></svg></div>' +
                '<div class="stat-label">زیرمجموعه‌ها</div><div class="stat-value">' + refCount + '</div><div class="stat-sub">نفر</div></div>' +
                '<div class="stat-card"><div class="stat-icon" style="background:var(--red-bg);"><svg width="16" height="16" fill="none" stroke="var(--red)" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"/></svg></div>' +
                '<div class="stat-label">تاریخ عضویت</div><div class="stat-value" style="font-size:14px;">عضو</div><div class="stat-sub">فعال</div></div>' +
            '</div>';

        if (refLink) {
            html += '<div class="invite-card">' +
                '<div class="invite-title">دعوت از دوستان</div>' +
                '<div class="invite-desc">لینک دعوت خود را با دوستان به اشتراک بگذارید</div>' +
                '<div class="invite-link"><input type="text" value="' + esc(refLink) + '" readonly id="inviteInput">' +
                '<button onclick="copyInvite()">کپی</button></div>' +
                '<div class="invite-stats"><div><div class="invite-stat-val">' + refCount + '</div><div class="invite-stat-label">دعوت‌شده</div></div>' +
                '<div><div class="invite-stat-val">' + fmtNum(invite ? invite.reward : 0) + '</div><div class="invite-stat-label">پاداش هر نفر</div></div></div></div>';
        }

        document.getElementById('profileContent').innerHTML = html;
    }

    /* ═══ Payment ═══ */
    window.openPay = function (planId) {
        haptic();
        selectedPlan = plans.find(function (p) { return p.id === planId; });
        if (!selectedPlan) return;
        document.getElementById('payPlanInfo').innerHTML = esc(selectedPlan.name) + ' · ' + (selectedPlan.is_ultimate ? 'نامحدود' : selectedPlan.gb + ' گیگ') + ' · ' + selectedPlan.days + ' روز';
        document.getElementById('payBalText').textContent = 'موجودی: ' + fmtNum(wallet ? wallet.balance : 0) + ' ' + (wallet ? wallet.currency : 'تومان');
        document.getElementById('paySheet').classList.add('open');
        document.getElementById('payOverlay').classList.add('open');
    };

    window.closeSheet = function (name) {
        haptic();
        var map = { pay: ['paySheet', 'payOverlay'], det: ['detSheet', 'detOverlay'] };
        var ids = map[name];
        if (ids) {
            document.getElementById(ids[0]).classList.remove('open');
            document.getElementById(ids[1]).classList.remove('open');
        }
    };

    window.doPay = async function (method) {
        if (!selectedPlan) return;
        haptic('medium');
        closeSheet('pay');

        if (method === 'wallet') {
            var bal = wallet ? wallet.balance : 0;
            if (bal < selectedPlan.price) {
                toast('موجودی کافی نیست. لطفاً ابتدا کیف پول خود را شارژ کنید.');
                return;
            }

            // Process wallet payment directly
            toast('در حال پردازش...');
            var cfgName = document.getElementById('configNameInput') ? document.getElementById('configNameInput').value.trim() : '';
            var result = await apiPost('/buy', { plan_id: selectedPlan.id, method: 'wallet', config_name: cfgName });
            if (result && result.success) {
                toast('سرویس با موفقیت ساخته شد!');
                if (wallet) wallet.balance -= selectedPlan.price;
                await loadConfigs();
                goTab('my-services');
            } else {
                toast((result && result.message) || 'خطا در خرید');
            }
            return;
        }

        if (method === 'c2c') {
            // Show card details sheet
            showC2CSheet();
        }
    };

    // ─── C2C Payment Sheet ───
    var cardInfo = null;

    async function showC2CSheet() {
        var cfgName = document.getElementById('configNameInput') ? document.getElementById('configNameInput').value.trim() : '';
        // Fetch card info from API (fallback to hardcoded if API fails)
        cardInfo = await apiGet('/card-info');
        var cardNum = (cardInfo && cardInfo.card_number) || '6219861938689725';
        var cardOwner = (cardInfo && cardInfo.card_owner) || 'اسکندر داروند';

        var sheet = document.getElementById('detSheet');
        var content = document.getElementById('detContent');
        var price = selectedPlan ? fmtNum(selectedPlan.price) : '0';
        var currency = (wallet && wallet.currency) || 'تومان';

        content.innerHTML =
            '<h3 style="font-size:18px;font-weight:800;margin-bottom:4px;">کارت به کارت</h3>' +
            '<p style="font-size:13px;color:var(--text3);margin-bottom:16px;">مبلغ را به کارت زیر واریز کنید</p>' +

            // Plan summary
            '<div class="card" style="text-align:center;margin-bottom:16px;">' +
                '<div style="font-size:13px;color:var(--text3);">مبلغ قابل پرداخت</div>' +
                '<div style="font-size:28px;font-weight:900;color:var(--accent);margin:4px 0;">' + price + '</div>' +
                '<div style="font-size:12px;color:var(--text3);">' + currency + ' · ' + esc(selectedPlan.name) + '</div>' +
            '</div>' +

            // Card number
            '<div class="card">' +
                '<div style="font-size:12px;color:var(--text3);margin-bottom:6px;">شماره کارت</div>' +
                '<div style="display:flex;align-items:center;gap:8px;">' +
                    '<div style="flex:1;background:var(--bg);border-radius:10px;padding:12px;font-size:16px;font-weight:700;font-family:monospace;direction:ltr;text-align:center;letter-spacing:1px;">' + esc(cardNum) + '</div>' +
                    '<button onclick="copyText(\'' + esc(cardNum) + '\')" style="background:var(--accent);color:#fff;border:none;padding:10px;border-radius:10px;cursor:pointer;flex-shrink:0;">' +
                        '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/></svg>' +
                    '</button>' +
                '</div>' +
                '<div style="font-size:11px;color:var(--text3);margin-top:6px;">صاحب کارت: ' + esc(cardOwner) + '</div>' +
            '</div>' +

            // Amount copy
            '<div class="card">' +
                '<div style="font-size:12px;color:var(--text3);margin-bottom:6px;">مبلغ دقیق</div>' +
                '<div style="display:flex;align-items:center;gap:8px;">' +
                    '<div style="flex:1;background:var(--bg);border-radius:10px;padding:12px;font-size:18px;font-weight:800;text-align:center;">' + price + ' ' + esc(currency) + '</div>' +
                    '<button onclick="copyText(\'' + price + ' ' + esc(currency) + '\')" style="background:var(--accent);color:#fff;border:none;padding:10px;border-radius:10px;cursor:pointer;flex-shrink:0;">' +
                        '<svg width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184"/></svg>' +
                    '</button>' +
                '</div>' +
            '</div>' +

            // Instructions
            '<div class="card" style="background:var(--yellow-bg);border-color:transparent;">' +
                '<div style="font-size:13px;font-weight:700;margin-bottom:6px;">راهنمای پرداخت</div>' +
                '<ol style="font-size:12px;color:var(--text2);padding-right:16px;line-height:2;">' +
                    '<li>مبلغ دقیق را به کارت بالا واریز کنید</li>' +
                    '<li>رسید پرداخت را ذخیره کنید</li>' +
                    '<li>روی دکمه زیر کلیک کنید تا رسید را در ربات آپلود کنید</li>' +
                '</ol>' +
            '</div>' +

            // Action buttons
            '<div style="display:flex;gap:8px;margin-top:4px;">' +
                '<button class="btn-buy" style="flex:1;padding:14px;font-size:15px;" onclick="goToBotForReceipt()">' +
                    'آپلود رسید در ربات' +
                '</button>' +
            '</div>' +
            '<button onclick="closeSheet(\'det\')" style="width:100%;margin-top:8px;padding:12px;background:none;border:none;color:var(--text3);font-size:14px;cursor:pointer;font-family:inherit;">بازگشت</button>';

        sheet.classList.add('open');
        document.getElementById('detOverlay').classList.add('open');
    }

    window.goToBotForReceipt = function () {
        haptic('success');
        closeSheet('det');
        var planId = selectedPlan ? selectedPlan.id : '';
        var cfgName = document.getElementById('configNameInput') ? document.getElementById('configNameInput').value.trim() : '';
        var botLink = 'https://t.me/NigVpnBot?start=c2c_' + planId + (cfgName ? '_' + encodeURIComponent(cfgName) : '');
        try {
            tg.openTelegramLink(botLink);
        } catch(e) {
            tg.close();
        }
    };

    window.generateRandomName = function () {
        var words = ['سریع', 'آزاد', 'امن', 'پرسرعت', 'نامحدود', 'پایدار', 'برتر', 'ویژه', 'فوق‌سریع', 'پرواز'];
        var name = words[Math.floor(Math.random() * words.length)] + '-' + Math.floor(Math.random() * 90 + 10);
        document.getElementById('configNameInput').value = name;
        haptic();
    };

    window.copyText = function (text) {
        navigator.clipboard.writeText(text).then(function () {
            toast('کپی شد');
            haptic('success');
        }).catch(function () {
            toast('خطا در کپی');
        });
    };

    /* ═══ QR Code (client-side) ═══ */
    function genQR(text, size) {
        try {
            // Use qrcode-generator library for proper scannable QR codes
            var typeNumber = 0; // auto-detect
            var errorCorrectionLevel = 'M';
            var qr = qrcode(typeNumber, errorCorrectionLevel);
            qr.addData(text);
            qr.make();

            var modules = qr.getModuleCount();
            var canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;
            var ctx = canvas.getContext('2d');

            // Background
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, size, size);

            // Get accent color
            var cs = getComputedStyle(document.documentElement);
            var fillColor = cs.getPropertyValue('--accent').trim() || '#4f46e5';
            ctx.fillStyle = fillColor;

            var cell = size / modules;
            var padding = cell * 0.5;

            for (var r = 0; r < modules; r++) {
                for (var c = 0; c < modules; c++) {
                    if (qr.isDark(r, c)) {
                        var x = c * cell + padding;
                        var y = r * cell + padding;
                        var radius = cell * 0.2;
                        ctx.beginPath();
                        if (ctx.roundRect) {
                            ctx.roundRect(x, y, cell - 1, cell - 1, radius);
                        } else {
                            ctx.rect(x, y, cell - 1, cell - 1);
                        }
                        ctx.fill();
                    }
                }
            }
            return canvas.toDataURL('image/png');
        } catch (e) {
            // Fallback: return empty white image
            var canvas = document.createElement('canvas');
            canvas.width = size;
            canvas.height = size;
            var ctx = canvas.getContext('2d');
            ctx.fillStyle = '#ffffff';
            ctx.fillRect(0, 0, size, size);
            return canvas.toDataURL('image/png');
        }
    }

    /* ═══ Helpers ═══ */
    function fmtNum(n) { return new Intl.NumberFormat('fa-IR').format(Math.round(n || 0)); }
    function esc(s) { var d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }

    function toast(msg) {
        var el = document.getElementById('toast');
        el.textContent = msg;
        el.classList.add('show');
        setTimeout(function () { el.classList.remove('show'); }, 2500);
    }

    window.copyLink = function (link) {
        if (!link) return;
        navigator.clipboard.writeText(link).then(function () { toast('لینک کپی شد'); haptic('success'); }).catch(function () { toast('خطا در کپی'); });
    };

    window.copyInvite = function () {
        var inp = document.getElementById('inviteInput');
        if (inp) navigator.clipboard.writeText(inp.value).then(function () { toast('لینک دعوت کپی شد'); haptic('success'); });
    };

    /* ═══ Data Loading ═══ */
    async function loadAll() {
        var results = await Promise.all([apiGet('/plans'), apiGet('/wallet'), apiGet('/invite')]);
        plans = (results[0] && results[0].plans) || [];
        wallet = results[1];
        invite = results[2];
        renderPlans();
    }

    /* ═══ Init ═══ */
    async function init() {
        try {
            initTG();

            // Hide loader, show app
            var loader = document.getElementById('loader');
            var app = document.getElementById('app');
            var nav = document.getElementById('bnav');
            if (loader) loader.classList.add('hide');
            if (app) app.classList.add('show');
            if (nav) nav.style.display = '';

            // Activate first tab
            document.getElementById('pg-services').classList.add('active');

            // Load data
            await loadAll();

            if (tg) tg.ready();
        } catch (e) {
            console.error('Init error:', e);
            var loader = document.getElementById('loader');
            if (loader) loader.innerHTML = '<div style="text-align:center;padding:20px;"><p style="color:var(--red);font-size:14px;">خطا در بارگذاری</p><p style="color:var(--text3);font-size:12px;margin-top:8px;">' + e.message + '</p></div>';
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
