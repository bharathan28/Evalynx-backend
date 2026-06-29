"""
Global exception handler.

Ensures every API error returns a uniform JSON envelope:
  { "success": false, "error": { "code": "...", "message": "...", "detail": {...} } }
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    response = exception_handler(exc, context)

    if response is None:
        return None

    error_payload = {
        "success": False,
        "error": {
            "code": _resolve_error_code(response.status_code),
            "message": _resolve_message(response.data),
            "detail": response.data,
        },
    }

    response.data = error_payload
    return response


def _resolve_error_code(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "RATE_LIMITED",
        500: "INTERNAL_SERVER_ERROR",
    }
    return mapping.get(status_code, "ERROR")


def _resolve_message(data: dict | list | str) -> str:
    if isinstance(data, dict):
        # Flatten the first validation error for the top-level message
        for value in data.values():
            if isinstance(value, list) and value:
                return str(value[0])
            if isinstance(value, str):
                return value
    if isinstance(data, list) and data:
        return str(data[0])
    return str(data)
