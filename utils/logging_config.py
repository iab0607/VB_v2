"""Logging configuration for edge tracking and analysis."""
import logging
import sys
from pathlib import Path
from datetime import datetime
from config.settings import LOGS_DIR, DEBUG_MODE

def setup_logging(session_name: str = "valuebet"):
    """Setup structured logging for the application."""
    
    # Create logs directory
    Path(LOGS_DIR).mkdir(exist_ok=True)
    
    # Create timestamp for this session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler - INFO level
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler - DEBUG level for main log
    main_log_file = Path(LOGS_DIR) / f"{session_name}_{timestamp}.log"
    file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Edge tracking logger - separate file for analysis
    edge_logger = logging.getLogger('edge_tracker')
    edge_logger.setLevel(logging.INFO)
    edge_logger.propagate = False  # Don't propagate to root
    
    edge_log_file = Path(LOGS_DIR) / f"edge_tracking_{timestamp}.log"
    edge_handler = logging.FileHandler(edge_log_file, encoding='utf-8')
    edge_handler.setLevel(logging.INFO)
    edge_formatter = logging.Formatter(
        '%(asctime)s|%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    edge_handler.setFormatter(edge_formatter)
    edge_logger.addHandler(edge_handler)
    
    # Performance logger
    perf_logger = logging.getLogger('performance')
    perf_logger.setLevel(logging.INFO)
    perf_logger.propagate = False
    
    perf_log_file = Path(LOGS_DIR) / f"performance_{timestamp}.log"
    perf_handler = logging.FileHandler(perf_log_file, encoding='utf-8')
    perf_handler.setLevel(logging.INFO)
    perf_formatter = logging.Formatter(
        '%(asctime)s|%(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    perf_handler.setFormatter(perf_formatter)
    perf_logger.addHandler(perf_handler)
    
    logging.info(f"Logging initialized - Session: {session_name}_{timestamp}")
    logging.info(f"Main log: {main_log_file}")
    logging.info(f"Edge tracking log: {edge_log_file}")
    
    return timestamp

def log_edge_opportunity(
    league: str,
    match: str,
    bookmaker: str,
    market: str,
    outcome: str,
    soft_odds: float,
    anchor_odds: float,
    edge_pct: float,
    recommended_stake: float,
    ev: float
):
    """Log an edge opportunity in structured format for analysis."""
    logger = logging.getLogger('edge_tracker')
    logger.info(
        f"{league}|{match}|{bookmaker}|{market}|{outcome}|"
        f"{soft_odds:.3f}|{anchor_odds:.3f}|{edge_pct:.2f}|"
        f"{recommended_stake:.2f}|{ev:.2f}"
    )

def log_performance_metric(metric_name: str, value: float, unit: str = ""):
    """Log performance metrics."""
    logger = logging.getLogger('performance')
    logger.info(f"{metric_name}|{value:.3f}|{unit}")