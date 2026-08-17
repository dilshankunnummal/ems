"""
Standardized API response envelope used by every endpoint in the system.

Success:
    {"success": true, "message": "...", "data": {...}, "meta": {...}}
Error:
    {"success": false, "message": "...", "error_code": "...", "details": {...}}
"""
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ResponseEnvelope(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Success"
    data: T | None = None
    meta: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    success: bool = False
    message: str
    error_code: str
    details: Any | None = None


def success_response(
    data: Any = None,
    message: str = "Success",
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {"success": True, "message": message, "data": data, "meta": meta}


def error_response(
    message: str,
    error_code: str,
    details: Any = None,
) -> dict[str, Any]:
    return {"success": False, "message": message, "error_code": error_code, "details": details}
