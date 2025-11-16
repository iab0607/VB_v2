"""Core data models."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

@dataclass
class UnifiedEvent:
    """Standardized event structure across all providers."""
    provider: str
    provider_event_id: str
    league: str
    country: str
    kickoff_utc: str
    home: str
    away: str
    markets: Dict[str, Dict[str, float]]
    scraped_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    is_live: bool = False

@dataclass 
class ValueBet:
    """Represents a value betting opportunity."""
    league: str
    kickoff: str
    home: str
    away: str
    bookmaker: str
    market: str
    outcome: str
    soft_odds: float
    anchor_odds: float
    soft_prob: float
    anchor_prob: float
    edge_percentage: float
    recommended_stake: float
    expected_value: float
    
    def to_dict(self):
        """Convert to dictionary for serialization."""
        return {
            "league": self.league,
            "kickoff": self.kickoff,
            "home": self.home,
            "away": self.away,
            "bookmaker": self.bookmaker,
            "market": self.market,
            "outcome": self.outcome,
            "soft_odds": self.soft_odds,
            "anchor_odds": self.anchor_odds,
            "soft_prob": round(self.soft_prob, 4),
            "anchor_prob": round(self.anchor_prob, 4),
            "edge_pct": round(self.edge_percentage, 2),
            "recommended_stake": round(self.recommended_stake, 2),
            "expected_value": round(self.expected_value, 2),
        }

@dataclass
class EdgeMetrics:
    """Metrics for tracking edge over time."""
    timestamp: str
    league: str
    match: str
    bookmaker: str
    market: str
    outcome: str
    odds_taken: float
    edge_at_placement: float
    closing_odds: Optional[float] = None
    closing_edge: Optional[float] = None
    result: Optional[str] = None  # "won", "lost", "void"
    profit: Optional[float] = None
    
    def calculate_clv(self) -> Optional[float]:
        """Calculate Closing Line Value."""
        if self.closing_odds:
            return (self.odds_taken / self.closing_odds) - 1.0
        return None