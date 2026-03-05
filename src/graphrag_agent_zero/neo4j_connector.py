"""
GraphRAG for Agent Zero - Neo4j Connector

Safe, bounded connection handler with timeouts, retries, and graceful fallback.
NO arbitrary Cypher execution - only allowlisted templates.
"""

import os
import time
import random
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import contextmanager

from .safe_cypher import get_safe_query, validate_parameters
from .logger import setup_logger, CorrelationContext
from .errors import CircuitOpenError

# Configure structured logging
logger = setup_logger("graphrag_agent_zero.neo4j")

class Neo4jCircuitBreaker:
    def __init__(self, failure_threshold=5, recovery_timeout=30):
        self.state = 'closed'
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0
    
    def _should_attempt_recovery(self) -> bool:
        return time.time() - self.last_failure_time > self.recovery_timeout
        
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == 'closed' and self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.error("Circuit Breaker OPENED - Neo4j is down", extra={"circuit_breaker_state": "open"})
            
    def record_success(self):
        if self.state != 'closed':
            logger.info("Circuit Breaker CLOSED - Neo4j recovered", extra={"circuit_breaker_state": "closed"})
        self.failure_count = 0
        self.state = 'closed'
        
    def check(self):
        if self.state == 'open':
            if self._should_attempt_recovery():
                self.state = 'half_open'
            else:
                raise CircuitOpenError("Neo4j circuit breaker is open. Waiting for recovery timeout.")

