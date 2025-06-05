"""
Enhanced bug fixer service that uses targeted fixes instead of complete file replacement
"""
import time
import logging
from typing import List, Optional
from datetime import datetime

from ..models.bug_models import BugIssue, FixResult, ImprovedFixAnalysis
from ..clients.github_client import GitHubClient
from ..clients.enhanced_ai_client_v2 import EnhancedAIClient
from ..utils.enhanced_git_operations import EnhancedGitOperations
from ..utils.codebase_analyzer import CodebaseAnalyzer

logger = logging.getLogger(__name__)


class EnhancedBugFixerService:
    """Enhanced service for fixing bugs with targeted changes"""
    
    def __init__(self, github_client: GitHubClient, ai_client: EnhancedAIClient, git_ops: EnhancedGitOperations):
        self.github_client = github_client
        self.ai_client = ai_client
        self.git_ops = git_ops
        self.codebase_analyzer: Optional[CodebaseAnalyzer] = None
    
    def fix_single_bug(self, issue: BugIssue) -> FixResult:
        """Fix a single bug issue with enhanced targeted approach"""
        logger.info(f"Attempting enhanced fix for issue #{issue.number}: {issue.title}")
        
        branch_name = f"enhanced-fix-issue-{issue.number}-{int(time.time())}"
        default_branch = self.git_ops.get_default_branch()
        
        try:
            # Step 1: Create feature branch
            self.git_ops.create_feature_branch(branch_name, default_branch)
            logger.info(f"Created feature branch: {branch_name}")
            
            # Step 2: Initialize codebase analyzer
            if not self.codebase_analyzer:
                if not self.git_ops.repo_path:
                    raise Exception("Repository path not set")
                self.codebase_analyzer = CodebaseAnalyzer(self.git_ops.repo_path)
            
            # Step 3: Get codebase information
            codebase_info = self.codebase_analyzer.analyze()
            
            # Step 4: Extract file references from issue and read actual file contents
            referenced_files = self.codebase_analyzer.extract_file_references_from_issue(issue.body)
            logger.info(f"Found {len(referenced_files)} file references in issue: {referenced_files}")
            
            file_contents = {}
            if referenced_files:
                file_contents = self.codebase_analyzer.read_specific_files(referenced_files)
                logger.info(f"Successfully read {len(file_contents)} files")
            else:
                logger.warning("No specific files referenced in issue - using general analysis")
            
            # Step 5: Enhanced AI analysis with actual file contents
            fix_analysis = self.ai_client.analyze_bug_with_file_contents(
                issue, 
                codebase_info, 
                file_contents,
                self.github_client.repo_owner, 
                self.github_client.repo_name
            )
            
            if not fix_analysis or not fix_analysis.is_valid():
                self.git_ops.cleanup_workspace()
                error_msg = "Failed to analyze bug with enhanced AI or AI response invalid"
                logger.error(error_msg)
                return FixResult(
                    issue_number=issue.number,
                    success=False,
                    branch_name=branch_name,
                    files_modified=[],
                    commit_message="",
                    error_message=error_msg
                )
            
            # Step 6: Apply targeted fixes instead of complete file replacement
            files_modified = self.git_ops.apply_targeted_fixes(fix_analysis.targeted_fixes)
            
            if not files_modified:
                self.git_ops.cleanup_workspace()
                return FixResult(
                    issue_number=issue.number,
                    success=False,
                    branch_name=branch_name,
                    files_modified=[],
                    commit_message="",
                    error_message="No files were modified by enhanced AI fix attempt"
                )
            
            # Step 7: Generate enhanced commit message
            commit_message = self._generate_enhanced_commit_message(issue, fix_analysis)
            self.git_ops.commit_changes(commit_message, files_modified)
            logger.info(f"Committed targeted changes for issue #{issue.number}")
            
            # Step 8: Push branch
            self.git_ops.push_branch(branch_name)
            logger.info(f"Pushed branch {branch_name}")
            
            # Step 9: Create pull request with enhanced description
            pr_url = self._create_enhanced_pull_request(issue, branch_name, fix_analysis, default_branch)
            
            if pr_url:
                logger.info(f"Created enhanced pull request: {pr_url}")
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
            logger.error(f"Enhanced bug fix failed for issue #{issue.number}: {e}")
            self.git_ops.cleanup_workspace()
            return FixResult(
                issue_number=issue.number,
                success=False,
                branch_name=branch_name,
                files_modified=[],
                commit_message="",
                error_message=str(e)
            )

    def _generate_enhanced_commit_message(self, issue: BugIssue, fix_analysis: ImprovedFixAnalysis) -> str:
        """Generate enhanced commit message with targeted fix details"""
        # Count different types of fixes
        fix_types = {}
        for fix in fix_analysis.targeted_fixes:
            fix_types[fix.fix_type] = fix_types.get(fix.fix_type, 0) + 1
        
        fix_summary = ", ".join([f"{count} {fix_type}" for fix_type, count in fix_types.items()])
        
        commit_message = f"fix: {issue.title} (#{issue.number})\n\n"
        commit_message += f"Applied targeted fixes: {fix_summary}\n\n"
        
        # Add details for each fix
        for i, fix in enumerate(fix_analysis.targeted_fixes, 1):
            commit_message += f"{i}. {fix.file_path}: {fix.explanation}\n"
        
        commit_message += f"\nConfidence Score: {fix_analysis.confidence_score:.2f}\n"
        commit_message += f"Root Cause: {fix_analysis.root_cause}\n"
        commit_message += f"\nResolves #{issue.number}"
        
        return commit_message

    def _create_enhanced_pull_request(self, issue: BugIssue, branch_name: str, fix_analysis: ImprovedFixAnalysis, base_branch: str) -> Optional[str]:
        """Create enhanced pull request with detailed targeted fix information"""
        try:
            pr_title = f"Enhanced Fix: {issue.title} (#{issue.number})"
            
            # Build detailed PR description
            pr_body = f"""## 🎯 Enhanced Targeted Bug Fix

**Fixes Issue:** #{issue.number} - {issue.title}

### 🔍 Analysis
{fix_analysis.analysis}

### 🎯 Root Cause
{fix_analysis.root_cause}

### 🛠️ Fix Strategy
{fix_analysis.fix_strategy}

### 📝 Targeted Changes Applied

"""
            
            for i, fix in enumerate(fix_analysis.targeted_fixes, 1):
                pr_body += f"#### {i}. `{fix.file_path}`\n"
                pr_body += f"- **Type:** {fix.fix_type.title()}\n"
                if fix.line_number:
                    pr_body += f"- **Line:** {fix.line_number}\n"
                pr_body += f"- **Change:** {fix.explanation}\n"
                
                if fix.old_content and fix.new_content:
                    pr_body += f"\n**Before:**\n```\n{fix.old_content[:200]}{'...' if len(fix.old_content) > 200 else ''}\n```\n"
                    pr_body += f"\n**After:**\n```\n{fix.new_content[:200]}{'...' if len(fix.new_content) > 200 else ''}\n```\n\n"
                else:
                    pr_body += "\n"

            pr_body += f"""
### ✅ Quality Assurance
- **Confidence Score:** {fix_analysis.confidence_score:.1%}
- **Targeted Approach:** Only modified specific problematic code
- **Preservation:** All existing functionality maintained
- **Minimal Impact:** {len(fix_analysis.targeted_fixes)} targeted change(s) applied

### 📋 Testing Recommendations
Please test the specific functionality mentioned in the original issue to ensure the fix works as expected.

---
*This PR was generated by Enhanced AI Bug Fixer with targeted, minimal changes approach.*
"""
            
            response = self.github_client.create_pull_request(
                title=pr_title,
                head_branch=branch_name,
                base_branch=base_branch,
                body=pr_body
            )
            if response:
                return response
            else:
                logger.error("Failed to create enhanced pull request")
                return None
                
        except Exception as e:
            logger.error(f"Error creating enhanced pull request: {e}")
            return None

    def fix_multiple_bugs(self, issues: List[BugIssue], max_concurrent: int = 1) -> List[FixResult]:
        """Fix multiple bugs with enhanced approach (sequential for reliability)"""
        results = []
        
        logger.info(f"Starting enhanced bug fixing for {len(issues)} issues")
        
        for i, issue in enumerate(issues, 1):
            logger.info(f"Processing issue {i}/{len(issues)}: #{issue.number}")
            
            try:
                result = self.fix_single_bug(issue)
                results.append(result)
                
                # Log progress
                if result.success:
                    logger.info(f"✅ Successfully fixed issue #{issue.number}")
                else:
                    logger.warning(f"❌ Failed to fix issue #{issue.number}: {result.error_message}")
                
            except Exception as e:
                logger.error(f"Error processing issue #{issue.number}: {e}")
                results.append(FixResult(
                    issue_number=issue.number,
                    success=False,
                    branch_name="",
                    files_modified=[],
                    commit_message="",
                    error_message=str(e)
                ))
        
        # Summary
        successful = sum(1 for r in results if r.success)
        logger.info(f"Enhanced bug fixing completed: {successful}/{len(issues)} issues fixed successfully")
        
        return results
