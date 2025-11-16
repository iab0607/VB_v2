"""Jack's Casino scraper (Kambi platform)."""
import logging
from typing import List, Dict, Optional, Tuple
from core.models import UnifiedEvent
from core.http_client import HttpClient
from utils.datetime_utils import normalize_iso_datetime
from config.leagues import get_league_config

logger = logging.getLogger(__name__)

def calculate_margin(odds_map: Dict[str, float]) -> float:
    implied_probs = [1.0/v for v in odds_map.values() if v and v > 1.0]
    return round((sum(implied_probs) - 1.0) * 100.0, 3) if implied_probs else 0.0

class JacksScraper:
    """Scraper for Jack's Casino odds (Kambi platform)."""
    
    BASE_URL = "https://eu1.offering-api.kambicdn.com/offering/v2018/jvh"
    
    def __init__(self, http: HttpClient):
        self.http = http
        self.headers = {"accept": "application/json"}
    
    @staticmethod
    def kambi_to_decimal(kambi_odds) -> Optional[float]:
        try:
            value = int(kambi_odds)
            return round(value / 1000.0, 3) if value >= 1000 else None
        except (ValueError, TypeError):
            return None
    
    @staticmethod
    def extract_line(offer: Dict) -> Optional[float]:
        line = offer.get("line")
        if line:
            try:
                return float(str(line).replace(",", ".").split("/")[0])
            except (ValueError, TypeError):
                pass
        return None
    
    def parse_bet_offer(self, offer: Dict) -> Tuple[Optional[str], Optional[Dict]]:
        outcomes = [o for o in offer.get("outcomes", []) if o.get("status", "").upper() in ("OPEN", "")]
        if not outcomes:
            return None, None
        
        # 1X2 Market
        if len(outcomes) == 3:
            odds = {}
            for outcome in outcomes:
                label = outcome.get("label", "").strip()
                decimal = self.kambi_to_decimal(outcome.get("odds"))
                if decimal:
                    if label == "1":
                        odds["home"] = decimal
                    elif label == "X":
                        odds["draw"] = decimal
                    elif label == "2":
                        odds["away"] = decimal
            
            if set(odds.keys()) == {"home", "draw", "away"}:
                return "1x2", {**odds, "margin": calculate_margin(odds)}
        
        # 2-way markets
        elif len(outcomes) == 2:
            line = self.extract_line(offer)
            if line and abs(line - 2.5) < 0.01:
                odds = {}
                for outcome in outcomes:
                    label = (outcome.get("label") or "").lower()
                    decimal = self.kambi_to_decimal(outcome.get("odds"))
                    if decimal:
                        if "over" in label:
                            odds["over"] = decimal
                        elif "under" in label:
                            odds["under"] = decimal
                
                if set(odds.keys()) == {"over", "under"}:
                    return "ou_2_5", {**odds, "line": 2.5, "margin": calculate_margin(odds)}
            
            bet_type = (offer.get("betOfferType", {}).get("name") or "").lower()
            if "both" in bet_type or "scoren" in bet_type:
                odds = {}
                for outcome in outcomes:
                    label = (outcome.get("label") or "").lower()
                    decimal = self.kambi_to_decimal(outcome.get("odds"))
                    if decimal:
                        if label in ("yes", "ja"):
                            odds["yes"] = decimal
                        elif label in ("no", "nee"):
                            odds["no"] = decimal
                
                if set(odds.keys()) == {"yes", "no"}:
                    return "btts", {**odds, "margin": calculate_margin(odds)}
        
        return None, None
    
    async def fetch_league_events(self, league_key: str) -> List[UnifiedEvent]:
        league_config = get_league_config(league_key)
        if not league_config or "jacks_path" not in league_config:
            logger.warning(f"No Jacks config for {league_key}")
            return []
        
        path = league_config["jacks_path"]
        url = f"{self.BASE_URL}/listView/{path}.json"
        params = {"lang": "nl_NL", "market": "NL"}
        
        data = await self.http.get(url, params=params, headers=self.headers)
        if not data or not isinstance(data, dict):
            return []
        
        events = []
        events_data = data.get("events", [])
        
        for item in events_data:
            event_data = item.get("event", {})
            event_id = event_data.get("id")
            
            if not event_id:
                continue
            
            home = event_data.get("homeName")
            away = event_data.get("awayName")
            kickoff = normalize_iso_datetime(event_data.get("start", ""))
            
            if not (home and away and kickoff):
                continue
            
            markets = {}
            for offer in item.get("betOffers", []):
                market_type, market_data = self.parse_bet_offer(offer)
                if market_type and market_data:
                    markets[market_type] = market_data
            
            if markets:
                events.append(UnifiedEvent(
                    provider="jacks",
                    provider_event_id=str(event_id),
                    league=league_key,
                    country=league_config["country"],
                    kickoff_utc=kickoff,
                    home=home,
                    away=away,
                    markets=markets,
                    is_live=bool(event_data.get("liveBetting")),
                ))
        
        logger.info(f"Jacks: Fetched {len(events)} events for {league_key}")
        return events