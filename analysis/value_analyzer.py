"""Value betting analysis and edge calculation."""
import logging
from typing import List, Dict, Optional
from core.models import UnifiedEvent, ValueBet
from matching.event_matcher import EventMatcher
from config.settings import MINIMUM_EDGE_THRESHOLD, KELLY_FRACTION, MAX_STAKE_PERCENTAGE
from utils.logging_config import log_edge_opportunity

logger = logging.getLogger(__name__)

class ValueAnalyzer:
    """Analyze betting value by comparing soft books to sharp anchor."""
    
    @staticmethod
    def remove_vig_multiplicative(odds: Dict[str, float]) -> Optional[Dict[str, float]]:
        """
        Multiplicative vig removal - more accurate than simple proportional.
        Uses power method for better accuracy with unequal margins.
        """
        try:
            keys = list(odds.keys())
            if "margin" in keys:
                keys.remove("margin")
            if "line" in keys:
                keys.remove("line")
            
            implied_probs = {k: 1.0/odds[k] for k in keys}
            total = sum(implied_probs.values())
            
            # Power method for accurate vig removal
            n = len(keys)
            if n <= 1:
                return {keys[0]: 1.0} if n == 1 else None
            
            exponent = (n - 1) / n
            
            adjusted = {}
            for k in keys:
                prob = implied_probs[k]
                adjusted[k] = prob ** (1/exponent) / (total ** (1/exponent))
            
            # Normalize to 1.0
            adj_total = sum(adjusted.values())
            return {k: v/adj_total for k, v in adjusted.items()}
        except (KeyError, ZeroDivisionError, ValueError):
            return None
    
    @staticmethod
    def calculate_edge(true_prob: float, offered_odds: float) -> float:
        """
        Calculate betting edge: (true_prob * offered_odds) - 1
        Positive = value bet
        """
        return (true_prob * offered_odds) - 1.0
    
    @staticmethod
    def kelly_stake(edge: float, odds: float, bankroll: float, 
                   kelly_fraction: float = KELLY_FRACTION) -> float:
        """
        Calculate Kelly stake with fractional Kelly for risk management.
        
        Returns:
            Recommended stake amount (capped at MAX_STAKE_PERCENTAGE of bankroll)
        """
        if edge <= 0 or odds <= 1.0:
            return 0.0
        
        # Kelly formula: f = (bp - q) / b
        p = (1 + edge) / odds  # True probability
        q = 1 - p
        b = odds - 1
        
        kelly = (b * p - q) / b
        
        # Apply fractional Kelly
        fractional_kelly = max(0, kelly * kelly_fraction)
        
        # Cap at MAX_STAKE_PERCENTAGE for safety
        return min(fractional_kelly * bankroll, bankroll * MAX_STAKE_PERCENTAGE)
    
    @classmethod
    def check_home_away_swap(cls, soft_odds: Dict[str, float], 
                            anchor_odds: Dict[str, float]) -> Dict[str, float]:
        """
        Check if home/away might be swapped and return best match.
        Returns probabilities that best align with anchor.
        """
        normal_probs = cls.remove_vig_multiplicative(soft_odds)
        anchor_probs = cls.remove_vig_multiplicative(anchor_odds)
        
        if not normal_probs or not anchor_probs:
            return normal_probs or {}
        
        # Calculate divergence for normal orientation
        normal_div = sum(abs(normal_probs.get(k, 0) - anchor_probs.get(k, 0)) 
                        for k in anchor_probs.keys())
        
        # Try swapped (if 3-way market)
        if "home" in soft_odds and "away" in soft_odds:
            swapped_odds = {
                "home": soft_odds.get("away"),
                "draw": soft_odds.get("draw"),
                "away": soft_odds.get("home")
            }
            swapped_probs = cls.remove_vig_multiplicative(swapped_odds)
            
            if swapped_probs:
                swapped_div = sum(abs(swapped_probs.get(k, 0) - anchor_probs.get(k, 0)) 
                                 for k in anchor_probs.keys())
                # If swapped is significantly better, use it and log warning
                if swapped_div + 0.05 < normal_div:
                    logger.warning("Detected home/away swap - using swapped probabilities")
                    return swapped_probs
        
        return normal_probs
    
    @classmethod
    def generate_value_bets(
        cls,
        anchor_events: List[UnifiedEvent],
        soft_books: Dict[str, List[UnifiedEvent]],
        time_tolerance: int = 12,
        min_edge: float = MINIMUM_EDGE_THRESHOLD,
        bankroll: float = 1000.0
    ) -> List[ValueBet]:
        """
        Generate list of value bets with edge above threshold.
        
        Args:
            anchor_events: Events from sharp bookmaker (Pinnacle)
            soft_books: Dict of bookmaker name -> events
            time_tolerance: Minutes tolerance for matching
            min_edge: Minimum edge threshold (e.g., 0.025 = 2.5%)
            bankroll: Bankroll for stake calculation
            
        Returns:
            List of ValueBet objects sorted by edge
        """
        value_bets = []
        
        for book_name, book_events in soft_books.items():
            matches = EventMatcher.match_events(book_events, anchor_events, time_tolerance)
            logger.info(f"Found {len(matches)} matches for {book_name}")
            
            for soft_event, anchor_event in matches:
                # Process each market type
                for market_type in ["1x2", "ou_2_5", "btts"]:
                    if market_type not in soft_event.markets or market_type not in anchor_event.markets:
                        continue
                    
                    # Get true probabilities from anchor
                    if market_type == "1x2":
                        soft_probs = cls.check_home_away_swap(
                            soft_event.markets[market_type],
                            anchor_event.markets[market_type]
                        )
                    else:
                        soft_probs = cls.remove_vig_multiplicative(soft_event.markets[market_type])
                    
                    anchor_probs = cls.remove_vig_multiplicative(anchor_event.markets[market_type])
                    
                    if not soft_probs or not anchor_probs:
                        continue
                    
                    # Calculate edge for each outcome
                    for outcome in anchor_probs.keys():
                        if outcome not in soft_event.markets[market_type]:
                            continue
                        
                        true_prob = anchor_probs[outcome]
                        soft_odds = soft_event.markets[market_type][outcome]
                        anchor_odds = anchor_event.markets[market_type][outcome]
                        
                        edge = cls.calculate_edge(true_prob, soft_odds)
                        
                        # Filter by minimum edge
                        if edge >= min_edge:
                            stake = cls.kelly_stake(edge, soft_odds, bankroll)
                            ev = stake * edge
                            value_bet = ValueBet(
                                league=soft_event.league,
                                kickoff=soft_event.kickoff_utc,
                                home=soft_event.home,
                                away=soft_event.away,
                                bookmaker=book_name,
                                market=market_type,
                                outcome=outcome,
                                soft_odds=soft_odds,
                                anchor_odds=anchor_odds,
                                soft_prob=soft_probs[outcome],
                                anchor_prob=true_prob,
                                edge_percentage=edge * 100,
                                recommended_stake=stake,
                                expected_value=ev
                            )
                            
                            value_bets.append(value_bet)
                            
                            # Log for analysis
                            log_edge_opportunity(
                                league=soft_event.league,
                                match=f"{soft_event.home} vs {soft_event.away}",
                                bookmaker=book_name,
                                market=market_type,
                                outcome=outcome,
                                soft_odds=soft_odds,
                                anchor_odds=anchor_odds,
                                edge_pct=edge * 100,
                                recommended_stake=stake,
                                ev=ev
                            )
        
        # Sort by edge (highest first)
        value_bets.sort(key=lambda x: x.edge_percentage, reverse=True)
        
        logger.info(f"Found {len(value_bets)} value bets above {min_edge*100:.1f}% edge threshold")
        return value_bets