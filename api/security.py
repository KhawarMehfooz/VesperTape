"""Optional browser-compatible single-user authentication for every app surface."""

import base64
import binascii
import secrets
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse


class AccessProtection:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        settings = getattr(scope['app'].state, 'settings', None)
        password = settings.access_password if settings else None
        headers = Headers(scope=scope)
        if password is not None and scope['path'] != '/api/health':
            valid = False
            try:
                scheme, token = headers.get('authorization', '').split(' ', 1)
                if scheme.lower() == 'basic':
                    username, supplied = base64.b64decode(token, validate=True).decode('utf-8').split(':', 1)
                    valid = secrets.compare_digest(username.encode(), b'vespertape') & secrets.compare_digest(
                        supplied.encode(), password.get_secret_value().encode())
            except (ValueError, UnicodeError, binascii.Error):
                pass
            if not valid:
                return await self.reject(scope, receive, send, 401, 'authentication_required',
                    'Sign in to VesperTape', {'WWW-Authenticate': 'Basic realm="VesperTape", charset="UTF-8"'})
        # Browsers may attach cached Basic credentials to cross-site requests.
        # Reject cross-origin mutations even when password protection is disabled.
        if scope['method'] not in ('GET', 'HEAD', 'OPTIONS'):
            origin = headers.get('origin')
            if headers.get('sec-fetch-site') == 'cross-site' or (origin and not self.same_origin(origin, scope, headers)):
                return await self.reject(scope, receive, send, 403, 'forbidden_origin', 'Cross-origin requests are not allowed')
        started = False
        async def safe_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
            await send(message)
        try:
            await self.app(scope, receive, safe_send)
        except Exception:
            # Uvicorn otherwise logs raw exception text after an error response.
            # Do not expose extractor, credential, or request details in tracebacks.
            if started:
                raise RuntimeError('Request failed after response started') from None
            await self.reject(scope, receive, send, 500, 'internal_error', 'Internal server error')

    @staticmethod
    def same_origin(origin, scope, headers):
        try:
            source = urlsplit(origin)
            target = urlsplit(f"{scope['scheme']}://{headers.get('host', '')}")
            return (source.scheme in ('http', 'https') and not source.username and not source.password
                    and not source.path and not source.query and not source.fragment
                    and (source.scheme, source.hostname, source.port or (443 if source.scheme == 'https' else 80))
                    == (target.scheme, target.hostname, target.port or (443 if target.scheme == 'https' else 80)))
        except ValueError:
            return False

    @staticmethod
    async def reject(scope, receive, send, status, code, message, headers=None):
        response = JSONResponse({'error': {'code': code, 'message': message, 'details': []}},
                                status_code=status, headers={'Cache-Control': 'no-store', **(headers or {})})
        await response(scope, receive, send)
