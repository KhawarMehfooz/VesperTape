"""One error envelope for routing, validation, domain, and internal failures."""

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

if __package__:
    from .contracts import ApiError, ErrorDetail, ErrorResponse
else:
    from contracts import ApiError, ErrorDetail, ErrorResponse


class ApiException(Exception):
    """Public, intentionally safe error text supplied by application code."""

    def __init__(self, status_code: int, code: str, message: str, details: list[ErrorDetail] | None = None):
        self.status_code = status_code
        self.error = ApiError(code=code, message=message, details=details or [])


def response(status_code: int, error: ApiError, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error).model_dump(),
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiException)
    async def application_error(request: Request, exception: ApiException):
        return response(exception.status_code, exception.error)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exception: RequestValidationError):
        # Never include input, context, or raw parser messages: these can contain
        # submitted URLs, credentials, headers, or an entire malformed body.
        details = [
            ErrorDetail(
                location=list(error["loc"]),
                code=error["type"],
                message="Required field is missing" if error["type"] == "missing" else "Invalid value",
            )
            for error in exception.errors()
        ]
        return response(422, ApiError(code="validation_error", message="Request validation failed", details=details))

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exception: HTTPException):
        codes = {404: "not_found", 405: "method_not_allowed"}
        try:
            message = HTTPStatus(exception.status_code).phrase
        except ValueError:
            message = "Request failed"
        return response(exception.status_code, ApiError(
            code=codes.get(exception.status_code, "http_error"), message=message,
        ), exception.headers)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exception: Exception):
        return response(500, ApiError(code="internal_error", message="Internal server error"))
