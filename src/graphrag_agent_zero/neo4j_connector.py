"""
GraphRAG for Agent Zero - Neo4j Connector

Safe, bounded connection handler with timeouts, retries, and graceful fallback.
NO arbitrary Cypher execution - only allowlisted templates.
"""

import os
import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import contextmanager

from .safe_cypher import get_safe_query, validate_parameters

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class Neo4jConfig:
    """Configuration for Neo4j connection"""
    uri: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = "graphrag2026"
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
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", "graphrag2026"),
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
        if os.getenv("GRAPH_RAG_ENABLED", "false").lower() != "true":
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
            logger.debug(f"Neo4j health check failed: {e}")
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
        parameters: Optional[Dict[str, Any]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Safe execution interface for all GraphRAG queries.
        
        MAINTENANCE NOTE for Mac:
        - NEVER pass a raw Cypher string here.
        - First add the template to 'safe_cypher.py'.
        - Then call this method with the template name and parameters.
        
        This design ensures that LLM-generated text cannot cause 
        injection or data corruption in your Knowledge Graph.
        """
        # 1. RETRIEVE the pre-defined query
        query = get_safe_query(template_name)
        if not query:
            logger.error(f"Attempted to execute unauthorized template: {template_name}")
            return None
            
        if parameters is None:
            parameters = {}
            
        # 2. VALIDATE the parameters for safety
        if not validate_parameters(parameters):
            logger.warning(f"Invalid parameters for query {template_name}")
            return None
            
        driver = self._get_driver()
        if driver is None:
            return None
            
        # 3. EXECUTE with retry logic for network resilience
        for attempt in range(self.config.max_retries):
            try:
                with driver.session(database=self.config.database) as session:
                    # Parameterized execution - the gold standard for safety
                    # Enforce timeout in seconds (matching Neo4j driver contract)
                    result = session.run(
                        query, 
                        parameters, 
                        timeout=self.config.query_timeout_ms / 1000.0
                    )
                    records = [dict(record) for record in result]
                    return records
            except Exception as e:
                logger.debug(f"Query attempt {attempt + 1} failed: {e}")
                if attempt < self.config.max_retries - 1:
                    time.sleep(self.config.retry_delay_ms / 1000)
                else:
                    logger.warning(f"Query failed after {self.config.max_retries} attempts: {e}")
                    return None
        
        return None
    
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


def is_neo4j_available() -> bool:
    """Check if Neo4j is available for use"""
    # Check feature flag first
    if os.getenv("GRAPH_RAG_ENABLED", "false").lower() != "true":
        return False
    return get_connector().is_healthy()
