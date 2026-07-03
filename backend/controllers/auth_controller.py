"""
Auth controller — 帳號密碼登入 / 註冊 / Token 驗證

Token 為 in-memory 儲存（重啟後需重新登入），對應 user_id，TTL 7 天。
"""
import re
import secrets
import time
from functools import wraps
from flask import Blueprint, request, jsonify, g

from models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# token → {'user_id': str, 'username': str, 'is_admin': bool, 'expires_at': float}
_valid_tokens: dict[str, dict] = {}
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 天

USERNAME_RE = re.compile(r'^[\w一-鿿.-]{2,32}$')


def _issue_token(user: User) -> str:
    token = secrets.token_urlsafe(32)
    _valid_tokens[token] = {
        'user_id': user.id,
        'username': user.username,
        'is_admin': bool(user.is_admin),
        'expires_at': time.time() + TOKEN_TTL_SECONDS,
    }
    return token


def _get_request_token() -> str:
    return (
        request.headers.get('X-Auth-Token') or
        request.headers.get('Authorization', '').removeprefix('Bearer ').strip() or
        request.args.get('token', '')
    )


def _resolve_token(token: str):
    if not token:
        return None
    # 服務對服務的固定 admin token（供後台系統狀態頁等內部整合使用）
    import os
    svc = os.getenv('ADMIN_API_TOKEN', '')
    if svc and secrets.compare_digest(token, svc):
        admin = User.query.filter_by(is_admin=True).first()
        if admin:
            return {'user_id': admin.id, 'username': admin.username,
                    'is_admin': True, 'expires_at': time.time() + 60}
    info = _valid_tokens.get(token)
    if info is None:
        return None
    if time.time() > info['expires_at']:
        del _valid_tokens[token]
        return None
    return info


def require_auth(f):
    """Decorator — 需帶 X-Auth-Token header 或 query ?token=，驗證後設定 g.user_id"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        info = _resolve_token(_get_request_token())
        if info is None:
            return jsonify({'error': '未授權，請先登入', 'code': 'UNAUTHORIZED'}), 401
        g.user_id = info['user_id']
        g.username = info['username']
        g.is_admin = info['is_admin']
        return f(*args, **kwargs)
    return wrapper


def authenticate_request():
    """供 app.before_request 使用：驗證通過回傳 None，否則回傳 401 response"""
    info = _resolve_token(_get_request_token())
    if info is None:
        return jsonify({'error': '未授權，請先登入', 'code': 'UNAUTHORIZED'}), 401
    g.user_id = info['user_id']
    g.username = info['username']
    g.is_admin = info['is_admin']
    return None


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.post('/register')
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not USERNAME_RE.match(username):
        return jsonify({'success': False, 'error': '帳號需為 2~32 字（中英文、數字、._-）'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'error': '密碼至少 6 個字元'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': '此帳號已存在'}), 409

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    token = _issue_token(user)
    return jsonify({'success': True, 'token': token, 'username': user.username,
                    'is_admin': user.is_admin, 'ttl': TOKEN_TTL_SECONDS})


@auth_bp.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    user = User.query.filter_by(username=username).first()
    if user is None or not user.check_password(password):
        return jsonify({'success': False, 'error': '帳號或密碼錯誤'}), 401

    token = _issue_token(user)
    return jsonify({'success': True, 'token': token, 'username': user.username,
                    'is_admin': user.is_admin, 'ttl': TOKEN_TTL_SECONDS})


@auth_bp.post('/logout')
def logout():
    token = _get_request_token()
    if token and token in _valid_tokens:
        del _valid_tokens[token]
    return jsonify({'success': True})


@auth_bp.post('/change-password')
def change_password():
    info = _resolve_token(_get_request_token())
    if info is None:
        return jsonify({'success': False, 'error': '未授權'}), 401
    data = request.get_json(silent=True) or {}
    old_pw = data.get('old_password') or ''
    new_pw = data.get('new_password') or ''
    if len(new_pw) < 6:
        return jsonify({'success': False, 'error': '新密碼至少 6 個字元'}), 400
    user = User.query.get(info['user_id'])
    if user is None or not user.check_password(old_pw):
        return jsonify({'success': False, 'error': '舊密碼錯誤'}), 401
    user.set_password(new_pw)
    db.session.commit()
    return jsonify({'success': True})


@auth_bp.get('/status')
def status():
    """前端啟動時用來確認 token 是否還有效"""
    info = _resolve_token(_get_request_token())
    if info is None:
        return jsonify({'auth_required': True, 'valid': False})
    return jsonify({'auth_required': True, 'valid': True,
                    'username': info['username'], 'is_admin': info['is_admin']})


# ── Admin：使用者管理（後台系統狀態頁整合用） ─────────────────────────────────

@auth_bp.get('/users')
def list_users():
    info = _resolve_token(_get_request_token())
    if info is None or not info['is_admin']:
        return jsonify({'success': False, 'error': '僅管理員可用'}), 403
    from models import Project
    from sqlalchemy import func
    counts = dict(
        db.session.query(Project.user_id, func.count(Project.id))
        .group_by(Project.user_id).all()
    )
    users = User.query.order_by(User.created_at).all()
    return jsonify({'success': True, 'users': [
        {**u.to_dict(), 'project_count': counts.get(u.id, 0)} for u in users
    ]})


@auth_bp.put('/users/<username>/password')
def admin_set_password(username):
    info = _resolve_token(_get_request_token())
    if info is None or not info['is_admin']:
        return jsonify({'success': False, 'error': '僅管理員可用'}), 403
    data = request.get_json(silent=True) or {}
    new_pw = data.get('new_password') or ''
    if len(new_pw) < 3:
        return jsonify({'success': False, 'error': '密碼至少 3 個字元'}), 400
    user = User.query.filter_by(username=username).first()
    if user is None:
        return jsonify({'success': False, 'error': '帳號不存在'}), 404
    user.set_password(new_pw)
    db.session.commit()
    return jsonify({'success': True, 'username': username})
