"""
Main autonomous bug fixer agent controller
"""
import logging
import sys
from typing import Optional

from .config import Config, ConfigLoader
from .bug_fixer_service import BugFixerService
from ..clients.github_client import GitHubClient
from ..clients.ai_client import AIClient
from ..utils.git_operations import GitOperations

logger = logging.getLogger(__name__)


class AutonomousBugFixer:
    """
    Autonomous AI Bug Fixer Agent
    
    This agent works completely independently to fix bugs in any repository.
    """
    
    def __init__(self, config: Config):
        self.config = config
        
        # Initialize clients
        self.github_client = GitHubClient(
            token=config.github_token,
            repo_owner=config.repo_owner,
            repo_name=config.repo_name
        )        
        self.ai_client = AIClient(
            api_key=config.gemini_api_key,
            system_instructions=config.system_instructions or "",
            use_fast_model=config.use_fast_model
        )
        
        self.git_ops = GitOperations(
            repo_url=config.repo_url,
            github_token=config.github_token
        )
        
        self.bug_fixer_service = BugFixerService(
            github_client=self.github_client,
            ai_client=self.ai_client,
            git_ops=self.git_ops
        )
        
        logger.info(f"Autonomous Bug Fixer initialized for {config.repo_full_name}")    
    @classmethod
    def from_config_file(cls, config_file: str = '.env', use_fast_model: bool = False) -> 'AutonomousBugFixer':
        """Create agent from configuration file"""
        config = ConfigLoader.load_from_env(config_file, use_fast_model)
        return cls(config)
    
    def run(self, limit_issues: Optional[int] = None, dry_run: bool = False):
        """Main execution method - fix all bugs autonomously"""
        logger.info("Starting Autonomous Bug Fixer Agent")
        
        try:
            # Setup workspace
            self.git_ops.setup_workspace()
            if not self.git_ops.repo_path:
                logger.error("Workspace setup failed")
                return

            # Get open issues that qualify for fixing
            issues_to_fix = self.github_client.get_open_issues()
            if not issues_to_fix:
                logger.info("No open issues found that qualify for fixing")
                return
            
            if dry_run:
                self._print_dry_run_results(issues_to_fix, limit_issues)
                return
            
            # Apply limit if specified
            if limit_issues and limit_issues > 0:
                if len(issues_to_fix) > limit_issues:
                    logger.info(f"Limiting to first {limit_issues} issues")
                    issues_to_fix = issues_to_fix[:limit_issues]
            
            logger.info(f"Found {len(issues_to_fix)} issues to process")
            
            # Fix bugs
            results = self.bug_fixer_service.fix_multiple_bugs(issues_to_fix, limit_issues)
            
            # Print summary
            self.bug_fixer_service.print_summary(results, self.config.repo_full_name)
            
        except Exception as e:
            logger.error(f"Fatal error in agent run: {e}")
        finally:
            logger.info("Cleaning up workspace...")
            self.git_ops.cleanup_workspace()
            logger.info("Agent run finished")
    
    def _print_dry_run_results(self, issues, limit_issues):
        """Print dry run results"""
        print("\n--- DRY RUN MODE ---")
        print(f"Repository: {self.config.repo_full_name}")
        
        if issues:
            display_count = min(len(issues), limit_issues) if limit_issues else len(issues)
            print(f"\nFound {len(issues)} open issues that would be processed:")
            print(f"Showing first {display_count} issues:")
            
            for i, issue in enumerate(issues[:display_count]):
                print(f"  {i+1}. Issue #{issue.number}: {issue.title}")
                print(f"     URL: {issue.url}")
                print(f"     Labels: {', '.join(issue.labels) if issue.labels else 'None'}")
                print()
                
            if limit_issues and len(issues) > limit_issues:
                print(f"  ...and {len(issues) - limit_issues} more issues")
        else:
            print("No open issues found that meet the criteria for processing.")
        
        print("--- END OF DRY RUN ---")
