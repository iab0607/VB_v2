"""
Pinnacle scraper (Arcadia API, class-based, compatible with main.py)

- Keeps the class architecture that main.py expects
- Uses Arcadia endpoints confirmed to work:
    * GET /leagues/{league_id}/matchups?brandId=0
    * GET /matchups/{parentId}/markets/related/straight?brandId=0
    * GET /matchups/{parentId}/markets/straight?brandId=0
- Avoids endpoints that returned 404 in diagnostics (e.g., /leagues, /matchups/{id}/markets)
- Exposes fetch_league_events(league_key) and fetch_events([...]) used by your pipeline
- Uses hardcoded headers, API key, and user agent
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

# Known Arcadia league IDs (fill out as you expand coverage).
# Eredivisie/Keuken Kampioen confirmed; add others when you have IDs.
LEAGUES: Dict[str, Optional[int]] = {
    # Netherlands
    "eredivisie": 1928,
    "keuken_kampioen_divisie": 1929,

    # Fill these with real Arcadia IDs when available:
    "premier_league": None,
    "championship": None,
    "bundesliga": None,
    "2_bundesliga": None,
    "la_liga": None,
    "serie_a": None,
    "ligue_1": None,
    "jupiler_pro_league": None,
    "primeira_liga": None,
}

HEADERS = {
    "X-API-Key": "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0",
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


# ---------------- Scraper ----------------

class PinnacleScraper:
    """Hybrid Pinnacle odds scraper using Arcadia guest API."""

    def __init__(self, http: HttpClient):
        self.http = http
        self.headers = HEADERS

    async def test_connection(self) -> bool:
        """
        Use a known-good endpoint to avoid false "offline" warnings.
        Diagnostics showed that /leagues/1928/matchups?brandId=0 returns 200.
        """
        try:
            url = f"{ARCADIA}/leagues/1928/matchups"
            res = await self.http.get(url, params={"brandId": str(BRAND_ID)}, headers=self.headers)
            return bool(res)
        except Exception as e:
            logger.warning(f"[Pinnacle] Connection test failed: {e}")
            return False

    # -------- Low-level API calls --------

    async def _fetch_league_matchups(self, league_id: int) -> List[dict]:
        """Fetch matchups (events) for a league id."""
        url = f"{ARCADIA}/leagues/{league_id}/matchups"
        data = await self.http.get(url, params={"brandId": str(BRAND_ID)}, headers=self.headers)
        if not data:
            return []
        # API may return a dict with "matchups" or "events", or a plain list
        if isinstance(data, dict):
            if isinstance(data.get("matchups"), list):
                return data["matchups"]
            if isinstance(data.get("events"), list):
                return data["events"]
        if isinstance(data, list):
            return data
        return []

    async def _fetch_parent_markets(self, parent_id: int) -> List[dict]:
        """
        Only use endpoints that returned 200 in diagnostics:
        - /markets/related/straight
        - /markets/straight
        """
        params = {"brandId": str(BRAND_ID)}
        for path in (
            f"{ARCADIA}/matchups/{parent_id}/markets/related/straight",
            f"{ARCADIA}/matchups/{parent_id}/markets/straight",
        ):
            data = await self.http.get(path, params=params, headers=self.headers)
            if isinstance(data, dict) and "markets" in data:
                return data.get("markets") or []
            if isinstance(data, list):
                return data
        return []

    # -------- Parsing --------

    def parse_markets(self, mkts: List[dict]) -> Dict[str, Dict]:
        """Parse Pinnacle markets to standardized keys."""
        out: Dict[str, Dict] = {}

        for m in mkts:
            mtype = (m.get("type") or "").lower()
            prices = m.get("prices") or []

            # 1X2 / Moneyline (3-way)
            if mtype in ("moneyline", "three_way_moneyline", "match_result", "result", "1x2"):
                three: Dict[str, float] = {}
                for pr in prices:
                    des = (pr.get("designation") or "").lower()
                    dec = american_to_decimal(pr.get("price"))
                    if not dec:
                        continue
                    if des in ("home", "1", "h"):
                        three["home"] = dec
                    elif des in ("draw", "x"):
                        three["draw"] = dec
                    elif des in ("away", "2", "a"):
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

        return out

    # -------- Public API used by main.py --------

    async def fetch_league_events(self, league_key: str) -> List[UnifiedEvent]:
        """
        Fetch events (with markets) for a single league key, e.g. 'eredivisie'.
        This method name/signature is called by main.py.
        """
        lid = LEAGUES.get(league_key)
        if not lid:
            logger.warning(f"[Pinnacle] No Arcadia ID for {league_key}")
            return []

        events: List[UnifiedEvent] = []
        matchups = await self._fetch_league_matchups(lid)
        if not isinstance(matchups, list) or not matchups:
            return events

        tasks, catalog = [], []
        seen_parent: set[str] = set()
        for ev in matchups:
            parent_id = ev.get("parentId") or ev.get("id")
            if not parent_id:
                continue
            pid = str(parent_id)
            if pid in seen_parent:
                continue
            seen_parent.add(pid)
            catalog.append((league_key, ev, pid))
            tasks.append(self._fetch_parent_markets(int(parent_id)))

        market_sets = await asyncio.gather(*tasks, return_exceptions=True)

        for (comp, ev, pid), mkts in zip(catalog, market_sets):
            if not isinstance(mkts, list):
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

            events.append(
                UnifiedEvent(
                    provider="pinnacle",
                    provider_event_id=pid,
                    league=comp,
                    country="Netherlands",  # Adjust per league if you later add multi-country coverage
                    kickoff_utc=kickoff,
                    home=home,
                    away=away,
                    markets=markets,
                    is_live=bool(ev.get("isLive")),
                )
            )

        return events

    async def fetch_events(self, competitions: List[str]) -> List[UnifiedEvent]:
        """
        Batch variant: fetch events for multiple league keys. Kept for convenience.
        main.py can keep calling fetch_league_events per league; this is optional.
        """
        results: List[UnifiedEvent] = []
        tasks = [self.fetch_league_events(comp) for comp in competitions]
        batches = await asyncio.gather(*tasks, return_exceptions=True)
        for batch in batches:
            if isinstance(batch, list):
                results.extend(batch)
        return results
