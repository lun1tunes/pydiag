class VersionConflictError(RuntimeError):
    """Raised when a writer tries to save stale JSON state."""


class FileLockTimeoutError(TimeoutError):
    """Raised when an exclusive state-file lock cannot be acquired in time."""
