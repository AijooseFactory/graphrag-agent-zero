import time
from collections import OrderedDict
from typing import Any, Optional

class LRUTTLCache:
    """Least Recently Used (LRU) Cache with Time-To-Live (TTL) eviction."""
    
    def __init__(self, capacity: int = 1000, ttl_seconds: int = 3600):
        self.capacity = capacity
        self.ttl = ttl_seconds
        self.cache: OrderedDict[str, Any] = OrderedDict()
        self.timestamps: dict[str, float] = {}
        
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
            
        # Check TTL
        if time.time() - self.timestamps[key] > self.ttl:
            self._evict(key)
            return None
            
        # Move to end as recently used (LRU property)
        self.cache.move_to_end(key)
        return self.cache[key]
        
    def set(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                # Evict oldest
                oldest_key = next(iter(self.cache))
                self._evict(oldest_key)
                
        self.cache[key] = value
        self.timestamps[key] = time.time()
        
    def _evict(self, key: str):
        if key in self.cache:
            del self.cache[key]
        if key in self.timestamps:
            del self.timestamps[key]
            
    def clear(self):
        self.cache.clear()
        self.timestamps.clear()
