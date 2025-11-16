"""TOTO scraper."""
import asyncio
import re
import logging
from typing import List, Dict, Optional
from core.models import UnifiedEvent
from core.http_client import HttpClient
from utils.datetime_utils import normalize_iso_datetime
from config.leagues import get_league_config
from config.settings import TOTO_RATE_LIMIT_DELAY

logger = logging.getLogger(__name__)

def calculate_margin(odds_map: Dict[str, float]) -> float:
    implied_probs = [1.0/v for v in odds_map.values() if v and v > 1.0]
    return round((sum(implied_probs) - 1.0) * 100.0, 3) if implied_probs else 0.0

class TotoScraper:
    """Scraper for TOTO odds."""
    
    EVENT_LIST_URL = "https://sport-api.toto.nl/event/request"
    EVENT_DETAIL_URL = "https://sport-api.toto.nl/cms/content"
    
    def __init__(self, http: HttpClient):
        self.http = http
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://sport.toto.nl/",
            "Origin": "https://sport.toto.nl",
        }
    
    @staticmethod
    def extract_odds(outcome: Dict) -> Optional[float]:
        prices = outcome.get("prices", [])
        if prices:
            decimal = prices[0].get("decimal")
            try:
                value = float(decimal)
                return round(value, 3) if value >= 1.01 else None
            except (ValueError, TypeError):
                pass
        return None
    
    @staticmethod
    def extract_line_from_label(label: str) -> Optional[float]:
        match = re.search(r'(\d+(?:[.,]\d+)?)', label)
        if match:
            try:
                return float(match.group(1).replace(',', '.'))
            except ValueError:
                pass
        return None
    
    def parse_markets(self, markets: List[Dict]) -> Dict[str, Dict[str, float]]:
        result = {}
        
        for market in markets:
            active_outcomes = [o for o in market.get("outcomes", []) if o.get("active")]
            if not active_outcomes:
                continue
            
            group_code = (market.get("groupCode") or "").lower()
            template_name = (market.get("templateName") or "").lower()
            
            # 1X2 Market
            if any(k in group_code or k in template_name for k in ("match odds", "1x2", "match result")):
                if len(active_outcomes) == 3:
                    odds = {}
                    for outcome in active_outcomes:
                        label = (outcome.get("name") or outcome.get("label") or "").lower()
                        decimal = self.extract_odds(outcome)
                        if decimal:
                            if label in ("home", "thuis", "1"):
                                odds["home"] = decimal
                            elif label in ("draw", "gelijkspel", "x"):
                                odds["draw"] = decimal
                            elif label in ("away", "uit", "2"):
                                odds["away"] = decimal
                    
                    if set(odds.keys()) == {"home", "draw", "away"} and "1x2" not in result:
                        result["1x2"] = {**odds, "margin": calculate_margin(odds)}
            
            # Over/Under 2.5
            elif "total goals" in group_code or "over/under" in group_code:
                if len(active_outcomes) == 2:
                    line = market.get("line")
                    if not line:
                        for outcome in active_outcomes:
                            label = outcome.get("label") or outcome.get("name") or ""
                            extracted_line = self.extract_line_from_label(label)
                            if extracted_line:
                                line = extracted_line
                                break
                    
                    try:
                        line_value = float(line) if line else None
                        if line_value and abs(line_value - 2.5) < 0.01:
                            odds = {}
                            for outcome in active_outcomes:
                                label = (outcome.get("name") or outcome.get("label") or "").lower()
                                decimal = self.extract_odds(outcome)
                                if decimal:
                                    if "over" in label or "meer" in label:
                                        odds["over"] = decimal
                                    elif "under" in label or "minder" in label:
                                        odds["under"] = decimal
                            
                            if set(odds.keys()) == {"over", "under"} and "ou_2_5" not in result:
                                result["ou_2_5"] = {**odds, "line": 2.5, "margin": calculate_margin(odds)}
                    except (ValueError, TypeError):
                        pass
            
            # BTTS
            elif "both_teams_to_score" in group_code or "btts" in group_code:
                if len(active_outcomes) == 2:
                    odds = {}
                    for outcome in active_outcomes:
                        label = (outcome.get("name") or outcome.get("label") or "").lower()
                        decimal = self.extract_odds(outcome)
                        if decimal:
                            if label in ("yes", "ja"):
                                odds["yes"] = decimal
                            elif label in ("no", "nee"):
                                odds["no"] = decimal
                    
                    if set(odds.keys()) == {"yes", "no"} and "btts" not in result:
                        result["btts"] = {**odds, "margin": calculate_margin(odds)}
        
        return result
    
    async def fetch_event_list(self, competition_key: str) -> List[Dict]:
        league_config = get_league_config(competition_key)
        if not league_config or "toto_id" not in league_config:
            return []
        
        comp_id = league_config["toto_id"]
        
        payload = {
            "includedIds": [{"selectionId": comp_id}],
            "isLive": True,
            "isPreMatch": True,
            "order": "START_TIME",
            "addOutRights": False,
            "grouping": "TIME",
            "eventListType": "STANDARD",
            "sortCode": "MTCH",
        }
        
        data = await self.http.post_json(
            self.EVENT_LIST_URL,
            json_body=payload,
            headers={**self.headers, "Content-Type": "application/json"}
        )
        
        if not isinstance(data, dict):
            return []
        
        events = []
        for group in data.get("eventGroups", []):
            events.extend(group.get("events", []))
        
        return events
    
    async def fetch_event_details(self, event_id: str, event_name: str) -> Optional[Dict]:
        params = {
            "eventId": event_id,
            "freetext": event_name.lower().replace(" ", "-"),
            "route": "Event",
            "formFactor": "mobile"
        }
        
        data = await self.http.get(self.EVENT_DETAIL_URL, params=params, headers=self.headers)
        return data if isinstance(data, dict) else None
    
    async def fetch_league_events(self, league_key: str) -> List[UnifiedEvent]:
        league_config = get_league_config(league_key)
        if not league_config or "toto_id" not in league_config:
            logger.warning(f"No TOTO config for {league_key}")
            return []
        
        events_list = await self.fetch_event_list(league_key)
        if not events_list:
            return []
        
        results = []
        for event in events_list:
            event_id = event.get("id") or event.get("eventId")
            if not event_id:
                continue
            
            details = await self.fetch_event_details(str(event_id), event.get("name", ""))
            if not details:
                continue
            
            items = details.get("items", [])
            if not items:
                continue
            
            markets_data = items[0].get("data", {}).get("event", {}).get("markets", [])
            parsed_markets = self.parse_markets(markets_data)
            
            if not parsed_markets:
                continue
            
            home = away = None
            for team in event.get("teams", []):
                side = (team.get("side") or "").lower()
                if side == "home":
                    home = team.get("name")
                elif side == "away":
                    away = team.get("name")
            
            kickoff = normalize_iso_datetime(event.get("startTime", ""))
            
            if home and away and kickoff:
                results.append(UnifiedEvent(
                    provider="toto",
                    provider_event_id=str(event_id),
                    league=league_key,
                    country=league_config["country"],
                    kickoff_utc=kickoff,
                    home=home,
                    away=away,
                    markets=parsed_markets,
                    is_live=bool(event.get("liveNow")),
                ))
            
            await asyncio.sleep(TOTO_RATE_LIMIT_DELAY)
        
        logger.info(f"TOTO: Fetched {len(results)} events for {league_key}")
        return results