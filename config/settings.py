"""Application settings and configuration."""
import os

# Directories
OUTPUT_DIR = "output"
LOGS_DIR = "logs"

# HTTP Settings
HTTP_TIMEOUT = 25
HTTP_CONCURRENCY = 12
HTTP_RETRIES = 2

# Matching Settings
MATCH_TIME_TOLERANCE_MINUTES = 12
TEAM_SIMILARITY_THRESHOLD = 0.85

# Value Betting Settings
MINIMUM_EDGE_THRESHOLD = 0.025  # 2.5% minimum edge
KELLY_FRACTION = 0.25  # Quarter Kelly (conservative)
MAX_STAKE_PERCENTAGE = 0.05  # Max 5% of bankroll per bet

# Edge Tracking Settings
TRACK_CLOSING_LINE_VALUE = True
STORE_HISTORICAL_ODDS = True

# Logging
DEBUG_MODE = os.getenv("DEBUG", "0") == "1"
VERBOSE = True

# Provider Settings
PINNACLE_API_KEY = "CmX2KcMrXuFmNg6YFbmTxE0y9CIrOi0R"

# Rate Limiting
TOTO_RATE_LIMIT_DELAY = 0.2  # seconds between requests

# Market Settings
SUPPORTED_MARKETS = ["1x2", "ou_2_5", "btts"]