import json
import logging
import datetime
import uuid
import sys
from typing import Any, Dict, Optional

class GraphRAGJSONFormatter(logging.Formatter):
    """Formats log records as JSON with correlation IDs and custom metrics."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.datetime.fromtimestamp(record.created, datetime.timezone.utc).isoformat()[:-0] + "Z",
            "level": record.levelname,
            "component": getattr(record, "component", "graphrag_agent_zero"),
            "operation": getattr(record, "operation", "system"),
            "message": record.getMessage()
        }
        
        # Add correlation ID if present
        if hasattr(record, "correlation_id"):
            log_obj["correlation_id"] = record.correlation_id
            
        # Add custom metrics directly to JSON payload
        for attr in ["memory_id", "entity_count", "duration_ms", "neo4j_query_time_ms", 
                     "cache_hit", "fallback_mode", "circuit_breaker_state", "retry_attempt"]:
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)
                
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def setup_logger(name: str = "graphrag_agent_zero") -> logging.Logger:
    logger = logging.getLogger(name)
    
    # Only add handler if not already present
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(GraphRAGJSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False # Prevent double logging if root logger also catches it
        
    return logger

class CorrelationContext:
    """Helper to generate and pass correlation IDs"""
    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        
    def get_extra(self, operation: str, **kwargs) -> Dict[str, Any]:
        """Returns the dictionary for the 'extra' kwarg in logger calls"""
        extra = {"correlation_id": self.correlation_id, "operation": operation}
        extra.update(kwargs)
        return extra
