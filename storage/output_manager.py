"""Output management for results and reports."""
import json
import csv
from pathlib import Path
from typing import List, Any
from core.models import UnifiedEvent, ValueBet
from config.settings import OUTPUT_DIR

class OutputManager:
    """Manage output files and reports."""
    
    def __init__(self, output_dir: str = OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def save_json(self, filename: str, data: Any):
        """Save data as JSON file."""
        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def save_events(self, provider: str, events: List[UnifiedEvent]):
        """Save events to JSON file."""
        data = [
            {
                "provider": e.provider,
                "provider_event_id": e.provider_event_id,
                "league": e.league,
                "country": e.country,
                "kickoff_utc": e.kickoff_utc,
                "home": e.home,
                "away": e.away,
                "markets": e.markets,
                "scraped_at": e.scraped_at,
                "is_live": e.is_live,
            }
            for e in events
        ]
        self.save_json(f"{provider}.json", data)
    
    def save_value_bets_json(self, value_bets: List[ValueBet]):
        """Save value bets as JSON."""
        data = [bet.to_dict() for bet in value_bets]
        self.save_json("value_bets.json", data)
    
    def save_value_bets_csv(self, value_bets: List[ValueBet]):
        """Save value bets as CSV for easy analysis in Excel."""
        path = self.output_dir / "value_bets.csv"
        
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "League", "Kickoff", "Home", "Away", "Bookmaker", 
                "Market", "Outcome", "Soft Odds", "Anchor Odds",
                "Edge %", "Recommended Stake", "Expected Value"
            ])
            
            for bet in value_bets:
                writer.writerow([
                    bet.league,
                    bet.kickoff,
                    bet.home,
                    bet.away,
                    bet.bookmaker,
                    bet.market,
                    bet.outcome,
                    f"{bet.soft_odds:.3f}",
                    f"{bet.anchor_odds:.3f}",
                    f"{bet.edge_percentage:.2f}",
                    f"{bet.recommended_stake:.2f}",
                    f"{bet.expected_value:.2f}"
                ])
    
    def print_summary(self, value_bets: List[ValueBet], top_n: int = 10):
        """Print summary of top value bets to console."""
        print("\n" + "=" * 100)
        print(f"TOP {top_n} VALUE BETS")
        print("=" * 100)
        
        for i, bet in enumerate(value_bets[:top_n], 1):
            print(f"\n{i}. {bet.home} vs {bet.away}")
            print(f"   League: {bet.league} | Bookmaker: {bet.bookmaker.upper()}")
            print(f"   Market: {bet.market.upper()} | Outcome: {bet.outcome}")
            print(f"   Soft Odds: {bet.soft_odds:.3f} | Anchor Odds: {bet.anchor_odds:.3f}")
            print(f"   Edge: {bet.edge_percentage:.2f}% | Recommended Stake: €{bet.recommended_stake:.2f}")
            print(f"   Expected Value: €{bet.expected_value:.2f}")
        
        print("\n" + "=" * 100)