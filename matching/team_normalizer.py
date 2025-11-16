"""Team name normalization for consistent matching across providers."""
import re
import unicodedata
from difflib import SequenceMatcher

def strip_accents(text: str) -> str:
    """Remove accents from unicode characters."""
    return "".join(c for c in unicodedata.normalize("NFD", text) 
                   if unicodedata.category(c) != "Mn")

# Comprehensive team aliases database
TEAM_ALIASES = {
    # Netherlands - Eredivisie
    "ajax": "ajax", "afc ajax": "ajax", "ajax amsterdam": "ajax",
    "psv": "psv", "psv eindhoven": "psv",
    "feyenoord": "feyenoord", "feyenoord rotterdam": "feyenoord",
    "az": "az", "az alkmaar": "az",
    "fc twente": "fc twente", "twente": "fc twente", "twente enschede": "fc twente",
    "fc utrecht": "fc utrecht", "utrecht": "fc utrecht",
    "sc heerenveen": "sc heerenveen", "heerenveen": "sc heerenveen",
    "nac breda": "nac breda", "nac": "nac breda",
    "rkc waalwijk": "rkc waalwijk", "rkc": "rkc waalwijk",
    "pec zwolle": "pec zwolle", "zwolle": "pec zwolle",
    "go ahead eagles": "go ahead eagles", "ga eagles": "go ahead eagles",
    "fortuna sittard": "fortuna sittard", "fortuna": "fortuna sittard",
    "sparta rotterdam": "sparta rotterdam", "sparta": "sparta rotterdam",
    "heracles almelo": "heracles almelo", "heracles": "heracles almelo",
    "willem ii": "willem ii", "willem ii tilburg": "willem ii",
    "nec nijmegen": "nec nijmegen", "nec": "nec nijmegen", "n e c nijmegen": "nec nijmegen",
    "fc groningen": "fc groningen", "groningen": "fc groningen",
    "almere city": "almere city", "almere city fc": "almere city",
    "excelsior": "excelsior", "excelsior rotterdam": "excelsior", "sbv excelsior": "excelsior",
    
    # Netherlands - Keuken Kampioen Divisie
    "fc eindhoven": "fc eindhoven", "eindhoven": "fc eindhoven",
    "fc den bosch": "fc den bosch", "den bosch": "fc den bosch",
    "fc dordrecht": "fc dordrecht", "dordrecht": "fc dordrecht",
    "fc emmen": "fc emmen", "emmen": "fc emmen",
    "fc volendam": "fc volendam", "volendam": "fc volendam",
    "de graafschap": "de graafschap", "graafschap": "de graafschap",
    "sc cambuur": "sc cambuur", "cambuur": "sc cambuur", "cambuur leeuwarden": "sc cambuur",
    "mvv maastricht": "mvv maastricht", "mvv": "mvv maastricht",
    "ado den haag": "ado den haag", "ado": "ado den haag",
    "helmond sport": "helmond sport", "helmond": "helmond sport",
    "telstar": "telstar", "sc telstar": "telstar",
    "top oss": "top oss", "oss": "top oss",
    "vvv venlo": "vvv venlo", "vvv-venlo": "vvv venlo", "venlo": "vvv venlo",
    "roda jc": "roda jc", "roda jc kerkrade": "roda jc", "roda": "roda jc",
    
    # Jong teams
    "jong ajax": "jong ajax", "ajax ii": "jong ajax",
    "jong psv": "jong psv", "psv ii": "jong psv",
    "jong az": "jong az", "az ii": "jong az",
    "jong fc utrecht": "jong fc utrecht", "fc utrecht ii": "jong fc utrecht",
    
    # England - Premier League
    "manchester united": "manchester united", "man united": "manchester united", "man utd": "manchester united",
    "manchester city": "manchester city", "man city": "manchester city",
    "liverpool": "liverpool", "liverpool fc": "liverpool",
    "chelsea": "chelsea", "chelsea fc": "chelsea",
    "arsenal": "arsenal", "arsenal fc": "arsenal",
    "tottenham": "tottenham", "tottenham hotspur": "tottenham", "spurs": "tottenham",
    "newcastle": "newcastle", "newcastle united": "newcastle",
    "aston villa": "aston villa", "villa": "aston villa",
    "brighton": "brighton", "brighton & hove albion": "brighton", "brighton and hove albion": "brighton",
    "west ham": "west ham", "west ham united": "west ham",
    "everton": "everton", "everton fc": "everton",
    "crystal palace": "crystal palace", "palace": "crystal palace",
    "fulham": "fulham", "fulham fc": "fulham",
    "brentford": "brentford", "brentford fc": "brentford",
    "nottingham forest": "nottingham forest", "notts forest": "nottingham forest", "forest": "nottingham forest",
    "wolverhampton": "wolverhampton", "wolves": "wolverhampton", "wolverhampton wanderers": "wolverhampton",
    "bournemouth": "bournemouth", "afc bournemouth": "bournemouth",
    "leicester": "leicester", "leicester city": "leicester",
    "southampton": "southampton", "southampton fc": "southampton",
    "leeds": "leeds", "leeds united": "leeds",
    "ipswich": "ipswich", "ipswich town": "ipswich",
    
    # Germany - Bundesliga
    "bayern munich": "bayern munich", "bayern": "bayern munich", "fc bayern munchen": "bayern munich",
    "borussia dortmund": "borussia dortmund", "dortmund": "borussia dortmund", "bvb": "borussia dortmund",
    "rb leipzig": "rb leipzig", "leipzig": "rb leipzig",
    "bayer leverkusen": "bayer leverkusen", "leverkusen": "bayer leverkusen",
    "union berlin": "union berlin", "fc union berlin": "union berlin",
    "freiburg": "freiburg", "sc freiburg": "freiburg",
    "eintracht frankfurt": "eintracht frankfurt", "frankfurt": "eintracht frankfurt",
    "vfl wolfsburg": "vfl wolfsburg", "wolfsburg": "vfl wolfsburg",
    "borussia monchengladbach": "borussia monchengladbach", "monchengladbach": "borussia monchengladbach", "gladbach": "borussia monchengladbach",
    "vfb stuttgart": "vfb stuttgart", "stuttgart": "vfb stuttgart",
    "werder bremen": "werder bremen", "bremen": "werder bremen",
    "hoffenheim": "hoffenheim", "tsg hoffenheim": "hoffenheim",
    "fc augsburg": "fc augsburg", "augsburg": "fc augsburg",
    "mainz": "mainz", "fsv mainz 05": "mainz", "mainz 05": "mainz",
    "fc koln": "fc koln", "koln": "fc koln", "cologne": "fc koln",
    "hertha berlin": "hertha berlin", "hertha bsc": "hertha berlin",
    
    # Spain - La Liga
    "real madrid": "real madrid", "madrid": "real madrid",
    "barcelona": "barcelona", "fc barcelona": "barcelona", "barca": "barcelona",
    "atletico madrid": "atletico madrid", "atletico": "atletico madrid",
    "sevilla": "sevilla", "sevilla fc": "sevilla",
    "real sociedad": "real sociedad", "sociedad": "real sociedad",
    "real betis": "real betis", "betis": "real betis",
    "villarreal": "villarreal", "villarreal cf": "villarreal",
    "athletic bilbao": "athletic bilbao", "athletic": "athletic bilbao", "athletic club": "athletic bilbao",
    "valencia": "valencia", "valencia cf": "valencia",
    "getafe": "getafe", "getafe cf": "getafe",
    "osasuna": "osasuna", "ca osasuna": "osasuna",
    "rayo vallecano": "rayo vallecano", "rayo": "rayo vallecano",
    "celta vigo": "celta vigo", "celta": "celta vigo",
    "mallorca": "mallorca", "rcd mallorca": "mallorca",
    "girona": "girona", "girona fc": "girona",
    "las palmas": "las palmas", "ud las palmas": "las palmas",
    "alaves": "alaves", "deportivo alaves": "alaves",
    
    # Italy - Serie A
    "juventus": "juventus", "juve": "juventus",
    "inter": "inter", "inter milan": "inter", "internazionale": "inter",
    "ac milan": "ac milan", "milan": "ac milan",
    "napoli": "napoli", "ssc napoli": "napoli",
    "roma": "roma", "as roma": "roma",
    "lazio": "lazio", "ss lazio": "lazio",
    "atalanta": "atalanta", "atalanta bc": "atalanta",
    "fiorentina": "fiorentina", "acf fiorentina": "fiorentina",
    "torino": "torino", "torino fc": "torino",
    "bologna": "bologna", "bologna fc": "bologna",
    "udinese": "udinese", "udinese calcio": "udinese",
    "sassuolo": "sassuolo", "us sassuolo": "sassuolo",
    "monza": "monza", "ac monza": "monza",
    "lecce": "lecce", "us lecce": "lecce",
    "cagliari": "cagliari", "cagliari calcio": "cagliari",
    "hellas verona": "hellas verona", "verona": "hellas verona",
    "salernitana": "salernitana", "us salernitana": "salernitana",
    "empoli": "empoli", "empoli fc": "empoli",
    
    # France - Ligue 1
    "psg": "psg", "paris saint germain": "psg", "paris sg": "psg",
    "marseille": "marseille", "om": "marseille", "olympique marseille": "marseille",
    "lyon": "lyon", "olympique lyon": "lyon", "olympique lyonnais": "lyon",
    "monaco": "monaco", "as monaco": "monaco",
    "lille": "lille", "losc lille": "lille",
    "rennes": "rennes", "stade rennais": "rennes",
    "nice": "nice", "ogc nice": "nice",
    "lens": "lens", "rc lens": "lens",
    "strasbourg": "strasbourg", "rc strasbourg": "strasbourg",
    "montpellier": "montpellier", "montpellier hsc": "montpellier",
    "nantes": "nantes", "fc nantes": "nantes",
    "reims": "reims", "stade reims": "reims",
    "toulouse": "toulouse", "toulouse fc": "toulouse",
    "brest": "brest", "stade brestois": "brest",
    "le havre": "le havre", "le havre ac": "le havre",
    "lorient": "lorient", "fc lorient": "lorient",
    "clermont": "clermont", "clermont foot": "clermont",
    "metz": "metz", "fc metz": "metz",
}

