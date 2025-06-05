"""
GitHub API client for bug fixer operations
"""
import json
import logging
from typing import List, Optional
import requests

from ..models.bug_models import BugIssue

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for interacting with GitHub API"""
    
    def __init__(self, token: str, repo_owner: str, repo_name: str):
        self.token = token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    
    def get_open_issues(self, limit: Optional[int] = None) -> List[BugIssue]:
        """Fetch open issues from GitHub repository that do not have an associated open pull request.
        
        Args:
            limit: Maximum number of suitable issues to return. If None, returns all.
        """
        try:
            url = f"{self.base_url}/issues"
            params = {
                'state': 'open',
                'per_page': 100,
                'sort': 'created',
                'direction': 'asc'
            }
            
            all_issues_data = []
            current_url = url
            page_num = 1
            found_suitable_count = 0
            
            # Handle pagination for issues list
            while current_url:
                logger.info(f"Fetching page {page_num} of open issues")
                response = requests.get(current_url, headers=self.headers, params=params if page_num == 1 else None)
                response.raise_for_status()
                
                page_data = response.json()
                if not page_data:
                    break
                all_issues_data.extend(page_data)
                
                # Early termination if we have enough data to potentially find our limit
                # We fetch more than the limit because some issues might be filtered out
                if limit and len(all_issues_data) >= limit * 3:
                    break
                
                if 'next' in response.links:
                    current_url = response.links['next']['url']
                    page_num += 1
                else:
                    current_url = None

            # Filter out pull requests
            candidate_issues_data = []
            for issue_data in all_issues_data:
                if 'pull_request' not in issue_data:
                    candidate_issues_data.append(issue_data)
            
            logger.info(f"Found {len(candidate_issues_data)} raw open issues. Now filtering by linked open PRs.")
              # Filter out issues with linked open PRs and apply limit
            final_issues = []
            for issue_data in candidate_issues_data:
                issue_number = issue_data['number']
                timeline_url = issue_data.get('timeline_url')

                if not timeline_url:
                    logger.warning(f"Issue #{issue_number} missing timeline_url. Cannot check for linked PRs. Skipping.")
                    continue

                if not self._has_linked_open_pr(issue_number, timeline_url):
                    issue = BugIssue(
                        number=issue_data['number'],
                        title=issue_data['title'],
                        body=issue_data.get('body', ''),
                        labels=[label['name'] for label in issue_data.get('labels', [])],
                        state=issue_data['state'],
                        created_at=issue_data['created_at'],
                        updated_at=issue_data['updated_at'],
                        url=issue_data['html_url'],
                        author=issue_data['user']['login']
                    )
                    final_issues.append(issue)
                    logger.info(f"Issue #{issue_number} ({issue.title}) is suitable for fixing.")
                    
                    # Check limit AFTER we've found a suitable issue
                    if limit and len(final_issues) >= limit:
                        logger.info(f"Reached issue limit of {limit}. Stopping search.")
                        break
            
            logger.info(f"Found {len(final_issues)} open issues suitable for fixing.")
            return final_issues
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch issues due to API error: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching issues: {e}")
            return []
    
    def _has_linked_open_pr(self, issue_number: int, timeline_url: str) -> bool:
        """Check if an issue has an associated open pull request by examining its timeline."""
        try:
            logger.debug(f"Checking timeline for issue #{issue_number}")
            
            current_page_url = timeline_url
            max_pages_to_check = 3
            pages_checked = 0

            while current_page_url and pages_checked < max_pages_to_check:
                pages_checked += 1
                response = requests.get(current_page_url, headers=self.headers, params={'per_page': 100})
                response.raise_for_status()
                events = response.json()

                if not events:
                    break

                for event in events:
                    source = event.get('source')
                    if source and source.get('type') == 'issue' and source.get('issue'):
                        source_item_data = source['issue']
                        
                        is_pr = 'pull_request' in source_item_data and source_item_data['pull_request'] is not None
                        is_open = source_item_data.get('state') == 'open'

                        if is_pr and is_open:
                            pr_number = source_item_data.get('number')
                            pr_url = source_item_data.get('html_url')
                            logger.info(f"Issue #{issue_number} is linked to open PR #{pr_number} ({pr_url}). Skipping.")
                            return True
                
                if 'next' in response.links:
                    current_page_url = response.links['next']['url']
                else:
                    current_page_url = None
            
            return False

        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API error while checking timeline for issue #{issue_number}: {e}")
            return True  # Be cautious
        except Exception as e:
            logger.error(f"Unexpected error while checking timeline for issue #{issue_number}: {e}")
            return True
    
    def create_pull_request(self, title: str, head_branch: str, base_branch: str, body: str) -> Optional[str]:
        """Create a pull request"""
        try:
            url = f"{self.base_url}/pulls"
            
            pr_data = {
                'title': title,
                'head': f"{self.repo_owner}:{head_branch}" if ":" not in head_branch else head_branch,
                'base': base_branch,
                'body': body,
                'maintainer_can_modify': True,
            }
            
            response = requests.post(url, headers=self.headers, json=pr_data)
            
            if response.status_code == 201:
                pr_url = response.json()['html_url']
                logger.info(f"Pull request created successfully: {pr_url}")
                return pr_url
            else:
                response_content = response.text
                try:
                    response_json = response.json()
                    errors = response_json.get('errors', [])
                    error_messages = [e.get('message', str(e)) for e in errors]
                    if error_messages:
                        response_content = "; ".join(error_messages)
                except json.JSONDecodeError:
                    pass
                
                logger.error(f"Failed to create pull request (HTTP {response.status_code}): {response_content}")
                if "A pull request already exists" in response_content:
                    logger.warning(f"A PR for branch {head_branch} might already exist.")
                return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API error during pull request creation: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating pull request: {e}")
            return None
    
    def get_open_pull_requests(self) -> List['PullRequest']:
        """Fetch all open pull requests from the repository"""
        try:
            url = f"{self.base_url}/pulls"
            params = {
                'state': 'open',
                'per_page': 100,
                'sort': 'created',
                'direction': 'desc'
            }
            
            all_prs = []
            current_url = url
            page_num = 1
            
            while current_url:
                logger.info(f"Fetching page {page_num} of open pull requests")
                response = requests.get(current_url, headers=self.headers, params=params if page_num == 1 else None)
                response.raise_for_status()
                
                page_data = response.json()
                if not page_data:
                    break
                
                # Filter out draft PRs if desired (configurable)
                filtered_prs = [pr for pr in page_data if not pr.get('draft', False)]
                
                for pr_data in filtered_prs:
                    pr = self._parse_pull_request(pr_data)
                    if pr:
                        all_prs.append(pr)
                
                # Check for next page
                links = response.headers.get('Link', '')
                current_url = None
                if 'rel="next"' in links:
                    for link in links.split(','):
                        if 'rel="next"' in link:
                            current_url = link.split(';')[0].strip('<> ')
                            break
                page_num += 1
            
            logger.info(f"Found {len(all_prs)} open pull requests")
            return all_prs
            
        except Exception as e:
            logger.error(f"Failed to fetch open pull requests: {e}")
            return []
    
    def get_pull_request_reviews(self, pr_number: int) -> List[dict]:
        """Get existing reviews for a pull request
        
        Args:
            pr_number: The pull request number
            
        Returns:
            List of review dictionaries from GitHub API
        """
        try:
            url = f"{self.base_url}/pulls/{pr_number}/reviews"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            reviews = response.json()
            logger.debug(f"Found {len(reviews)} existing reviews for PR #{pr_number}")
            return reviews
            
        except Exception as e:
            logger.error(f"Failed to get reviews for PR #{pr_number}: {e}")
            return []
    
    def has_automated_reviews(self, pr_number: int) -> bool:
        """Check if a PR already has automated reviews (to avoid duplicate reviews)
        
        Args:
            pr_number: The pull request number
            
        Returns:
            True if the PR already has reviews, False otherwise
        """
        reviews = self.get_pull_request_reviews(pr_number)
        
        # Check if there are any reviews at all
        if not reviews:
            return False
              # For now, consider any review as a reason to skip
        # You could enhance this to only check for bot reviews or specific review types
        return len(reviews) > 0

    def get_recent_pull_requests(self, limit: Optional[int] = None) -> List['PullRequest']:
        """Fetch recent pull requests from the repository that don't have existing reviews
        
        Args:
            limit: Maximum number of PRs to return. If None, returns all.
        """
        # Get all open pull requests
        all_prs = self.get_open_pull_requests()
        
        # Filter out PRs that already have reviews to avoid duplicating work
        unreviewed_prs = []
        for pr in all_prs:
            if not self.has_automated_reviews(pr.number):
                unreviewed_prs.append(pr)
                logger.debug(f"PR #{pr.number} has no existing reviews - adding to review queue")
            else:
                logger.info(f"Skipping PR #{pr.number} - already has existing reviews")
        
        logger.info(f"Filtered {len(all_prs)} open PRs down to {len(unreviewed_prs)} unreviewed PRs")
        
        if limit:
            return unreviewed_prs[:limit]
        return unreviewed_prs
    
    def get_pull_request_files(self, pr_number: int) -> List['FileChange']:
        """Get the files changed in a pull request"""
        try:
            url = f"{self.base_url}/pulls/{pr_number}/files"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            files_data = response.json()
            file_changes = []
            
            for file_data in files_data:
                file_change = self._parse_file_change(file_data)
                if file_change:
                    file_changes.append(file_change)
            
            logger.info(f"Retrieved {len(file_changes)} changed files for PR #{pr_number}")
            return file_changes
            
        except Exception as e:
            logger.error(f"Failed to get PR files for #{pr_number}: {e}")
            return []
    
    def create_pull_request_review(self, pr_number: int, review_result: 'CodeReviewResult') -> Optional[str]:
        """Create an automated code review on a pull request"""
        try:
            url = f"{self.base_url}/pulls/{pr_number}/reviews"
              # Prepare review comments - skip line-specific comments for now
            comments = []
            # for comment in review_result.comments:
            #     if comment.line_number:
            #         comments.append({
            #             'path': comment.file_path,
            #             'line': comment.line_number,
            #             'body': f"**{comment.severity.upper()} - {comment.category.title()}**\n\n{comment.comment}"
            #         })
            
            # Prepare main review body
            review_body = self._format_review_body(review_result)            # Determine review event
            if review_result.recommendation == 'approve':
                event = 'APPROVE'
            elif review_result.recommendation == 'request_changes':
                event = 'REQUEST_CHANGES'
            else:
                event = 'COMMENT'
            
            payload = {
                'body': review_body,
                'event': event,
                'comments': comments            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code not in [200, 201]:
                logger.error(f"GitHub API error {response.status_code}: {response.text}")
                logger.error(f"Payload sent: {payload}")
            
            response.raise_for_status()
            
            review_data = response.json()
            review_url = review_data.get('html_url')
            
            logger.info(f"Created code review for PR #{pr_number}: {review_url}")
            return review_url
            
        except Exception as e:
            logger.error(f"Failed to create review for PR #{pr_number}: {e}")
            return None
    
    def _parse_pull_request(self, pr_data: dict) -> Optional['PullRequest']:
        """Parse GitHub PR data into PullRequest object"""
        try:
            from datetime import datetime
            from ..models.review_models import PullRequest
            
            return PullRequest(
                number=pr_data['number'],
                title=pr_data['title'],
                body=pr_data.get('body', ''),
                url=pr_data['html_url'],
                author=pr_data['user']['login'],
                branch=pr_data['head']['ref'],
                base_branch=pr_data['base']['ref'],
                created_at=datetime.fromisoformat(pr_data['created_at'].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(pr_data['updated_at'].replace('Z', '+00:00')),
                additions=pr_data.get('additions', 0),
                deletions=pr_data.get('deletions', 0),
                changed_files=pr_data.get('changed_files', 0),
                mergeable=pr_data.get('mergeable', True),
                draft=pr_data.get('draft', False),
                labels=[label['name'] for label in pr_data.get('labels', [])],
                raw_data=pr_data
            )
        except Exception as e:
            logger.error(f"Failed to parse pull request data: {e}")
            return None
    
    def _parse_file_change(self, file_data: dict) -> Optional['FileChange']:
        """Parse GitHub file change data into FileChange object"""
        try:
            from ..models.review_models import FileChange
            
            return FileChange(
                filename=file_data['filename'],
                status=file_data['status'],
                additions=file_data['additions'],
                deletions=file_data['deletions'],
                changes=file_data['changes'],
                patch=file_data.get('patch'),
                previous_filename=file_data.get('previous_filename')
            )
        except Exception as e:
            logger.error(f"Failed to parse file change data: {e}")
            return None
    
    def _format_review_body(self, review_result: 'CodeReviewResult') -> str:
        """Format the main review body"""
        body_parts = [
            "## 🤖 Automated Code Review",
            f"**Overall Assessment:** {review_result.overall_assessment}",
            f"**Quality Score:** {review_result.score}/10",
            "",
            "### Summary",
            review_result.summary,
            "",            "### Recommendation",
            f"**{review_result.recommendation.replace('_', ' ').title()}**"
        ]
        
        if review_result.comments:
            # Count only actual issues (errors and warnings), not positive aspects or suggestions
            issue_comments = [c for c in review_result.comments if c.severity in ['error', 'warning']]
            
            if issue_comments:
                body_parts.extend([
                    "",
                    f"### Issues Found ({len(issue_comments)})",
                    "Please see the inline comments for specific issues and suggestions."
                ])
            else:
                body_parts.extend([
                    "",
                    "### No Issues Found",
                    "This PR looks good! See below for positive feedback and suggestions."
                ])
        
        body_parts.extend([
            "",
            "---",
            "*This review was generated automatically by the AI Code Review Agent.*"
        ])
        
        return "\n".join(body_parts)
