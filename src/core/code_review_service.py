"""
Code review service that orchestrates the automated code review process
"""
import logging
from typing import List, Optional

from ..models.review_models import PullRequest, CodeReviewResult, ReviewAnalysis, FileChange
from ..clients.github_client import GitHubClient
from ..clients.ai_client import AIClient

logger = logging.getLogger(__name__)


class CodeReviewService:
    """Service for performing automated code reviews on pull requests"""
    
    def __init__(self, github_client: GitHubClient, ai_client: AIClient):
        self.github_client = github_client
        self.ai_client = ai_client
        self.review_client = None  # Will be set by agent if using separate review client
    
    def review_pull_requests(self, limit: Optional[int] = None) -> List[CodeReviewResult]:
        """Review multiple open pull requests"""
        try:
            # Get open pull requests
            pull_requests = self.github_client.get_open_pull_requests()
            if not pull_requests:
                logger.info("No open pull requests found for review")
                return []
            
            # Apply limit if specified
            if limit and limit > 0:
                if len(pull_requests) > limit:
                    logger.info(f"Limiting to first {limit} pull requests")
                    pull_requests = pull_requests[:limit]
            
            logger.info(f"Found {len(pull_requests)} pull requests to review")
            
            results = []
            for i, pr in enumerate(pull_requests, 1):
                logger.info(f"--- Reviewing PR {i}/{len(pull_requests)}: #{pr.number} ---")
                result = self.review_single_pull_request(pr)
                results.append(result)
                
                if result.success:
                    logger.info(f"[SUCCESS] Reviewed PR #{pr.number}")
                else:
                    logger.error(f"[FAILED] Failed to review PR #{pr.number}: {result.error_message}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error reviewing pull requests: {e}")
            return []
    
    def review_single_pull_request(self, pr: PullRequest) -> CodeReviewResult:
        """Review a single pull request"""
        logger.info(f"Starting review of PR #{pr.number}: {pr.title}")
        
        try:
            # Get file changes for the PR
            file_changes = self.github_client.get_pull_request_files(pr.number)
            if not file_changes:
                return CodeReviewResult(
                    pr_number=pr.number,
                    overall_assessment="No changes found",
                    recommendation="comment",
                    summary="This pull request appears to have no file changes.",
                    comments=[],
                    score=5,
                    success=False,
                    error_message="No file changes found in pull request"
                )
            
            logger.info(f"Found {len(file_changes)} changed files in PR #{pr.number}")            # Perform AI analysis of the changes
            review_analysis = self.ai_client.analyze_code_changes(pr.title, pr.body, file_changes)
            
            if not review_analysis:
                return CodeReviewResult(
                    pr_number=pr.number,
                    overall_assessment="Review failed",
                    recommendation="comment",
                    summary="Failed to analyze code changes with AI.",
                    comments=[],
                    score=0,
                    success=False,
                    error_message="AI analysis failed"
                )
              # Convert AI analysis to review result
            review_result = self._create_review_result_from_dict(pr, review_analysis)            # Submit the review to GitHub
            client_for_review = self.review_client if self.review_client else self.github_client
            client_name = "review client" if self.review_client else "main client"
            logger.info(f"Posting review for PR #{pr.number} using {client_name}")
            review_url = client_for_review.create_pull_request_review(pr.number, review_result)
            if review_url:
                review_result.review_url = review_url
                logger.info(f"Posted code review for PR #{pr.number}: {review_url}")
            else:
                logger.warning(f"Failed to post code review for PR #{pr.number}")
            
            return review_result
            
        except Exception as e:
            logger.error(f"Error reviewing PR #{pr.number}: {e}")
            return CodeReviewResult(
                pr_number=pr.number,
                overall_assessment="Review failed",
                recommendation="comment",
                summary=f"Failed to review pull request due to error: {str(e)}",
                comments=[],
                score=0,
                success=False,
                error_message=str(e)
            )
    
    def _create_review_result(self, pr: PullRequest, analysis: ReviewAnalysis) -> CodeReviewResult:
        """Convert AI analysis to a structured review result"""
        from ..models.review_models import ReviewComment
        
        comments = []
        issues_count = 0
        
        # Add security concerns as high-priority comments
        for concern in analysis.security_concerns:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"🔒 **Security Concern**: {concern}",
                severity="error",
                category="security"
            ))
            issues_count += 1
        
        # Add performance issues
        for issue in analysis.performance_issues:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"⚡ **Performance**: {issue}",
                severity="warning",
                category="performance"
            ))
        
        # Add code style issues
        for issue in analysis.code_style_issues:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"🎨 **Style**: {issue}",
                severity="suggestion",
                category="style"
            ))
        
        # Add logic concerns
        for concern in analysis.logic_concerns:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"🧠 **Logic**: {concern}",
                severity="error",
                category="logic"
            ))
            issues_count += 1
        
        # Add maintainability issues
        for issue in analysis.maintainability_issues:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"🔧 **Maintainability**: {issue}",
                severity="warning",
                category="maintainability"
            ))
        
        # Add positive aspects
        for positive in analysis.positive_aspects:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"✅ **Good**: {positive}",
                severity="info",
                category="positive"
            ))
        
        # Add suggestions
        for suggestion in analysis.suggestions:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"💡 **Suggestion**: {suggestion}",
                severity="suggestion",
                category="improvement"
            ))
        
        # Determine recommendation based on issues found
        if issues_count > 0:
            recommendation = "request_changes"
        elif len(analysis.performance_issues) > 0 or len(analysis.maintainability_issues) > 0:
            recommendation = "comment"
        else:
            recommendation = "approve"
        
        # Calculate score (1-10)
        base_score = 8
        score = max(1, min(10, base_score - issues_count - len(analysis.performance_issues) // 2))
        
        return CodeReviewResult(
            pr_number=pr.number,
            overall_assessment=analysis.overall_quality,
            recommendation=recommendation,
            summary=self._create_summary(pr, analysis, issues_count),
            comments=comments,
            score=score,
            success=True
        )
    
    def _create_review_result_from_dict(self, pr: PullRequest, analysis_dict: dict) -> CodeReviewResult:
        """Convert AI analysis dictionary to a structured review result"""
        from ..models.review_models import ReviewComment
        
        comments = []
        issues_count = 0
        
        # Extract data from dictionary with defaults
        overall_assessment = analysis_dict.get("overall_assessment", "COMMENT")
        summary = analysis_dict.get("summary", "Automated code review completed")
        strengths = analysis_dict.get("strengths", [])
        concerns = analysis_dict.get("concerns", [])
        suggestions = analysis_dict.get("suggestions", [])
        security_issues = analysis_dict.get("security_issues", [])
        performance_notes = analysis_dict.get("performance_notes", [])
        detailed_feedback = analysis_dict.get("detailed_feedback", "")
        
        # Add security concerns as high-priority comments
        for concern in security_issues:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"🔒 **Security Concern**: {concern}",
                severity="error",
                category="security"
            ))
            issues_count += 1
        
        # Add general concerns
        for concern in concerns:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"⚠️ **Concern**: {concern}",
                severity="warning",
                category="general"
            ))
            if "security" in concern.lower() or "vulnerable" in concern.lower():
                issues_count += 1
        
        # Add performance notes
        for note in performance_notes:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"⚡ **Performance**: {note}",
                severity="warning",
                category="performance"
            ))
        
        # Add positive aspects
        for strength in strengths:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"✅ **Good**: {strength}",
                severity="info",
                category="positive"
            ))
        
        # Add suggestions
        for suggestion in suggestions:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"💡 **Suggestion**: {suggestion}",
                severity="suggestion",
                category="improvement"
            ))
        
        # Add detailed feedback as main comment if provided
        if detailed_feedback:
            comments.append(ReviewComment(
                file_path="",
                line_number=None,
                comment=f"📝 **Detailed Review**:\n{detailed_feedback}",
                severity="info",
                category="general"
            ))
        
        # Determine recommendation based on AI assessment and issues found
        recommendation_map = {
            "APPROVE": "approve",
            "REQUEST_CHANGES": "request_changes",
            "COMMENT": "comment"
        }
        recommendation = recommendation_map.get(overall_assessment.upper(), "comment")
        
        # Override recommendation if critical issues found
        if issues_count > 0:
            recommendation = "request_changes"
        
        # Calculate score based on assessment
        score_map = {
            "approve": 8,
            "comment": 6,
            "request_changes": 4
        }
        score = score_map.get(recommendation, 5)
        
        return CodeReviewResult(
            pr_number=pr.number,
            overall_assessment=overall_assessment,
            recommendation=recommendation,
            summary=summary,
            comments=comments,
            score=score,
            success=True
        )
    
    def _create_summary(self, pr: PullRequest, analysis: ReviewAnalysis, issues_count: int) -> str:
        """Create a summary of the code review"""
        summary_parts = [
            f"## 🤖 Automated Code Review for PR #{pr.number}",
            f"",
            f"**Overall Assessment:** {analysis.overall_quality}",
            f"**Complexity:** {analysis.complexity_assessment}",
            f"**Issues Found:** {issues_count}",
            f""
        ]
        
        if analysis.test_coverage_notes:
            summary_parts.extend([
                f"**Test Coverage:** {analysis.test_coverage_notes}",
                f""
            ])
        
        if issues_count > 0:
            summary_parts.extend([
                f"### ⚠️ Issues to Address",
                f"This PR has {issues_count} issue(s) that should be addressed before merging.",
                f""
            ])
        
        if analysis.positive_aspects:
            summary_parts.extend([
                f"### ✅ Positive Aspects",
                f"This PR demonstrates good practices in several areas.",
                f""
            ])
        
        if analysis.suggestions:
            summary_parts.extend([
                f"### 💡 Suggestions for Improvement",
                f"Consider the suggestions below to enhance code quality.",
                f""
            ])
        
        summary_parts.append("---")
        summary_parts.append("*This review was generated automatically by the AI Code Review Agent.*")
        
        return "\n".join(summary_parts)
    
    def print_review_summary(self, results: List[CodeReviewResult], repo_full_name: str):
        """Print summary of all code reviews"""
        if not results:
            print("\nNo pull requests were reviewed in this run.")
            return

        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print("\n" + "="*80)
        print("AUTOMATED CODE REVIEW - RUN SUMMARY")
        print("="*80)
        print(f"Repository: {repo_full_name}")
        print(f"Total PRs Reviewed: {len(results)}")
        print(f"Successfully Reviewed: {len(successful)}")
        print(f"Failed Reviews: {len(failed)}")
        print("-" * 80)
        
        if successful:
            print("\nSUCCESSFUL REVIEWS:")
            for result in successful:
                print(f"  [SUCCESS] PR #{result.pr_number}")
                print(f"     Assessment: {result.overall_assessment}")
                print(f"     Recommendation: {result.recommendation.upper()}")
                print(f"     Score: {result.score}/10")
                print(f"     Comments: {len(result.comments)}")
                if result.review_url:
                    print(f"     Review URL: {result.review_url}")
                print()
        
        if failed:
            print("\nFAILED REVIEWS:")
            for result in failed:
                print(f"  [FAILED] PR #{result.pr_number}")
                print(f"     Error: {result.error_message}")
                print()
        
        print("="*80)
        print("Review summary complete. Check logs for detailed information.")
