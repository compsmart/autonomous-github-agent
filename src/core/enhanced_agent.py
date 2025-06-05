"""
Enhanced autonomous bug fixer agent controller
This version uses targeted fixes instead of complete file replacement
"""
import logging
import sys
from typing import Optional

from .config import Config, ConfigLoader
from .enhanced_bug_fixer_service import EnhancedBugFixerService
from .code_review_service import CodeReviewService
from ..clients.github_client import GitHubClient
from ..clients.enhanced_ai_client_v2 import EnhancedAIClient
from ..utils.enhanced_git_operations import EnhancedGitOperations

logger = logging.getLogger(__name__)


class EnhancedAutonomousBugFixer:
    """
    Enhanced Autonomous AI Bug Fixer Agent
    
    This agent uses targeted fixes to preserve existing functionality
    while precisely fixing specific bugs.
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
            
        # Initialize enhanced AI client
        self.ai_client = EnhancedAIClient(
            api_key=config.gemini_api_key,
            system_instructions=config.system_instructions or "",
            use_fast_model=config.use_fast_model
        )
        
        # Initialize enhanced git operations
        repo_url = f"https://github.com/{config.repo_owner}/{config.repo_name}.git"
        self.git_ops = EnhancedGitOperations(repo_url, config.github_token)
        
        # Initialize enhanced services
        self.bug_fixer_service = EnhancedBugFixerService(
            self.github_client, 
            self.ai_client, 
            self.git_ops
        )
        
        self.code_review_service = CodeReviewService(
            self.github_review_client, 
            self.ai_client
        )
        
        logger.info("Enhanced Autonomous Bug Fixer initialized successfully")

    def run(self, issue_limit: Optional[int] = None, dry_run: bool = False) -> dict:
        """
        Run the enhanced autonomous bug fixer
        
        Args:
            issue_limit: Maximum number of issues to process (None for all)
            dry_run: If True, analyze issues but don't make changes
        
        Returns:
            Dictionary with execution results
        """
        try:
            logger.info("🚀 Starting Enhanced Autonomous Bug Fixer")
            logger.info(f"Repository: {self.config.repo_owner}/{self.config.repo_name}")
            logger.info(f"Dry run: {dry_run}")
            logger.info(f"Issue limit: {issue_limit or 'unlimited'}")
            
            # Step 1: Setup workspace
            if not dry_run:
                workspace_path = self.git_ops.setup_workspace()
                logger.info(f"✅ Workspace setup complete: {workspace_path}")
              # Step 2: Get open issues (with limit applied early)
            logger.info("📋 Fetching open issues...")
            open_issues = self.github_client.get_open_issues(limit=issue_limit)
            
            if not open_issues:
                logger.info("No open issues found")
                return {
                    'success': True,
                    'issues_processed': 0,
                    'issues_fixed': 0,
                    'message': 'No open issues to process'
                }
            
            logger.info(f"Found {len(open_issues)} open issues to process")
            
            if dry_run:
                logger.info("🔍 DRY RUN - Analyzing issues only (no changes will be made)")
                for issue in open_issues:
                    logger.info(f"Would process: #{issue.number} - {issue.title}")
                return {
                    'success': True,
                    'issues_processed': len(open_issues),
                    'issues_fixed': 0,
                    'message': f'Dry run completed - {len(open_issues)} issues analyzed'
                }
            
            # Step 3: Fix bugs with enhanced approach
            logger.info("🛠️ Starting enhanced bug fixing process...")
            fix_results = self.bug_fixer_service.fix_multiple_bugs(open_issues)
            
            # Step 4: Generate summary
            successful_fixes = [r for r in fix_results if r.success]
            failed_fixes = [r for r in fix_results if not r.success]
            
            logger.info("📊 Enhanced Bug Fixing Summary:")
            logger.info(f"   Total issues processed: {len(fix_results)}")
            logger.info(f"   Successfully fixed: {len(successful_fixes)}")
            logger.info(f"   Failed to fix: {len(failed_fixes)}")
            
            if successful_fixes:
                logger.info("✅ Successfully fixed issues:")
                for result in successful_fixes:
                    logger.info(f"   #{result.issue_number}: {len(result.files_modified)} files modified")
            
            if failed_fixes:
                logger.info("❌ Failed to fix issues:")
                for result in failed_fixes:
                    logger.info(f"   #{result.issue_number}: {result.error_message}")
            
            # Step 5: Cleanup
            if not dry_run:
                self.git_ops.cleanup_workspace()
                logger.info("🧹 Workspace cleaned up")
            
            return {
                'success': True,
                'issues_processed': len(fix_results),
                'issues_fixed': len(successful_fixes),
                'successful_fixes': [r.issue_number for r in successful_fixes],
                'failed_fixes': [(r.issue_number, r.error_message) for r in failed_fixes],
                'message': f'Enhanced processing complete: {len(successful_fixes)}/{len(fix_results)} issues fixed'
            }
            
        except Exception as e:
            logger.error(f"💥 Enhanced bug fixer execution failed: {e}")
            
            # Cleanup on error
            try:
                if hasattr(self, 'git_ops'):
                    self.git_ops.cleanup_workspace()
            except:
                pass
            
            return {
                'success': False,
                'issues_processed': 0,
                'issues_fixed': 0,
                'error': str(e),
                'message': f'Execution failed: {e}'
            }

    def run_code_reviews(self, pr_limit: Optional[int] = None) -> dict:
        """
        Run automated code reviews on recent pull requests
        
        Args:
            pr_limit: Maximum number of PRs to review (None for all recent)
        
        Returns:
            Dictionary with review results
        """
        try:
            logger.info("🔍 Starting Enhanced Code Review Process")
            
            # Get recent pull requests for review
            recent_prs = self.github_client.get_recent_pull_requests(limit=pr_limit or 10)
            
            if not recent_prs:
                logger.info("No recent pull requests found for review")
                return {
                    'success': True,
                    'prs_reviewed': 0,
                    'message': 'No recent PRs to review'
                }
            
            logger.info(f"Found {len(recent_prs)} recent pull requests to review")
              # Perform code reviews
            review_results = []
            for pr in recent_prs:
                try:
                    result = self.code_review_service.review_pull_request(pr)
                    review_results.append(result)
                    logger.info(f"Reviewed PR #{pr.number}: {result.get('status', 'unknown')}")
                except Exception as e:
                    logger.error(f"Failed to review PR #{pr.number}: {e}")
                    review_results.append({'pr_number': pr.number, 'status': 'error', 'error': str(e)})
            
            successful_reviews = [r for r in review_results if r.get('status') == 'success']
            
            logger.info(f"📊 Code Review Summary: {len(successful_reviews)}/{len(review_results)} PRs reviewed successfully")
            
            return {
                'success': True,
                'prs_reviewed': len(review_results),
                'successful_reviews': len(successful_reviews),
                'results': review_results,
                'message': f'Code review complete: {len(successful_reviews)}/{len(review_results)} PRs reviewed'
            }
            
        except Exception as e:
            logger.error(f"Code review execution failed: {e}")
            return {
                'success': False,
                'prs_reviewed': 0,
                'error': str(e),
                'message': f'Code review failed: {e}'
            }
    @classmethod
    def from_config_file(cls, config_path: str, use_fast_model: bool = False) -> 'EnhancedAutonomousBugFixer':
        """Create enhanced agent from configuration file"""
        config_loader = ConfigLoader()
        config = config_loader.load_from_env_file(config_path, use_fast_model)
        return cls(config)
