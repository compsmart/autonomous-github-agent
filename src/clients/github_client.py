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
    
    def get_open_issues(self) -> List[BugIssue]:
        """Fetch all open issues from GitHub repository that do not have an associated open pull request."""
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
            
            # Handle pagination for issues list
            while current_url:
                logger.info(f"Fetching page {page_num} of open issues")
                response = requests.get(current_url, headers=self.headers, params=params if page_num == 1 else None)
                response.raise_for_status()
                
                page_data = response.json()
                if not page_data:
                    break
                all_issues_data.extend(page_data)
                
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
            
            # Filter out issues with linked open PRs
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
