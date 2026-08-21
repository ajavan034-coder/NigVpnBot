"""
Telegram Mini Web App - Server-side API
Flask blueprint that serves the webapp and API endpoints.
Uses web_db (synchronous) for database access.
"""

import hashlib
import hmac
import json
import time
import os
from functools import wraps
from urllib.parse import unquote

from flask import Blueprint, request, jsonify, send_from_directory, current_app

import web_db

webapp_bp = Blueprint(
    'webapp',
    __name__,
    static_folder='webapp',
    static_url_path='/webapp',
)


# ── Telegram initData verification ──────────────────────────────
def _verify_init_data(init_data: str, bot_token: str) -> dict | None:
    try:
        parsed = dict(
            item.split('=', 1)
            for item in unquote(init_data).split('&')
            if '=' in item
        )
    except Exception:
        return None

    auth_date = int(parsed.get('auth_date', 0))
    if time.time() - auth_date > 86400:
        return None

    check_hash = parsed.pop('hash', None)
    if not check_hash:
        return None

    data_check = '\n'.join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

    if computed != check_hash:
        return None

    return json.loads(parsed.get('user', '{}'))


def _get_user_id() -> int | None:
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    token = auth[7:]

    bot_token = current_app.config.get('BOT_TOKEN', '')
    if bot_token:
        user = _verify_init_data(token, bot_token)
        if user:
            return user.get('id')
        # If initData verification failed, check if it's a numeric ID (dev/test mode)
        try:
            return int(token)
        except ValueError:
            return None

    # Dev mode: trust numeric token directly
    try:
        return int(token)
    except ValueError:
        return None


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = _get_user_id()
        if not user_id:
            return jsonify({'error': 'unauthorized'}), 401
        request.user_id = user_id
        return f(*args, **kwargs)
    return decorated


# ── Serve the webapp ────────────────────────────────────────────
@webapp_bp.route('/app')
@webapp_bp.route('/app/')
@webapp_bp.route('/app/<path:filename>')
def serve_webapp(filename='index.html'):
    return send_from_directory('webapp', filename)


# ── API Endpoints ───────────────────────────────────────────────
@webapp_bp.route('/api/wallet')
@require_auth
def api_wallet():
    user = web_db.get_user(request.user_id)
    currency = web_db.get_setting('currency_symbol') or 'Toman'
    return jsonify({
        'balance': int(user['balance']) if user else 0,
        'currency': currency,
    })


@webapp_bp.route('/api/configs')
@require_auth
def api_configs():
    configs = web_db.get_user_configs(request.user_id)
    result = []
    for c in (configs or []):
        plan_name = 'Free Test' if not c.get('plan_id') else ''
        if c.get('plan_id'):
            plan = web_db.get_plan(c['plan_id'])
            plan_name = plan['name'] if plan else 'Unknown'
        result.append({
            'id': c['id'],
            'plan_id': c.get('plan_id'),
            'plan_name': plan_name,
            'config_name': c.get('config_name') or '',
            'sub_link': c['sub_link'],
            'expire_date': c['expire_date'],
            'is_active': bool(c.get('is_active', True)),
        })
    return jsonify({'configs': result})


@webapp_bp.route('/api/config/<int:config_id>')
@require_auth
def api_config_detail(config_id):
    import sqlite3
    from config import DB_PATH

    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT * FROM configs WHERE id = ?', (config_id,)).fetchone()
    conn.close()

    if not row or row['user_id'] != request.user_id:
        return jsonify({'error': 'not found'}), 404

    cfg = dict(row)

    # Get traffic info from panel (fresh PanelAPI per request to avoid event loop conflicts)
    traffic = None
    try:
        import asyncio
        from api import PanelAPI
        import database as db

        async def _fetch():
            panel_id = cfg.get('panel_id')
            if panel_id:
                p = await db.get_panel(panel_id)
                if not p:
                    return None
                api = PanelAPI(panel_url=p['url'], panel_user=p['username'], panel_pass=p['password'])
            else:
                api = PanelAPI()
            try:
                return await api.get_client_traffic(cfg['email'])
            finally:
                await api.close()

        traffic = asyncio.run(_fetch())
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Traffic fetch failed for {cfg.get('email')}: {e}")

    plan_name = 'Free Test'
    if cfg.get('plan_id'):
        plan = web_db.get_plan(cfg['plan_id'])
        plan_name = plan['name'] if plan else 'Unknown'

    return jsonify({
        'config': {
            'id': cfg['id'],
            'plan_name': plan_name,
            'sub_link': cfg['sub_link'],
            'expire_date': cfg['expire_date'],
            'is_active': bool(cfg.get('is_active', True)),
        },
        'traffic': traffic,
    })


