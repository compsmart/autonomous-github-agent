#!/usr/bin/env python3
"""
Autonomous AI Bug Fixer Agent - Main Entry Point

A simplified, modular AI agent that automatically:
1. Analyzes open GitHub issues
2. Fixes bugs using AI
3. Creates pull requests with fixes

Usage:
    python main.py [--config .env] [--repo owner/name] [--dry-run] [--limit N]
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add src directory to Python path for imports
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from src.core.agent import AutonomousBugFixer
from src.core.config import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bug_fixer.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Autonomous AI Bug Fixer Agent. Fixes open GitHub issues without existing open PRs.'
    )
    parser.add_argument(
        '--config', 
        default='.env', 
        help='Path to the .env configuration file (default: .env)'
    )
    parser.add_argument(
        '--repo', 
        help='Target repository in "owner/name" format (overrides .env settings)'
    )
    parser.add_argument(
        '--dry-run', 
        action='store_true',
        help='List issues that would be processed without making changes'
    )
    parser.add_argument(
        '--limit', 
        type=int, 
        help='Limit the number of issues to process in a single run'
    )
    parser.add_argument(
        '--fast',
        action='store_true',
        help='Use the fast Gemini Flash model instead of the Pro model for faster but potentially less accurate responses'
    )
    
    args = parser.parse_args()
    
    try:
        # Override repository from command line if provided
        if args.repo:
            if '/' not in args.repo:
                print("Error: --repo argument must be in 'owner/name' format.")
                sys.exit(1)
            owner, name = args.repo.split('/', 1)
            os.environ['REPO_OWNER'] = owner
            os.environ['REPO_NAME'] = name
            logger.info(f"Overriding repository from command line: {owner}/{name}")
          # Create and run agent
        agent = AutonomousBugFixer.from_config_file(args.config, use_fast_model=args.fast)
        agent.run(limit_issues=args.limit, dry_run=args.dry_run)
            
    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
        print(f"Error: {ve}")
        print("Please check your .env file or command line arguments.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
        print("Check bug_fixer.log for details.")
        sys.exit(1)


if __name__ == '__main__':
    main()
