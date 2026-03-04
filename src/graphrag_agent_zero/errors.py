class GraphRAGError(Exception):
    """Base exception for GraphRAG errors"""
    pass

class TransientError(GraphRAGError):
    """Temporary failures - retry recommended"""
    def __init__(self, message: str, retry_after: int = None, max_retries: int = 3):
        super().__init__(message)
        self.retry_after = retry_after
        self.max_retries = max_retries

class PermanentError(GraphRAGError):
    """Unrecoverable failures - fail fast"""
    pass

class CircuitOpenError(GraphRAGError):
    """Circuit breaker is open - Neo4j is unreachable"""
    pass

class PartialSuccessError(GraphRAGError):
    """Partial completion - log and continue"""
    def __init__(self, message: str, succeeded: int, failed: int, failed_items: list[str] = None):
        super().__init__(message)
        self.succeeded = succeeded
        self.failed = failed
        self.failed_items = failed_items or []
