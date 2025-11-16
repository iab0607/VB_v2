"""
Pinnacle scraper (Arcadia API, class-based, compatible with main.py)

- Uses dynamic league discovery via /sports/{sport_id}/leagues endpoint with all=true
- Fetches ALL leagues and iterates over ALL league IDs
- Uses robust error handling per league to prevent early termination
- Uses Arcadia endpoints confirmed to work:
    * GET /sports/{sport_id}/leagues?all=true&brandId=0
    * GET /leagues/{league_id}/matchups?brandId=0
    * GET /matchups/{parentId}/markets/related/straight?brandId=0
    * GET /matchups/{parentId}/markets/straight?brandId=0
- Exposes fetch_league_events(league_key) and fetch_events([...]) used by your pipeline
- Uses hardcoded headers, API key, and user agent
- Adds detailed INFO logging to diagnose zero-event situations
"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple, Any

from core.models import UnifiedEvent
from core.http_client import HttpClient
from utils.datetime_utils import normalize_iso_datetime

logger = logging.getLogger(__name__)

ARCADIA = "https://guest.api.arcadia.pinnacle.com/0.1"
BRAND_ID = 0  # required by Arcadia guest API
SPORT_ID = 29  # Soccer/Football sport ID

HEADERS = {
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Linux; Android) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "Referer": "https://www.pinnacle.com/",
    "X-Device-UUID": "1a0d9901-387642a9-a10b0cb6-71185001",
}

# League name mapping (slug -> exact API names to match)
# CRITICAL: Must match EXACTLY to avoid corners/bookings/wrong leagues
LEAGUE_PATTERNS: Dict[str, List[str]] = {
    # Netherlands
    "eredivisie": ["netherlands - eredivisie"],
    "keuken_kampioen_divisie": ["netherlands - eerste divisie"],
    
    # England
    "premier_league": ["england - premier league"],
    "championship": ["england - championship"],
    
    # Germany
    "bundesliga": ["germany - bundesliga"],
    "2_bundesliga": ["germany - 2. bundesliga"],
    
    # Spain
    "la_liga": ["spain - la liga"],
    
    # Italy
    "serie_a": ["italy - serie a"],
    
    # France
    "ligue_1": ["france - ligue 1"],
    
    # Belgium
    "jupiler_pro_league": ["belgium - jupiler pro league"],
    
    # Portugal
    "primeira_liga": ["portugal - liga portugal", "portugal - primeira liga"],
}


# ---------------- Utilities ----------------

def calculate_margin(odds_map: Dict[str, float]) -> float:
    """Calculate bookmaker overround (percentage)."""
    implied = [1.0 / v for v in odds_map.values() if v and v > 1.0]
    return round((sum(implied) - 1.0) * 100.0, 3) if implied else 0.0


def american_to_decimal(px: Any) -> Optional[float]:
    """Convert American price to decimal odds; be tolerant of str/float."""
    if px is None or px == "":
        return None
    try:
        p = int(px)
    except Exception:
        try:
            p = int(float(px))
        except Exception:
            return None
    if p > 0:
        return round(1.0 + p / 100.0, 3)
    if p < 0:
        return round(1.0 + 100.0 / abs(p), 3)
    return None


def extract_home_away(ev: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract home/away from event with multiple possible shapes."""
    parent = ev.get("parent") or {}
    parts = parent.get("participants") or []
    home, away = None, None
    for p in parts:
        al = (p.get("alignment") or "").lower()
        if al == "home":
            home = p.get("name")
        elif al == "away":
            away = p.get("name")
    if not home:
        home = ev.get("home") or ev.get("homeTeam") or ev.get("team1")
    if not away:
        away = ev.get("away") or ev.get("awayTeam") or ev.get("team2")
    return home, away


