#!/usr/bin/env python3
"""
Quick test to verify GitHub review posting works
"""
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

from src.clients.github_client import GitHubClient
from src.core.config import ConfigLoader
from src.models.review_models import CodeReviewResult, ReviewComment

def test_dummy_review():
    """Test posting a dummy review to PR #27"""
    print("Testing GitHub review posting...")
    
    # Load config
    config = ConfigLoader.load_from_env('.env')
      # Initialize GitHub client with review token
    review_github_client = GitHubClient(
        token=config.github_codereview_token,
        repo_owner=config.repo_owner,
        repo_name=config.repo_name
    )    # Create a dummy review result
    dummy_review = CodeReviewResult(
        pr_number=27,
        overall_assessment="REQUEST_CHANGES",
        recommendation="request_changes",
        summary="🤖 Test review with changes requested - found critical issues!",
        comments=[
            ReviewComment(
                file_path="",
                line_number=None,
                comment="🤖 This is an automated test review",
                severity="info",
                category="test"
            ),
            ReviewComment(
                file_path="",
                line_number=None,
                comment="✅ Code structure appears clean",
                severity="info",
                category="positive"
            )
        ],
        score=8,
        success=True
    )
      # Try to post the review
    try:
        review_url = review_github_client.create_pull_request_review(27, dummy_review)
        if review_url:
            print(f"✅ SUCCESS: Review posted successfully!")
            print(f"Review URL: {review_url}")
        else:
            print("❌ FAILED: Review posting returned None")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == '__main__':
    test_dummy_review()
