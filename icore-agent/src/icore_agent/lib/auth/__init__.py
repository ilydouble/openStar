"""Authentication primitives shared by backend HTTP and gateway integration."""

from .jwt import JWTValidationError, sign_access_token, verify_access_token

__all__ = ["JWTValidationError", "sign_access_token", "verify_access_token"]