@webapp_bp.route('/api/plans')
@require_auth
def api_plans():
    plans = web_db.get_all_plans()
    currency = web_db.get_setting('currency_symbol') or 'Toman'
    result = []
    for p in (plans or []):
        if not p.get('is_active', True):
            continue
        result.append({
            'id': p['id'],
            'name': p['name'],
            'gb': p['gb'],
            'days': p['days'],
            'price': p['price'],
            'is_ultimate': bool(p.get('is_ultimate', False)),
            'currency': currency,
        })
    return jsonify({'plans': result})


@webapp_bp.route('/api/invite')
@require_auth
def api_invite():
    enabled = web_db.get_setting('invite_enabled') or '0'
    if enabled != '1':
        return jsonify({'enabled': False})

    # Get invite stats using synchronous query
    import sqlite3
    from config import DB_PATH

    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    row = conn.execute('SELECT invite_code FROM users WHERE id = ?', (request.user_id,)).fetchone()
    code = row['invite_code'] if row else None
    cnt = conn.execute('SELECT COUNT(*) as cnt FROM users WHERE referred_by = ?', (request.user_id,)).fetchone()['cnt']
    conn.close()

    reward = int(web_db.get_setting('invite_reward_amount') or '0')

    # Get bot username from token
    bot_token = current_app.config.get('BOT_TOKEN', '')
    bot_username = 'yourbot'
    try:
        import requests as _req
        resp = _req.get(f'https://api.telegram.org/bot{bot_token}/getMe', timeout=5)
        if resp.status_code == 200:
            bot_username = resp.json().get('result', {}).get('username', bot_username)
    except Exception:
        pass

    return jsonify({
        'enabled': True,
        'code': code or '',
        'link': f"https://t.me/{bot_username}?start={code}" if code else '',
        'count': cnt,
        'reward': reward,
    })


@webapp_bp.route('/api/topup', methods=['POST'])
@require_auth
def api_topup():
    data = request.get_json(silent=True) or {}
    amount = int(data.get('amount', 0))
    min_topup = int(web_db.get_setting('min_topup') or '50000')

    if amount < min_topup:
        return jsonify({'success': False, 'message': f'Minimum top up is {min_topup:,} Toman'})

    # Create pending receipt
    import sqlite3
    from config import DB_PATH
    from datetime import datetime

    conn = sqlite3.connect(DB_PATH, timeout=5)
    cursor = conn.execute(
        'INSERT INTO receipts (user_id, plan_id, amount, photo_file_id, created_at) VALUES (?, 0, ?, ?, ?)',
        (request.user_id, amount, 'webapp_topup', datetime.utcnow().isoformat()),
    )
    receipt_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({'success': True, 'receipt_id': receipt_id})


@webapp_bp.route('/api/card-info')
@require_auth
def api_card_info():
    card_number = web_db.get_setting('card_number') or '1234-5678-9012-3456'
    card_owner = web_db.get_setting('card_owner') or 'Card Owner'
    return jsonify({'card_number': card_number, 'card_owner': card_owner})


