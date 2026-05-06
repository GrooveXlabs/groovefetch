"""Adaptive learning engine — learns optimal scraping strategies per domain."""

import time
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics


@dataclass
class DomainProfile:
    """Learned profile for a specific domain."""
    domain: str
    request_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    delays: list = None
    stealth_required: bool = False
    optimal_headers: Dict[str, str] = None
    best_user_agent: str = ""
    retry_pattern: str = "exponential"
    last_updated: float = 0.0
    
    def __post_init__(self):
        if self.delays is None:
            self.delays = []
        if self.optimal_headers is None:
            self.optimal_headers = {}
        if self.last_updated == 0.0:
            self.last_updated = time.time()
    
    @property
    def success_rate(self) -> float:
        if self.request_count == 0:
            return 0.0
        return self.success_count / self.request_count
    
    @property
    def optimal_delay(self) -> float:
        if not self.delays:
            return 2.0
        # Use median to be robust against outliers
        return statistics.median(self.delays)
    
    def record_attempt(self, success: bool, delay: float, used_stealth: bool):
        """Record the result of a scraping attempt."""
        self.request_count += 1
        if success:
            self.success_count += 1
            self.delays.append(delay)
            # Keep only last 50 delays
            self.delays = self.delays[-50:]
        else:
            self.failure_count += 1
        
        if used_stealth:
            # Weight stealth requirement by success rate
            current = float(self.stealth_required)
            new = 1.0 if success else 0.0
            self.stealth_required = (current * self.request_count + new) / (self.request_count + 1)
        
        self.last_updated = time.time()


class AdaptiveLearner:
    """Learns and stores optimal scraping strategies per domain.
    
    Usage:
        learner = AdaptiveLearner()
        learner.record("example.com", success=True, delay=1.5, used_stealth=False)
        
        # Later, get optimized settings
        profile = learner.get_profile("example.com")
        print(profile.optimal_delay)  # ~1.5
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = storage_path or str(Path.home() / ".groovefetch" / "profiles.json")
        self.profiles: Dict[str, DomainProfile] = {}
        self._load()
    
    def record(
        self,
        domain: str,
        success: bool,
        delay: float,
        used_stealth: bool = False,
        headers: Optional[Dict[str, str]] = None
    ):
        """Record the outcome of a scraping attempt.
        
        Args:
            domain: Target domain
            success: Whether the request succeeded
            delay: Delay used before this request (seconds)
            used_stealth: Whether stealth mode was used
            headers: Headers that were used
        """
        if domain not in self.profiles:
            self.profiles[domain] = DomainProfile(domain=domain)
        
        profile = self.profiles[domain]
        profile.record_attempt(success, delay, used_stealth)
        
        # Track which headers correlate with success
        if success and headers:
            # Simple: just store the last successful headers
            profile.optimal_headers = dict(headers)
        
        self._save()
    
    def get_profile(self, domain: str) -> DomainProfile:
        """Get learned profile for a domain.
        
        Args:
            domain: Domain to look up
            
        Returns:
            DomainProfile (returns defaults if never seen)
        """
        return self.profiles.get(domain, DomainProfile(domain=domain))
    
    def should_use_stealth(self, domain: str, threshold: float = 0.6) -> bool:
        """Determine if stealth mode is recommended for a domain.
        
        Args:
            domain: Target domain
            threshold: Probability threshold for stealth recommendation
            
        Returns:
            True if stealth is recommended
        """
        profile = self.get_profile(domain)
        if profile.request_count < 3:
            return False  # Not enough data
        return profile.stealth_required > threshold
    
    def recommend_delay(self, domain: str) -> float:
        """Recommend optimal delay for a domain.
        
        Args:
            domain: Target domain
            
        Returns:
            Recommended delay in seconds
        """
        profile = self.get_profile(domain)
        base = profile.optimal_delay
        
        # Adjust based on success rate
        if profile.success_rate < 0.5:
            base *= 2.0  # Be more conservative
        elif profile.success_rate > 0.95:
            base *= 0.8  # Can be slightly more aggressive
        
        return max(base, 0.5)  # Minimum 500ms
    
    def stats(self, domain: str) -> Dict[str, Any]:
        """Get human-readable stats for a domain.
        
        Args:
            domain: Target domain
            
        Returns:
            Dictionary of stats
        """
        p = self.get_profile(domain)
        return {
            "domain": domain,
            "requests": p.request_count,
            "success_rate": round(p.success_rate, 2),
            "optimal_delay": round(p.optimal_delay, 2),
            "stealth_required": p.stealth_required > 0.5,
            "last_updated": p.last_updated,
        }
    
    def _load(self):
        """Load profiles from disk."""
        path = Path(self.storage_path)
        if not path.exists():
            return
        
        try:
            with open(path) as f:
                data = json.load(f)
            
            for domain, profile_data in data.items():
                self.profiles[domain] = DomainProfile(**profile_data)
        except (json.JSONDecodeError, TypeError):
            self.profiles = {}
    
    def _save(self):
        """Save profiles to disk."""
        path = Path(self.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {domain: asdict(profile) for domain, profile in self.profiles.items()}
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
