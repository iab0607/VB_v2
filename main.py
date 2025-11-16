"""
Value Betting System - Production Version
Main application entry point
"""
import asyncio
import argparse
import logging
import time
from pathlib import Path

# Core imports
from core.http_client import HttpClient
from config.settings import (
    HTTP_TIMEOUT, HTTP_CONCURRENCY, HTTP_RETRIES,
    MINIMUM_EDGE_THRESHOLD, OUTPUT_DIR, LOGS_DIR
)
from config.leagues import get_leagues_by_priority

# Scrapers
from scrapers.pinnacle import PinnacleScraper
from scrapers.jacks import JacksScraper
from scrapers.toto import TotoScraper

# Analysis
from analysis.value_analyzer import ValueAnalyzer

# Storage
from storage.output_manager import OutputManager

# Utils
from utils.logging_config import setup_logging, log_performance_metric

logger = logging.getLogger(__name__)

async def scrape_provider(scraper, leagues: list, provider_name: str):
    """Scrape all leagues for a single provider."""
    start_time = time.time()
    all_events = []
    
    for league in leagues:
        try:
            events = await scraper.fetch_league_events(league)
            all_events.extend(events)
        except Exception as e:
            logger.error(f"{provider_name} - {league}: {e}")
    
    duration = time.time() - start_time
    log_performance_metric(f"{provider_name}_scrape_time", duration, "seconds")
    
    return all_events

