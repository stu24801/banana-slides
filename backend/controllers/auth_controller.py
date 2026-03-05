"""
Auth controller — 密碼登入 / Token 驗證
"""
import os
import secrets
import hashlib
import time
from functools import wraps
from flask import Blueprint, request, jsonify, current_app

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# ── In-memory token store (process-level cache) ───────────────────────────────
# token → expires_at (unix timestamp)
_valid_tokens: dict[str, float] = {}
TOKEN_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 天


def _get_password() -> str:
    return os.getenv('SITE_PASSWORD', '')


def _issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _valid_tokens[token] = time.time() + TOKEN_TTL_SECONDS
    return token


def _is_valid_token(token: str) -> bool:
    if not token:
        return False
    expires_at = _valid_tokens.get(token)
    if expires_at is None:
        return False
    if time.time() > expires_at:
        del _valid_tokens[token]
        return False
    return True


def require_auth(f):
    """Decorator — 所有 API 需帶 X-Auth-Token header 或 query ?token="""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # 若未設定密碼，直接放行（向下相容）
        if not _get_password():
            return f(*args, **kwargs)
        token = (
            request.headers.get('X-Auth-Token') or
            request.headers.get('Authorization', '').removeprefix('Bearer ').strip() or
            request.args.get('token', '')
        )
        if not _is_valid_token(token):
            return jsonify({'error': '未授權，請先登入', 'code': 'UNAUTHORIZED'}), 401
        return f(*args, **kwargs)
    return wrapper


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.post('/login')
def login():
    data = request.get_json(silent=True) or {}
    password = data.get('password', '')
    site_password = _get_password()

    if not site_password:
        # 未設定密碼時直接回傳成功
        return jsonify({'success': True, 'token': '', 'message': '無需密碼'})

    # 使用 constant-time 比較防止 timing attack
    if not secrets.compare_digest(password, site_password):
        return jsonify({'success': False, 'error': '密碼錯誤'}), 401

    token = _issue_token()
    return jsonify({'success': True, 'token': token, 'ttl': TOKEN_TTL_SECONDS})


@auth_bp.post('/logout')
def logout():
    token = (
        request.headers.get('X-Auth-Token') or
        request.headers.get('Authorization', '').removeprefix('Bearer ').strip()
    )
    if token and token in _valid_tokens:
        del _valid_tokens[token]
    return jsonify({'success': True})


@auth_bp.get('/status')
def status():
    """前端啟動時用來確認 token 是否還有效"""
    site_password = _get_password()
    if not site_password:
        return jsonify({'auth_required': False, 'valid': True})
    token = (
        request.headers.get('X-Auth-Token') or
        request.headers.get('Authorization', '').removeprefix('Bearer ').strip() or
        request.args.get('token', '')
    )
    return jsonify({'auth_required': True, 'valid': _is_valid_token(token)})