def normalize_team_name(name: str) -> str:
    """
    Normalize team name for consistent matching.
    Handles various formats, prefixes, and special characters.
    """
    if not name:
        return ""
    
    # Basic normalization
    normalized = strip_accents(name.lower().strip())
    normalized = re.sub(r"[.\-–—/']", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    
    # Direct lookup
    if normalized in TEAM_ALIASES:
        return TEAM_ALIASES[normalized]
    
    # Try without common prefixes
    without_prefix = re.sub(r'^(fc|sc|bv|sv|vv|afc|rk|pk|cf|us|ac|as|ssc|rc|og|ca|ud|rcd)\s+', '', normalized)
    if without_prefix in TEAM_ALIASES:
        return TEAM_ALIASES[without_prefix]
    
    # Try without city/country suffixes
    without_suffix = re.sub(r'\s+(fc|united|city|town|rovers|wanderers|athletic|hotspur|albion|calcio|amsterdam|rotterdam|nl)$', '', normalized)
    if without_suffix in TEAM_ALIASES:
        return TEAM_ALIASES[without_suffix]
    
    # Return normalized version if no alias found
    return normalized

def team_similarity(name1: str, name2: str) -> float:
    """Calculate similarity score between team names (0-1)."""
    return SequenceMatcher(None, name1, name2).ratio()