@webapp_bp.route('/api/buy', methods=['POST'])
@require_auth
def api_buy():
    data = request.get_json(silent=True) or {}
    plan_id = int(data.get('plan_id', 0))
    method = data.get('method', 'wallet')
    config_name = data.get('config_name', '')

    plan = web_db.get_plan(plan_id)
    if not plan or not plan.get('is_active', True):
        return jsonify({'success': False, 'message': 'Plan not found or inactive'})

    user = web_db.get_user(request.user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found'})

    currency = web_db.get_setting('currency_symbol') or 'Toman'

    if method == 'wallet':
        if user['balance'] < plan['price']:
            return jsonify({
                'success': False,
                'message': f'Insufficient balance. Need {int(plan["price"]):,} {currency}, have {int(user["balance"]):,}',
            })

        # Deduct balance
        web_db.update_balance(request.user_id, -plan['price'])

        # Create config on panel
        import time as _time
        username = user.get('username') or str(request.user_id)
        email = f"webapp_{request.user_id}_{username}_{int(_time.time())}"

        try:
            from api import PanelAPI
            import asyncio
            import database as db

            plan_inbound_ids = None
            if plan.get('inbound_ids'):
                plan_inbound_ids = [int(x.strip()) for x in plan['inbound_ids'].split(',') if x.strip().isdigit()]

            async def _create_config():
                panel_id = plan.get('panel_id')
                if panel_id:
                    panel = await db.get_panel(panel_id)
                    if not panel:
                        return None
                    api = PanelAPI(
                        panel_url=panel['url'],
                        panel_user=panel['username'],
                        panel_pass=panel['password'],
                    )
                else:
                    from api import panel_api
                    panel_api.reload_config()
                    api = panel_api
                try:
                    return await api.create_config(email, days=plan['days'], total_gb=plan['gb'], inbound_ids=plan_inbound_ids)
                finally:
                    if panel_id:
                        await api.close()

            result = asyncio.run(_create_config())

            if not result:
                # Refund on failure
                web_db.update_balance(request.user_id, plan['price'])
                return jsonify({'success': False, 'message': 'Failed to create config on panel'})

            # Save config to DB
            import sqlite3
            from config import DB_PATH
            from datetime import datetime, timedelta

            conn = sqlite3.connect(DB_PATH, timeout=5)
            conn.execute(
                'INSERT INTO configs (user_id, plan_id, sub_link, uuid, email, expire_date, panel_id, config_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                (request.user_id, plan_id, result['sub_link'], result['uuid'], result['email'], result['expire_date'], panel_id, config_name),
            )
            conn.commit()
            conn.close()

            return jsonify({
                'success': True,
                'config': {
                    'sub_link': result['sub_link'],
                    'expire_date': result['expire_date'],
                },
            })
        except Exception as e:
            # Refund on exception
            web_db.update_balance(request.user_id, plan['price'])
            return jsonify({'success': False, 'message': f'Error: {str(e)}'})

    elif method == 'c2c':
        # Create pending receipt for card-to-card payment
        import sqlite3
        from config import DB_PATH
        from datetime import datetime

        conn = sqlite3.connect(DB_PATH, timeout=5)
        cursor = conn.execute(
            'INSERT INTO receipts (user_id, plan_id, amount, photo_file_id, created_at, config_name) VALUES (?, ?, ?, ?, ?, ?)',
            (request.user_id, plan_id, plan['price'], 'webapp_c2c', datetime.utcnow().isoformat(), config_name),
        )
        receipt_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'receipt_id': receipt_id,
            'message': 'Receipt uploaded. Waiting for admin approval.',
        })

    return jsonify({'success': False, 'message': 'Invalid payment method'})


# ── Grouped endpoints for section/panel views ──────────────────
@webapp_bp.route('/api/sections')
@require_auth
def api_sections():
    """Return plan sections with their plans grouped."""
    sections = web_db.get_plan_sections()
    all_plans = web_db.get_all_plans()
    currency = web_db.get_setting('currency_symbol') or 'Toman'

    # Group plans by section_id
    section_plans = {}
    for p in (all_plans or []):
        if not p.get('is_active', True):
            continue
        sid = p.get('section_id')
        if sid not in section_plans:
            section_plans[sid] = []
        section_plans[sid].append({
            'id': p['id'],
            'name': p['name'],
            'gb': p['gb'],
            'days': p['days'],
            'price': p['price'],
            'collaborator_price': p.get('collaborator_price'),
            'is_ultimate': bool(p.get('is_ultimate', False)),
            'currency': currency,
        })

    result = []
    for s in (sections or []):
        sid = s['id']
        plans = section_plans.get(sid, [])
        if not plans:
            continue
        result.append({
            'id': sid,
            'name': s['name'],
            'plans': plans,
        })

    return jsonify({'sections': result})


@webapp_bp.route('/api/configs-grouped')
@require_auth
def api_configs_grouped():
    """Return user configs grouped by panel."""
    import sqlite3
    from config import DB_PATH

    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        'SELECT c.*, p.name as plan_name FROM configs c '
        'LEFT JOIN plans p ON c.plan_id = p.id '
        'WHERE c.user_id = ? ORDER BY c.panel_id, c.expire_date DESC',
        (request.user_id,)
    ).fetchall()

    panels = {}
    for pr in conn.execute('SELECT id, name, emoji_id FROM panels ORDER BY id').fetchall():
        prd = dict(pr); panels[prd['id']] = {'name': prd['name'], 'emoji_id': prd.get('emoji_id', '')}
    conn.close()

    # Group by panel_id
    grouped = {}
    for r in rows:
        cfg = dict(r)
        pid = cfg.get('panel_id')
        if pid not in grouped:
            panel_info = panels.get(pid, {'name': 'سرویس', 'emoji_id': ''}) if pid else {'name': 'سایر', 'emoji_id': ''}
            grouped[pid] = {
                'panel_id': pid,
                'panel_name': panel_info['name'],
                'emoji_id': panel_info.get('emoji_id', ''),
                'configs': [],
            }
        grouped[pid]['configs'].append({
            'id': cfg['id'],
            'plan_id': cfg.get('plan_id'),
            'plan_name': cfg.get('plan_name') or 'Free Test',
            'config_name': cfg.get('config_name') or '',
            'sub_link': cfg.get('sub_link') or '',
            'expire_date': cfg.get('expire_date') or '',
            'is_active': bool(cfg.get('is_active', True)),
        })

    return jsonify({'groups': list(grouped.values())})

