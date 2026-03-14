"""Custom exceptions for Skua."""


class SkuaError(Exception):
    """Base exception for all Skua errors."""

    pass


class UploadError(SkuaError):
    """Error during upload to Skua API."""

    pass


class ConfigurationError(SkuaError):
    """Error in Skua configuration."""

    pass


class SerializationError(SkuaError):
    """Error during object serialization."""

    pass


class ValidationError(SkuaError):
    """Error validating input (e.g., title too long, description too long)."""

    pass