@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection"""
    uri: str = "bolt://localhost:7687"
    http_uri: str = "http://localhost:7474"
    user: str = "neo4j"
    password: str = ""
    database: str = "neo4j"
    connection_timeout_ms: int = 2000
    query_timeout_ms: int = 10000
    max_retries: int = 3
    retry_delay_ms: int = 100
    
    @classmethod
    def from_env(cls) -> 'Neo4jConfig':
        """Load configuration from environment variables"""
        return cls(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            http_uri=os.getenv("NEO4J_HTTP_URI", "http://localhost:7474"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
            database=os.getenv("NEO4J_DATABASE", "neo4j"),
            connection_timeout_ms=int(os.getenv("NEO4J_CONNECTION_TIMEOUT_MS", "2000")),
            query_timeout_ms=int(os.getenv("NEO4J_QUERY_TIMEOUT_MS", "10000")),
            max_retries=int(os.getenv("NEO4J_MAX_RETRIES", "3")),
            retry_delay_ms=int(os.getenv("NEO4J_RETRY_DELAY_MS", "100")),
        )


class Neo4jConnector:
    """
    Standard Neo4j Connection Handler for the 2026 GraphRAG Release.
    
    SECURITY PRINCIPLE:
    - This connector acts as a 'Firewall'.
    - It explicitly FORBIDS the execution of arbitrary Cypher strings.
    - Only allowlisted templates from 'safe_cypher.py' can be executed.
    
    FEATURES:
    - Connection pooling for high-performance multi-agent access.
    - Automatic retries with exponential backoff (minimal impact).
    - Cached health checks to minimize database load.
    """
    
    def __init__(self, config: Optional[Neo4jConfig] = None):
        self.config = config or Neo4jConfig.from_env()
        self._driver = None
        self._healthy = False
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds (throttle health checks)
        self.circuit_breaker = Neo4jCircuitBreaker(failure_threshold=5, recovery_timeout=30)
        
    def _get_driver(self):
        """
        Lazy-initialize the Neo4j Bolt driver.
        Initializes only when the first query is requested.
        """
        if self._driver is None:
            try:
                from neo4j import GraphDatabase
                self._driver = GraphDatabase.driver(
                    self.config.uri,
                    auth=(self.config.user, self.config.password),
                    connection_timeout=self.config.connection_timeout_ms / 1000,
                    max_connection_lifetime=3600,
                    max_connection_pool_size=50,  # Scale for multi-agent setups
                    connection_acquisition_timeout=60,
                )
                logger.info(f"Neo4j driver initialized for {self.config.uri}")
            except ImportError:
                logger.warning("neo4j driver not installed - GraphRAG disabled")
                return None
            except Exception as e:
                logger.warning(f"Failed to initialize Neo4j driver: {e}")
                return None
        return self._driver
    
    def is_healthy(self) -> bool:
        """
        Non-blocking health check.
        Uses a cached status to avoid hitting the DB on every message loop.
        """
        # Feature flag check first for reliability
        # Check both GRAPHRAG_ENABLED (contract) and GRAPH_RAG_ENABLED (legacy)
        if not _is_feature_enabled():
            return False
            
        # Cache health check result to avoid overhead
        now = time.time()
        if now - self._last_health_check < self._health_check_interval:
            return self._healthy
            
        self._last_health_check = now
        driver = self._get_driver()
        
        if driver is None:
            self._healthy = False
            return False
            
        try:
            # Execute a lightweight 'check_health' template query
            with driver.session(database=self.config.database) as session:
                query = get_safe_query("check_health")
                result = session.run(query)
                result.single()
                self._healthy = True
                logger.debug("Neo4j health check passed")
                return True
        except Exception as e:
            self._healthy = False
            logger.warning(f"Neo4j health check failed: {e}")
            return False
    
    @contextmanager
    def session(self):
        """
        Context manager for clean session handling.
        MAINTENANCE NOTE for Mac: Use this if adding new administrative tools.
        """
        driver = self._get_driver()
        if driver is None:
            raise ConnectionError("Neo4j driver not available")
        
        session = None
        try:
            session = driver.session(database=self.config.database)
            yield session
        finally:
            if session:
                session.close()
    
    def execute_template(
        self, 
        template_name: str, 
        parameters: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Safe execution interface for all GraphRAG queries.
        Uses Circuit Breaker and Exponential Backoff for resilience.
        """
        ctx = CorrelationContext(correlation_id)
        
        # 1. RETRIEVE the pre-defined query
        query = get_safe_query(template_name)
        if not query:
            logger.error(f"Attempted to execute unauthorized template: {template_name}", 
                         extra=ctx.get_extra(f"execute_{template_name}", fallback_mode=True))
            return None
            
        if parameters is None:
            parameters = {}
            
        # 2. VALIDATE the parameters for safety
        if not validate_parameters(parameters):
            logger.warning(f"Invalid parameters for query {template_name}", 
                           extra=ctx.get_extra(f"execute_{template_name}", fallback_mode=True))
            return None
        
        # 3. CIRCUIT BREAKER check
        try:
            self.circuit_breaker.check()
        except CircuitOpenError:
            logger.warning("Query rejected due to open circuit breaker", 
                           extra=ctx.get_extra(f"execute_{template_name}", fallback_mode=True))
            return None
            
        driver = self._get_driver()
        if driver is None:
            self.circuit_breaker.record_failure()
            return None
            
        # 4. EXECUTE with Exponential Backoff
        start_time = time.time()
        for attempt in range(self.config.max_retries):
            try:
                with driver.session(database=self.config.database) as session:
                    result = session.run(
                        query, 
                        parameters, 
                        timeout=self.config.query_timeout_ms / 1000.0
                    )
                    records = [dict(record) for record in result]
                    
                    self.circuit_breaker.record_success()
                    duration_ms = int((time.time() - start_time) * 1000)
                    
                    # Log successful execution with metrics
                    logger.debug(f"Executed {template_name} successfully", 
                                extra=ctx.get_extra(
                                    f"execute_{template_name}",
                                    neo4j_query_time_ms=duration_ms,
                                    retry_attempt=attempt
                                ))
                    return records
                    
            except Exception as e:
                # Classify error
                error_msg = str(e).lower()
                is_transient = any(term in error_msg for term in ["timeout", "deadlock", "connection", "socket", "pool"])
                
                if not is_transient:
                    self.circuit_breaker.record_failure()
                    logger.error(f"Permanent DB error on {template_name}: {e}", 
                                 extra=ctx.get_extra(f"execute_{template_name}", fallback_mode=True))
                    return None
                    
                if attempt < self.config.max_retries - 1:
                    # Exponential backoff: base_delay * 2^attempt + jitter
                    base_delay = self.config.retry_delay_ms / 1000.0
                    delay = (base_delay * (2 ** attempt)) + random.uniform(0, 0.1)
                    logger.warning(f"Transient error on {template_name}, retrying in {delay:.2f}s: {e}", 
                                   extra=ctx.get_extra(f"execute_{template_name}", retry_attempt=attempt))
                    time.sleep(delay)
                else:
                    self.circuit_breaker.record_failure()
                    logger.error(f"Failed {template_name} after {self.config.max_retries} attempts: {e}", 
                                 extra=ctx.get_extra(f"execute_{template_name}", fallback_mode=True))
                    return None
        
        return None
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Safely deletes a document node and all its relationships from Neo4j.
        """
        try:
            result = self.execute_template("delete_document", {"doc_id": doc_id})
            if result and len(result) > 0:
                deleted_count = result[0].get("deleted", 0)
                return deleted_count > 0
            return False
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id} from Neo4j: {e}")
            return False

    def close(self):
        """Standard cleanup for the Neo4j driver."""
        if self._driver:
            self._driver.close()
            self._driver = None
            self._healthy = False


# Global connector instance
_connector: Optional[Neo4jConnector] = None


def get_connector() -> Neo4jConnector:
    """Get or create global connector instance"""
    global _connector
    if _connector is None:
        _connector = Neo4jConnector()
    return _connector


def _is_feature_enabled() -> bool:
    """Check if GraphRAG is enabled via feature flags.
    
    Mirrors extension_hook._read_feature_flag() priority:
    1) GRAPHRAG_ENABLED (contract flag)
    2) GRAPH_RAG_ENABLED (legacy)
    3) false (default)
    """
    if "GRAPHRAG_ENABLED" in os.environ:
        return os.getenv("GRAPHRAG_ENABLED", "false").lower() == "true"
    return os.getenv("GRAPH_RAG_ENABLED", "false").lower() == "true"


def is_neo4j_available() -> bool:
    """Check if Neo4j is available for use"""
    # Check feature flag first
    if not _is_feature_enabled():
        return False
    return get_connector().is_healthy()
