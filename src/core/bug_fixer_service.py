"""
Main bug fixer service that orchestrates the bug fixing process
"""
import time
import logging
from typing import List, Optional
from datetime import datetime

from ..models.bug_models import BugIssue, FixResult, FixAnalysis
from ..clients.github_client import GitHubClient
from ..clients.ai_client import AIClient
from ..utils.git_operations import GitOperations
from ..utils.codebase_analyzer import CodebaseAnalyzer

logger = logging.getLogger(__name__)


class BugFixerService:
    """Main service for fixing bugs autonomously"""
    
    def __init__(self, github_client: GitHubClient, ai_client: AIClient, git_ops: GitOperations):
        self.github_client = github_client
        self.ai_client = ai_client
        self.git_ops = git_ops
        self.codebase_analyzer: Optional[CodebaseAnalyzer] = None
    
    def fix_single_bug(self, issue: BugIssue) -> FixResult:
        """Fix a single bug issue"""
        logger.info(f"Attempting to fix issue #{issue.number}: {issue.title}")
        
        branch_name = f"fix-issue-{issue.number}-{int(time.time())}"
        default_branch = self.git_ops.get_default_branch()
        
        try:
            # Step 1: Create feature branch
            self.git_ops.create_feature_branch(branch_name, default_branch)
            logger.info(f"Created feature branch: {branch_name}")
              # Step 2: Analyze the bug with AI
            if not self.codebase_analyzer:
                if not self.git_ops.repo_path:
                    raise Exception("Repository path not set")
                self.codebase_analyzer = CodebaseAnalyzer(self.git_ops.repo_path)
            
            codebase_info = self.codebase_analyzer.analyze()
            fix_analysis = self.ai_client.analyze_bug_and_generate_fix(
                issue, 
                codebase_info, 
                self.github_client.repo_owner, 
                self.github_client.repo_name
            )
            
            if not fix_analysis or not fix_analysis.is_valid():
                self.git_ops.cleanup_failed_branch(branch_name, default_branch)
                error_msg = "Failed to analyze bug with AI or AI response invalid"
                logger.error(error_msg)
                return FixResult(
                    issue_number=issue.number,
                    success=False,
                    branch_name=branch_name,
                    files_modified=[],
                    commit_message="",
                    error_message=error_msg
                )
            
            # Step 3: Apply the fix
            files_modified = self.git_ops.apply_file_changes(fix_analysis.files_to_modify)
            
            if not files_modified:
                self.git_ops.cleanup_failed_branch(branch_name, default_branch)
                return FixResult(
                    issue_number=issue.number,
                    success=False,
                    branch_name=branch_name,
                    files_modified=[],
                    commit_message="",
                    error_message="No files were modified by AI fix attempt"
                )
            
            # Step 4: Commit changes
            commit_message = self._generate_commit_message(issue, fix_analysis)
            self.git_ops.commit_changes(commit_message, files_modified)
            logger.info(f"Committed changes for issue #{issue.number}")
            
            # Step 5: Push branch
            self.git_ops.push_branch(branch_name)
            logger.info(f"Pushed branch {branch_name}")
            
            # Step 6: Create pull request
            pr_url = self._create_pull_request(issue, branch_name, fix_analysis, default_branch)
            
            if pr_url:
                logger.info(f"Created pull request: {pr_url}")
            else:
                logger.error(f"Failed to create PR for issue #{issue.number}")

            return FixResult(
                issue_number=issue.number,
                success=True,
                branch_name=branch_name,
                files_modified=files_modified,
                commit_message=commit_message,
                pr_url=pr_url
            )
            
        except Exception as e:
            logger.error(f"Failed to fix issue #{issue.number}: {e}")
            self.git_ops.cleanup_failed_branch(branch_name, default_branch)
            return FixResult(
                issue_number=issue.number,
                success=False,
                branch_name=branch_name,
                files_modified=[],
                commit_message="",
                error_message=str(e)
            )
    
    def fix_multiple_bugs(self, issues: List[BugIssue], limit: Optional[int] = None) -> List[FixResult]:
        """Fix multiple bug issues"""
        if limit and len(issues) > limit:
            issues = issues[:limit]
            logger.info(f"Limited to first {limit} issues")
        
        results = []
        default_branch = self.git_ops.get_default_branch()
        
        for i, issue in enumerate(issues, 1):
            logger.info(f"--- Processing issue {i}/{len(issues)}: #{issue.number} ---")
            
            # Ensure clean state before each fix
            self.git_ops.ensure_clean_default_branch(default_branch)
            
            # Fix the issue
            result = self.fix_single_bug(issue)
            results.append(result)
            
            if result.success:
                logger.info(f"[SUCCESS] Fixed issue #{issue.number}")
            else:
                logger.error(f"[FAILED] Failed to fix issue #{issue.number}: {result.error_message}")
            
            # Brief pause between fixes
            if i < len(issues):
                time.sleep(10)
        
        return results
    
    def _generate_commit_message(self, issue: BugIssue, fix_analysis: FixAnalysis) -> str:
        """Generate commit message for the fix"""
        title = self._generate_commit_title(issue)
        return f"Fix: #{issue.number} {title}\n\n{fix_analysis.explanation}\n\nRelated to issue: {issue.url}"
    
    def _generate_commit_title(self, issue: BugIssue) -> str:
        """Generate a concise commit title from issue"""
        title = issue.title
        
        # Clean up common prefixes
        prefixes_to_remove = ["bug:", "bug -", "fix:", "fix -", "issue:", "issue -"]
        for prefix in prefixes_to_remove:
            if title.lower().startswith(prefix):
                title = title[len(prefix):].strip()
        
        # Limit length
        max_len = 60
        if len(title) > max_len:
            title = title[:max_len-3] + "..."
        
        # Capitalize first letter
        if title:
            title = title[0].upper() + title[1:]
        else:
            title = f"Address issue {issue.number}"
            
        return title
    
    def _create_pull_request(self, issue: BugIssue, branch_name: str, fix_analysis: FixAnalysis, base_branch: str) -> Optional[str]:
        """Create a pull request for the fix"""
        pr_title = f"Fix #{issue.number}: {self._generate_commit_title(issue)}"
        
        # Construct PR body
        pr_body_parts = [
            f"## Automated Bug Fix for Issue #{issue.number}",
            f"**Closes:** #{issue.number}",
            f"**Issue URL:** {issue.url}",
            "\n### Problem Description:",
            f"> {issue.body.strip() if issue.body else 'No detailed description provided.'}",
            "\n### AI Analysis & Fix:",
            f"**Analysis:** {fix_analysis.analysis}",
            f"**Root Cause:** {fix_analysis.root_cause}",
            f"**Fix Strategy:** {fix_analysis.fix_strategy}",
            f"**Explanation:** {fix_analysis.explanation}",
        ]

        if fix_analysis.files_to_modify:
            pr_body_parts.append("\n### Files Modified:")
            for f_item in fix_analysis.files_to_modify:
                pr_body_parts.append(f"- `{f_item.get('file', 'Unknown file')}`")
        
        pr_body_parts.append("\n---\n*This pull request was generated automatically by the AI Bug Fixer Agent.*")
        pr_body = "\n".join(pr_body_parts)

        return self.github_client.create_pull_request(pr_title, branch_name, base_branch, pr_body)
    
    def print_summary(self, results: List[FixResult], repo_full_name: str):
        """Print summary of all bug fixes"""
        if not results:
            print("\nNo issues were processed in this run.")
            return

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print("\n" + "="*80)
        print("AUTONOMOUS BUG FIXER - RUN SUMMARY")
        print("="*80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Repository: {repo_full_name}")
        print(f"Total Issues Processed: {len(results)}")
        print(f"Successfully Fixed: {len(successful)}")
        print(f"Failed to Fix: {len(failed)}")
        print("-" * 80)
        
        if successful:
            print("\nSUCCESSFUL FIXES:")
            for result in successful:
                print(f"  [SUCCESS] Issue #{result.issue_number}")
                print(f"     Branch: {result.branch_name}")
                print(f"     Files Modified: {', '.join(result.files_modified) if result.files_modified else 'None'}")
                print(f"     Commit: \"{result.commit_message.splitlines()[0]}\"")
                if result.pr_url:
                    print(f"     Pull Request: {result.pr_url}")
                else:
                    print(f"     Pull Request: Creation failed")
                print()
        
        if failed:
            print("\nFAILED FIXES:")
            for result in failed:
                print(f"  [FAILED] Issue #{result.issue_number}")
                print(f"     Branch: {result.branch_name}")
                print(f"     Error: {result.error_message}")
                print()
        
        print("="*80)
        print("Summary complete. Check logs for detailed information.")
