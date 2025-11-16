"""Event matching across providers."""
import logging
from typing import List, Tuple
from core.models import UnifiedEvent
from matching.team_normalizer import normalize_team_name, team_similarity
from utils.datetime_utils import parse_datetime, within_time_window
from config.settings import MATCH_TIME_TOLERANCE_MINUTES, TEAM_SIMILARITY_THRESHOLD

logger = logging.getLogger(__name__)

class EventMatcher:
    """Match events across different providers."""
    
    @classmethod
    def match_events(
        cls, 
        left: List[UnifiedEvent], 
        right: List[UnifiedEvent],
        time_tolerance_minutes: int = MATCH_TIME_TOLERANCE_MINUTES,
        min_similarity: float = TEAM_SIMILARITY_THRESHOLD
    ) -> List[Tuple[UnifiedEvent, UnifiedEvent]]:
        """
        Match events from two providers based on teams and kickoff time.
        Uses fuzzy matching as fallback for team names.
        """
        matches = []
        used_indices = set()
        
        for left_event in left:
            try:
                left_kickoff = parse_datetime(left_event.kickoff_utc)
                left_home = normalize_team_name(left_event.home)
                left_away = normalize_team_name(left_event.away)
                
                candidates = []
                for idx, right_event in enumerate(right):
                    if idx in used_indices or right_event.league != left_event.league:
                        continue
                    
                    right_home = normalize_team_name(right_event.home)
                    right_away = normalize_team_name(right_event.away)
                    
                    # Exact match check
                    exact_match = (left_home == right_home and left_away == right_away)
                    
                    # Fuzzy match as fallback
                    home_sim = team_similarity(left_home, right_home)
                    away_sim = team_similarity(left_away, right_away)
                    avg_similarity = (home_sim + away_sim) / 2
                    
                    if exact_match or avg_similarity >= min_similarity:
                        right_kickoff = parse_datetime(right_event.kickoff_utc)
                        if within_time_window(left_kickoff, right_kickoff, time_tolerance_minutes):
                            time_diff = abs((right_kickoff - left_kickoff).total_seconds())
                            # Prioritize exact matches (lower score = better)
                            score = time_diff if exact_match else time_diff + 1000
                            candidates.append((idx, right_event, score, exact_match, avg_similarity))
                
                if candidates:
                    best_idx, best_event, _, is_exact, similarity = min(candidates, key=lambda x: x[2])
                    used_indices.add(best_idx)
                    matches.append((left_event, best_event))
                    
                    if not is_exact:
                        logger.debug(
                            f"Fuzzy match: {left_event.home} vs {left_event.away} "
                            f"<-> {best_event.home} vs {best_event.away} "
                            f"(similarity: {similarity:.2f})"
                        )
            except Exception as e:
                logger.warning(f"Error matching event {left_event.home} vs {left_event.away}: {e}")
                continue
        
        logger.info(f"Matched {len(matches)} events between providers")
        return matches