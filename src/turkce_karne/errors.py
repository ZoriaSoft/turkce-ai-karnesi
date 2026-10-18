"""Shared exception types."""


class DatasetError(Exception):
    """Dataset files are missing or malformed."""


class CheckSpecError(DatasetError):
    """A check specification in the dataset is invalid."""


class ClientError(Exception):
    """The model endpoint failed after all retries (or with a fatal error)."""
