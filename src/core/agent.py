"""
Main autonomous bug fixer agent controller
"""
import logging
import sys
from typing import Optional

from .config import Config, ConfigLoader
from .bug_fixer_service import BugFixerService
from .code_review_service import CodeReviewService
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
        
        # Create separate GitHub client for code reviews if token is provided
        if config.github_codereview_token and config.github_codereview_token != config.github_token:
            self.github_review_client = GitHubClient(
                token=config.github_codereview_token,
                repo_owner=config.repo_owner,
                repo_name=config.repo_name
            )
            logger.info("Using separate GitHub token for code reviews")
        else:
            self.github_review_client = self.github_client
            logger.info("Using main GitHub token for code reviews")
            
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
        
        self.code_review_service = CodeReviewService(
            github_client=self.github_client,
            ai_client=self.ai_client
        )
        
        # Store the review client separately for the service to use
        self.code_review_service.review_client = self.github_review_client
        
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

    def review_pull_requests(self, limit_prs: Optional[int] = None, dry_run: bool = False):
        """Review open pull requests autonomously"""
        logger.info("Starting Code Review Mode")
        try:
            pull_requests = self.github_client.get_open_pull_requests()
            if not pull_requests:
                logger.info("No open pull requests found for review")
                return
            if dry_run:
                self._print_dry_run_pr_results(pull_requests, limit_prs)
                return
            if limit_prs and limit_prs > 0:
                if len(pull_requests) > limit_prs:
                    logger.info(f"Limiting to first {limit_prs} pull requests")
                    pull_requests = pull_requests[:limit_prs]
            logger.info(f"Found {len(pull_requests)} pull requests to review")
            results = self.code_review_service.review_pull_requests(limit_prs)
            self._print_review_summary(results, self.config.repo_full_name)
        except Exception as e:
            logger.error(f"Fatal error in code review: {e}")
        finally:
            logger.info("Code review finished")

    def _print_dry_run_pr_results(self, pull_requests, limit_prs):
        print("\n--- DRY RUN MODE (Code Review) ---")
        print(f"Repository: {self.config.repo_full_name}")
        if pull_requests:
            display_count = min(len(pull_requests), limit_prs) if limit_prs else len(pull_requests)
            print(f"\nFound {len(pull_requests)} open pull requests that would be reviewed:")
            print(f"Showing first {display_count} pull requests:")
            for i, pr in enumerate(pull_requests[:display_count]):
                print(f"  {i+1}. PR #{pr.number}: {pr.title}")
                print(f"     URL: {pr.url}")
            if limit_prs and len(pull_requests) > limit_prs:
                print(f"  ...and {len(pull_requests) - limit_prs} more pull requests")
        else:
            print("No open pull requests found that meet the criteria for review.")
        print("--- END OF DRY RUN ---")

    def _print_review_summary(self, results, repo_full_name):
        print("\n--- CODE REVIEW SUMMARY ---")
        print(f"Repository: {repo_full_name}")
        if not results:
            print("No pull requests were reviewed.")
            return
        for result in results:
            status = "SUCCESS" if result.success else "FAILED"
            print(f"PR #{result.pr_number}: {status}")
            if result.review_url:
                print(f"  Review URL: {result.review_url}")
            if result.error_message:
                print(f"  Error: {result.error_message}")
        print("--- END OF SUMMARY ---")
