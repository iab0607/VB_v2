"""League configurations for all supported competitions."""

LEAGUE_CONFIG = {
    # Netherlands
    "eredivisie": {
        "country": "Netherlands",
        "display_name": "Eredivisie",
        "priority": 1,
        "pinnacle_id": 1928,
        "jacks_path": "football/netherlands/eredivisie",
        "toto_id": "1176",
    },
    "keuken_kampioen_divisie": {
        "country": "Netherlands", 
        "display_name": "Keuken Kampioen Divisie",
        "priority": 1,
        "pinnacle_id": 1929,
        "jacks_path": "football/netherlands/eerste_divisie",
        "toto_id": "1053",
    },
    
    # England
    "premier_league": {
        "country": "England",
        "display_name": "Premier League",
        "priority": 1,
        "pinnacle_id": 1980,
        "jacks_path": "football/england/premier_league",
        "toto_id": "8",
    },
    "championship": {
        "country": "England",
        "display_name": "Championship",
        "priority": 2,
        "pinnacle_id": 2627,
        "jacks_path": "football/england/championship",
        "toto_id": "70",
    },
    
    # Germany
    "bundesliga": {
        "country": "Germany",
        "display_name": "Bundesliga",
        "priority": 1,
        "pinnacle_id": 2196,
        "jacks_path": "football/germany/bundesliga",
        "toto_id": "35",
    },
    "2_bundesliga": {
        "country": "Germany",
        "display_name": "2. Bundesliga", 
        "priority": 2,
        "pinnacle_id": 6436,
        "jacks_path": "football/germany/2_bundesliga",
        "toto_id": "44",
    },
    
    # Spain
    "la_liga": {
        "country": "Spain",
        "display_name": "La Liga",
        "priority": 1,
        "pinnacle_id": 2627,
        "jacks_path": "football/spain/la_liga",
        "toto_id": "17",
    },
    
    # Italy
    "serie_a": {
        "country": "Italy",
        "display_name": "Serie A",
        "priority": 1,
        "pinnacle_id": 2436,
        "jacks_path": "football/italy/serie_a",
        "toto_id": "23",
    },
    
    # France
    "ligue_1": {
        "country": "France",
        "display_name": "Ligue 1",
        "priority": 1,
        "pinnacle_id": 2664,
        "jacks_path": "football/france/ligue_1",
        "toto_id": "34",
    },
    
    # Belgium
    "jupiler_pro_league": {
        "country": "Belgium",
        "display_name": "Jupiler Pro League",
        "priority": 2,
        "pinnacle_id": 2439,
        "jacks_path": "football/belgium/jupiler_pro_league",
        "toto_id": "9",
    },
    
    # Portugal
    "primeira_liga": {
        "country": "Portugal",
        "display_name": "Primeira Liga",
        "priority": 2,
        "pinnacle_id": 2411,
        "jacks_path": "football/portugal/primeira_liga",
        "toto_id": "42",
    },
}

def get_leagues_by_priority(min_priority: int = 1, max_priority: int = 2):
    """Get leagues filtered by priority."""
    return {
        key: config 
        for key, config in LEAGUE_CONFIG.items() 
        if min_priority <= config["priority"] <= max_priority
    }

def get_leagues_by_country(country: str):
    """Get all leagues for a specific country."""
    return {
        key: config 
        for key, config in LEAGUE_CONFIG.items() 
        if config["country"] == country
    }

def get_league_config(league_key: str):
    """Get configuration for a specific league."""
    return LEAGUE_CONFIG.get(league_key)