async def main(args):
    """Main application logic."""
    # Setup
    session_timestamp = setup_logging("valuebet")
    output_manager = OutputManager()
    
    # Create output directories
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    Path(LOGS_DIR).mkdir(exist_ok=True)
    
    logger.info("=" * 100)
    logger.info("VALUE BETTING SYSTEM - Production Version")
    logger.info("=" * 100)
    
    # Get leagues to scrape
    leagues_config = get_leagues_by_priority(min_priority=1, max_priority=args.max_priority)
    league_keys = list(leagues_config.keys())
    
    logger.info(f"Scraping {len(league_keys)} leagues: {', '.join(league_keys)}")
    logger.info(f"Minimum edge threshold: {args.min_edge*100:.1f}%")
    logger.info(f"Bankroll: €{args.bankroll}")
    
    start_time = time.time()
    
    async with HttpClient(timeout=HTTP_TIMEOUT, concurrency=HTTP_CONCURRENCY, retries=HTTP_RETRIES) as http:
        # Initialize scrapers
        pinnacle = PinnacleScraper(http)
        jacks = JacksScraper(http)
        toto = TotoScraper(http)
        
        logger.info("\n📊 Starting data collection from providers...")
        
        # Test Pinnacle connection
        pinnacle_online = await pinnacle.test_connection()
        if not pinnacle_online:
            logger.warning("⚠️  Pinnacle API appears to be offline or blocked")
        
        # Scrape all providers concurrently
        scrape_tasks = [
            scrape_provider(pinnacle, league_keys, "Pinnacle"),
            scrape_provider(jacks, league_keys, "Jacks"),
            scrape_provider(toto, league_keys, "TOTO"),
        ]
        
        results = await asyncio.gather(*scrape_tasks, return_exceptions=True)
        
        pinnacle_events = results[0] if not isinstance(results[0], Exception) else []
        jacks_events = results[1] if not isinstance(results[1], Exception) else []
        toto_events = results[2] if not isinstance(results[2], Exception) else []
    
    scrape_duration = time.time() - start_time
    log_performance_metric("total_scrape_time", scrape_duration, "seconds")
    
    # Save raw data
    logger.info("\n💾 Saving raw data...")
    output_manager.save_events("pinnacle", pinnacle_events)
    output_manager.save_events("jacks", jacks_events)
    output_manager.save_events("toto", toto_events)
    
    # Summary
    logger.info("\n" + "=" * 100)
    logger.info("DATA COLLECTION SUMMARY")
    logger.info("=" * 100)
    logger.info(f"Pinnacle: {len(pinnacle_events)} events")
    logger.info(f"Jack's:   {len(jacks_events)} events")
    logger.info(f"TOTO:     {len(toto_events)} events")
    logger.info(f"Duration: {scrape_duration:.1f} seconds")
    
    # Value analysis
    if not pinnacle_events:
        logger.error("\n❌ No Pinnacle events available - cannot calculate value bets (need anchor)")
        return
    
    logger.info("\n💰 Analyzing value opportunities...")
    analysis_start = time.time()
    
    value_bets = ValueAnalyzer.generate_value_bets(
        anchor_events=pinnacle_events,
        soft_books={"jacks": jacks_events, "toto": toto_events},
        min_edge=args.min_edge,
        bankroll=args.bankroll
    )
    
    analysis_duration = time.time() - analysis_start
    log_performance_metric("analysis_time", analysis_duration, "seconds")
    
    # Save results
    output_manager.save_value_bets_json(value_bets)
    output_manager.save_value_bets_csv(value_bets)
    
    # Print summary
    logger.info(f"\n✅ Found {len(value_bets)} value bets above {args.min_edge*100:.1f}% edge")
    
    if value_bets:
        output_manager.print_summary(value_bets, top_n=args.top_n)
        
        # Calculate aggregate statistics
        total_ev = sum(bet.expected_value for bet in value_bets)
        avg_edge = sum(bet.edge_percentage for bet in value_bets) / len(value_bets)
        total_stake = sum(bet.recommended_stake for bet in value_bets)
        
        logger.info("\n" + "=" * 100)
        logger.info("PORTFOLIO STATISTICS")
        logger.info("=" * 100)
        logger.info(f"Total Opportunities: {len(value_bets)}")
        logger.info(f"Average Edge: {avg_edge:.2f}%")
        logger.info(f"Total Recommended Stake: €{total_stake:.2f}")
        logger.info(f"Total Expected Value: €{total_ev:.2f}")
        logger.info(f"Expected ROI: {(total_ev/total_stake*100):.2f}%")
    
    # Final summary
    total_duration = time.time() - start_time
    log_performance_metric("total_runtime", total_duration, "seconds")
    
    logger.info("\n" + "=" * 100)
    logger.info("📁 Output saved to:")
    logger.info(f"   {Path(OUTPUT_DIR).absolute()}/")
    logger.info("   - pinnacle.json (raw data)")
    logger.info("   - jacks.json (raw data)")
    logger.info("   - toto.json (raw data)")
    logger.info("   - value_bets.json (analysis results)")
    logger.info("   - value_bets.csv (Excel-ready)")
    logger.info(f"\n📊 Logs saved to:")
    logger.info(f"   {Path(LOGS_DIR).absolute()}/")
    logger.info(f"   - valuebet_{session_timestamp}.log (main log)")
    logger.info(f"   - edge_tracking_{session_timestamp}.log (edge analysis)")
    logger.info(f"   - performance_{session_timestamp}.log (performance metrics)")
    logger.info("=" * 100)
    logger.info(f"\n⏱️  Total runtime: {total_duration:.1f} seconds")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Value Betting System")
    
    parser.add_argument(
        "--min-edge",
        type=float,
        default=MINIMUM_EDGE_THRESHOLD,
        help=f"Minimum edge threshold (default: {MINIMUM_EDGE_THRESHOLD*100:.1f}%%)"
    )
    
    parser.add_argument(
        "--bankroll",
        type=float,
        default=1000.0,
        help="Bankroll for stake calculations (default: €1000)"
    )
    
    parser.add_argument(
        "--max-priority",
        type=int,
        default=2,
        help="Maximum league priority to scrape (1=top leagues, 2=includes secondary, default: 2)"
    )
    
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top bets to display (default: 10)"
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    asyncio.run(main(args))