def match_league_name(api_name: str, patterns: List[str]) -> bool:
    """
    Check if API league name EXACTLY matches our patterns.
    Must be exact match to avoid corners/bookings/wrong leagues.
    """
    api_lower = api_name.lower().strip()
    
    for pattern in patterns:
        pattern_lower = pattern.lower().strip()
        
        # Exact match
        if api_lower == pattern_lower:
            return True
        
        # Allow slight variations but exclude corners/bookings/special markets
        if pattern_lower in api_lower:
            # Exclude special markets
            exclusions = ["corner", "booking", "card", "penalty", "throw", "goal kick", 
                         "offsides", "women", "youth", "u19", "u21", "u23", "reserve"]
            if any(excl in api_lower for excl in exclusions):
                return False
            return True
    
    return False


# ---------------- Scraper ----------------

class PinnacleScraper:
    """Hybrid Pinnacle odds scraper using Arcadia guest API with dynamic league discovery."""

    def __init__(self, http: HttpClient):
        self.http = http
        self.headers = HEADERS
        self.league_cache: Dict[str, Optional[int]] = {}  # league_key -> league_id mapping
        self.all_leagues_cache: Optional[List[dict]] = None  # Cache all leagues

    async def test_connection(self) -> bool:
        """Test connection by fetching available leagues."""
        try:
            url = f"{ARCADIA}/sports/{SPORT_ID}/leagues"
            res = await self.http.get(
                url, 
                params={"all": "true", "brandId": str(BRAND_ID)}, 
                headers=self.headers
            )
            ok = bool(res)
            logger.info(f"[Pinnacle] test_connection -> {ok}")
            return ok
        except Exception as e:
            logger.warning(f"[Pinnacle] Connection test failed: {e}")
            return False

    # -------- Dynamic League Discovery --------

    async def _fetch_all_leagues(self) -> List[dict]:
        """Fetch ALL available soccer leagues from the API using all=true."""
        # Return cached leagues if available
        if self.all_leagues_cache is not None:
            return self.all_leagues_cache
        
        url = f"{ARCADIA}/sports/{SPORT_ID}/leagues"
        params = {"all": "true", "brandId": str(BRAND_ID)}  # CRITICAL: all=true
        
        try:
            data = await self.http.get(url, params=params, headers=self.headers)
            if not data:
                logger.warning(f"[Pinnacle] No data returned from leagues endpoint")
                return []
            
            # Handle different response structures
            if isinstance(data, dict):
                leagues = data.get("leagues") or data.get("items") or []
            elif isinstance(data, list):
                leagues = data
            else:
                leagues = []
            
            logger.info(f"[Pinnacle] Found {len(leagues)} total leagues (all=true)")
            
            # Cache the result
            self.all_leagues_cache = leagues
            return leagues
        except Exception as e:
            logger.error(f"[Pinnacle] Error fetching leagues: {e}")
            return []

    async def _resolve_league_id(self, league_key: str) -> Optional[int]:
        """Resolve a league key to its Pinnacle league ID."""
        # Check cache first
        if league_key in self.league_cache:
            return self.league_cache[league_key]
        
        # Fetch all available leagues
        leagues = await self._fetch_all_leagues()
        
        # Try to match the league key to an available league
        patterns = LEAGUE_PATTERNS.get(league_key, [league_key])
        
        for league in leagues:
            league_name = league.get("name") or ""
            league_id = league.get("id") or league.get("leagueId")
            
            if match_league_name(league_name, patterns):
                logger.info(f"[Pinnacle] Matched '{league_key}' to '{league_name}' (id={league_id})")
                self.league_cache[league_key] = league_id
                return league_id
        
        logger.warning(f"[Pinnacle] Could not find league ID for '{league_key}'. Available leagues logged below.")
        # Log some league names to help with debugging
        sample_names = [lg.get("name", "?") for lg in leagues[:20]]
        logger.debug(f"[Pinnacle] Sample league names: {sample_names}")
        
        self.league_cache[league_key] = None
        return None

    async def fetch_all_league_ids(self) -> List[Tuple[int, str]]:
        """
        Fetch ALL league IDs from Pinnacle.
        Returns list of (league_id, league_name) tuples.
        """
        leagues = await self._fetch_all_leagues()
        result = []
        for league in leagues:
            league_id = league.get("id") or league.get("leagueId")
            league_name = league.get("name") or "Unknown"
            if league_id:
                result.append((league_id, league_name))
        logger.info(f"[Pinnacle] Extracted {len(result)} league IDs for scraping")
        return result

    # -------- Low-level API calls with robust error handling --------

    async def _fetch_league_matchups_safe(self, league_id: int, league_name: str = "") -> List[dict]:
        """
        Fetch matchups for a league with error handling.
        Returns empty list on failure, never raises.
        """
        try:
            url = f"{ARCADIA}/leagues/{league_id}/matchups"
            data = await self.http.get(url, params={"brandId": str(BRAND_ID)}, headers=self.headers)
            
            if not data:
                logger.debug(f"[Pinnacle] No matchups for league {league_id} ({league_name})")
                return []
            
            # API may return a dict with "matchups" or "events", or a plain list
            if isinstance(data, dict):
                if isinstance(data.get("matchups"), list):
                    items = data["matchups"]
                elif isinstance(data.get("events"), list):
                    items = data["events"]
                else:
                    items = []
            elif isinstance(data, list):
                items = data
            else:
                items = []
            
            if items:
                logger.info(f"[Pinnacle] League {league_id} ({league_name}): {len(items)} matchups")
            return items
            
        except Exception as e:
            logger.warning(f"[Pinnacle] Failed to fetch matchups for league {league_id} ({league_name}): {e}")
            return []

    async def _fetch_parent_markets_safe(self, parent_id: int) -> List[dict]:
        """
        Fetch markets for a parent with error handling.
        Returns empty list on failure, never raises.
        """
        try:
            params = {"brandId": str(BRAND_ID)}
            for path in (
                f"{ARCADIA}/matchups/{parent_id}/markets/related/straight",
                f"{ARCADIA}/matchups/{parent_id}/markets/straight",
            ):
                try:
                    data = await self.http.get(path, params=params, headers=self.headers)
                    if isinstance(data, dict) and "markets" in data:
                        mkts = data.get("markets") or []
                        if mkts:
                            return mkts
                    if isinstance(data, list) and data:
                        return data
                except Exception as e:
                    logger.debug(f"[Pinnacle] Market fetch failed for {parent_id} via {path}: {e}")
                    continue
            return []
        except Exception as e:
            logger.debug(f"[Pinnacle] Failed to fetch markets for parent {parent_id}: {e}")
            return []

    # -------- Parsing --------

    def parse_markets(self, mkts: List[dict]) -> Dict[str, Dict]:
        """Parse Pinnacle markets to standardized keys."""
        out: Dict[str, Dict] = {}

        for m in mkts:
            try:
                mtype = (m.get("type") or m.get("marketType") or "").lower()
                prices = m.get("prices") or m.get("outcomes") or []

                # 1X2 / Moneyline (3-way)
                if mtype in ("moneyline", "three_way_moneyline", "match_result", "result", "1x2", "s;0ou"):
                    three: Dict[str, float] = {}
                    for pr in prices:
                        des = (pr.get("designation") or pr.get("type") or "").lower()
                        dec = american_to_decimal(pr.get("price") or pr.get("decimal"))
                        if not dec:
                            continue
                        if des in ("home", "1", "h", "team1"):
                            three["home"] = dec
                        elif des in ("draw", "x", "tie"):
                            three["draw"] = dec
                        elif des in ("away", "2", "a", "team2"):
                            three["away"] = dec
                    if set(three.keys()) == {"home", "draw", "away"}:
                        out["1x2"] = {**three, "margin": calculate_margin(three)}
                    continue

                # Over/Under 2.5 (totals)
                if mtype in ("totals", "goal_total", "match_total", "total_goals"):
                    over = next((x for x in prices if (x.get("designation") or "").lower() == "over"), None)
                    under = next((x for x in prices if (x.get("designation") or "").lower() == "under"), None)
                    pts = (over or {}).get("points")
                    if pts is None:
                        pts = (under or {}).get("points")
                    try:
                        pts_val = float(pts) if pts is not None else None
                    except Exception:
                        pts_val = None
                    if pts_val is not None and abs(pts_val - 2.5) < 1e-6:
                        two: Dict[str, float] = {}
                        if over:
                            d = american_to_decimal(over.get("price"))
                            if d:
                                two["over"] = d
                        if under:
                            d = american_to_decimal(under.get("price"))
                            if d:
                                two["under"] = d
                        if set(two.keys()) == {"over", "under"}:
                            out["ou_2_5"] = {**two, "line": 2.5, "margin": calculate_margin(two)}
                    continue

                # BTTS (Both Teams To Score)
                if mtype in ("both_teams_to_score", "both_teams_to_score_regular_time", "btts", "btts_regular_time"):
                    two: Dict[str, float] = {}
                    for pr in prices:
                        des = (pr.get("designation") or "").lower()
                        d = american_to_decimal(pr.get("price"))
                        if not d:
                            continue
                        if des in ("yes", "y"):
                            two["yes"] = d
                        elif des in ("no", "n"):
                            two["no"] = d
                    if set(two.keys()) == {"yes", "no"}:
                        out["btts"] = {**two, "margin": calculate_margin(two)}
                    continue
            except Exception as e:
                logger.debug(f"[Pinnacle] Error parsing market: {e}")
                continue

        return out

    # -------- Public API used by main.py --------

    async def fetch_league_events(self, league_key: str) -> List[UnifiedEvent]:
        """
        Fetch events (with markets) for a single league key, e.g. 'eredivisie'.
        This method name/signature is called by main.py.
        Uses robust error handling to prevent early termination.
        """
        try:
            # Dynamically resolve league ID
            lid = await self._resolve_league_id(league_key)
            if not lid:
                logger.warning(f"[Pinnacle] No Arcadia ID found for '{league_key}'")
                return []

            logger.info(f"[Pinnacle] Fetching league '{league_key}' (id={lid})")
            matchups = await self._fetch_league_matchups_safe(lid, league_key)
            
            if not matchups:
                logger.info(f"[Pinnacle] No matchups for league '{league_key}' (id={lid})")
                return []

            events: List[UnifiedEvent] = []
            tasks, catalog = [], []
            seen_parent: set[str] = set()

            for ev in matchups:
                try:
                    parent_id = ev.get("parentId") or ev.get("id")
                    if not parent_id:
                        continue
                    pid = str(parent_id)
                    if pid in seen_parent:
                        continue
                    seen_parent.add(pid)
                    catalog.append((league_key, ev, pid))
                    tasks.append(self._fetch_parent_markets_safe(int(parent_id)))
                except Exception as e:
                    logger.debug(f"[Pinnacle] Error processing matchup: {e}")
                    continue

            if not tasks:
                logger.info(f"[Pinnacle] No valid parent IDs for league '{league_key}'")
                return []

            logger.info(f"[Pinnacle] League '{league_key}': requesting markets for {len(catalog)} parents")
            market_sets = await asyncio.gather(*tasks, return_exceptions=True)

            with_markets = 0
            appended = 0

            for (comp, ev, pid), mkts in zip(catalog, market_sets):
                try:
                    if isinstance(mkts, Exception):
                        logger.debug(f"[Pinnacle] Exception for parent {pid}: {mkts}")
                        continue
                    
                    if not isinstance(mkts, list) or not mkts:
                        continue
                    
                    with_markets += 1
                    markets = self.parse_markets(mkts)
                    
                    # Even if markets dict is empty, continue trying other events
                    if not markets:
                        continue

                    parent = ev.get("parent") or {}
                    start = (
                        parent.get("startTime")
                        or ev.get("startTime")
                        or ev.get("start")
                        or ev.get("kickoff")
                        or ""
                    )
                    kickoff = normalize_iso_datetime(start)
                    home, away = extract_home_away(ev)
                    
                    if not (home and away and kickoff):
                        continue

                    events.append(
                        UnifiedEvent(
                            provider="pinnacle",
                            provider_event_id=pid,
                            league=comp,
                            country="Netherlands",  # TODO: Extract from league info if available
                            kickoff_utc=kickoff,
                            home=home,
                            away=away,
                            markets=markets,
                            is_live=bool(ev.get("isLive")),
                        )
                    )
                    appended += 1
                except Exception as e:
                    logger.debug(f"[Pinnacle] Error processing event {pid}: {e}")
                    continue

            logger.info(
                f"[Pinnacle] League '{league_key}': matchups={len(matchups)}, "
                f"with_markets={with_markets}, emitted={appended}"
            )

            return events
        
        except Exception as e:
            logger.error(f"[Pinnacle] Critical error in fetch_league_events('{league_key}'): {e}")
            return []

    async def fetch_events(self, competitions: List[str]) -> List[UnifiedEvent]:
        """
        Batch variant: fetch events for multiple league keys.
        Uses robust error handling - one league failure won't stop others.
        """
        results: List[UnifiedEvent] = []
        
        # Process each league independently with error isolation
        for comp in competitions:
            try:
                logger.info(f"[Pinnacle] Processing league: {comp}")
                events = await self.fetch_league_events(comp)
                if events:
                    results.extend(events)
                    logger.info(f"[Pinnacle] League '{comp}': added {len(events)} events")
                else:
                    logger.info(f"[Pinnacle] League '{comp}': no events found")
            except Exception as e:
                logger.error(f"[Pinnacle] Failed to process league '{comp}': {e}")
                continue  # Continue with next league
        
        logger.info(f"[Pinnacle] Total emitted events across all leagues: {len(results)}")
        return results

    async def fetch_all_events(self) -> List[UnifiedEvent]:
        """
        Fetch events from ALL available leagues on Pinnacle.
        Iterates over every league ID returned by the API.
        """
        logger.info("[Pinnacle] Starting full scrape of ALL leagues")
        
        # Get all league IDs
        league_ids = await self.fetch_all_league_ids()
        if not league_ids:
            logger.warning("[Pinnacle] No league IDs found")
            return []
        
        logger.info(f"[Pinnacle] Scraping {len(league_ids)} leagues")
        
        results: List[UnifiedEvent] = []
        
        # Process each league with full error isolation
        for league_id, league_name in league_ids:
            try:
                logger.info(f"[Pinnacle] Processing league_id={league_id} ({league_name})")
                matchups = await self._fetch_league_matchups_safe(league_id, league_name)
                
                if not matchups:
                    continue
                
                # Process matchups for this league
                tasks, catalog = [], []
                seen_parent: set[str] = set()
                
                for ev in matchups:
                    try:
                        parent_id = ev.get("parentId") or ev.get("id")
                        if not parent_id:
                            continue
                        pid = str(parent_id)
                        if pid in seen_parent:
                            continue
                        seen_parent.add(pid)
                        catalog.append((league_name, ev, pid))
                        tasks.append(self._fetch_parent_markets_safe(int(parent_id)))
                    except Exception as e:
                        logger.debug(f"[Pinnacle] Error processing matchup: {e}")
                        continue
                
                if not tasks:
                    continue
                
                market_sets = await asyncio.gather(*tasks, return_exceptions=True)
                
                for (league_display_name, ev, pid), mkts in zip(catalog, market_sets):
                    try:
                        if isinstance(mkts, Exception) or not isinstance(mkts, list) or not mkts:
                            continue
                        
                        markets = self.parse_markets(mkts)
                        if not markets:
                            continue
                        
                        parent = ev.get("parent") or {}
                        start = (
                            parent.get("startTime")
                            or ev.get("startTime")
                            or ev.get("start")
                            or ev.get("kickoff")
                            or ""
                        )
                        kickoff = normalize_iso_datetime(start)
                        home, away = extract_home_away(ev)
                        
                        if not (home and away and kickoff):
                            continue
                        
                        results.append(
                            UnifiedEvent(
                                provider="pinnacle",
                                provider_event_id=pid,
                                league=league_display_name,
                                country="Unknown",  # Could parse from league name
                                kickoff_utc=kickoff,
                                home=home,
                                away=away,
                                markets=markets,
                                is_live=bool(ev.get("isLive")),
                            )
                        )
                    except Exception as e:
                        logger.debug(f"[Pinnacle] Error creating event: {e}")
                        continue
                
            except Exception as e:
                logger.error(f"[Pinnacle] Error processing league {league_id} ({league_name}): {e}")
                continue  # Continue with next league
        
        logger.info(f"[Pinnacle] Full scrape complete: {len(results)} total events from {len(league_ids)} leagues")
        return results