"""Bounded strict JSON parsing and safe HTTP exception conversion."""
import json
import math
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from .common import ApiError, require, uid
from .adapters.business import ValidationError, ContractError, AftercareError


def strict_route(operator):
    class StrictRoute(APIRoute):
        def get_route_handler(self):
            original = super().get_route_handler()
            async def strict(request):
                # Operator decision routes reject before parsing their JSON body.
                if request.url.path.endswith('/decisions'):
                    operator(request)
                raw_upload = self.path in {'/api/v1/cases/{case_id}/contract-reviews',
                    '/api/v1/cases/{case_id}/living-services/attachments'}
                if not raw_upload and request.method == 'POST':
                    media = request.headers.get('Content-Type', '').split(';')[0].strip().lower()
                    require(not media or media == 'application/json' or (media.startswith('application/') and media.endswith('+json')),
                            415, 'unsupported_media_type', 'Send a JSON request')
                    def unique(items):
                        result = {}
                        for key, value in items:
                            require(key not in result, 422, 'invalid_json', 'Duplicate JSON keys are not allowed')
                            result[key] = value
                        return result
                    def finite_float(value):
                        number = float(value)
                        require(math.isfinite(number), 422, 'invalid_json', 'Non-finite numbers are not allowed')
                        return number
                    def constant(value):
                        raise ApiError(422, 'invalid_json', 'Non-finite numbers are not allowed')
                    try:
                        raw = bytearray()
                        async for chunk in request.stream():
                            require(len(raw) + len(chunk) <= 256_000, 413, 'request_too_large', 'JSON request exceeds the local limit')
                            raw.extend(chunk)
                        # Preserve Starlette's body cache for the subsequent FastAPI parameter parser.
                        request._body = bytes(raw)
                        json.loads(raw, object_pairs_hook=unique, parse_constant=constant, parse_float=finite_float)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        raise ApiError(422, 'invalid_json', 'Supply valid UTF-8 JSON')
                return await original(request)
            return strict

    return StrictRoute


def install_error_handlers(app, services):
    safe_message = services.safe_message
    def failure(request, status, code, message, fields=None):
        error = {'code': code, 'message': safe_message(message), 'request_id': request.headers.get('X-Request-Id', uid('error'))}
        if fields:
            error['fields'] = fields
        return JSONResponse({'error': error}, status_code=status)

    @app.exception_handler(ApiError)
    async def api_failure(request, exc):
        return failure(request, exc.status, exc.code, exc.message, exc.fields)

    @app.exception_handler(RequestValidationError)
    async def validation_failure(request, exc):
        return failure(request, 422, 'invalid_input', 'Request parameters are invalid')

    @app.exception_handler(HTTPException)
    async def http_failure(request, exc):
        return failure(request, exc.status_code, 'not_found' if exc.status_code == 404 else 'invalid_request', exc.detail)

    @app.exception_handler(AftercareError)
    async def aftercare_failure(request, exc):
        code = exc.code
        status = 403 if code == 'access_denied' else 404 if code == 'not_found' else 503 if code == 'storage_error' else 422 if code == 'invalid_input' else 409
        return failure(request, status, code, str(exc))

    @app.exception_handler(ContractError)
    async def contract_failure(request, exc):
        code = exc.code
        return failure(request, 409 if code in {'duplicate_request_conflict', 'invalid_request'} else 422, code, str(exc))

    @app.exception_handler(ValidationError)
    async def profile_failure(request, exc):
        return failure(request, 422, 'invalid_profile', str(exc), {'profile': safe_message(exc)})

    @app.exception_handler(ValueError)
    async def value_failure(request, exc):
        return failure(request, 422, 'invalid_input', str(exc))

    @app.exception_handler(Exception)
    async def unknown_failure(request, exc):
        return failure(request, 500, 'service_failure', 'The local operation failed. Previous saved results remain available.')
