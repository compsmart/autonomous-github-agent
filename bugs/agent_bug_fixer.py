#!/usr/bin/env python3
"""
Autonomous AI Bug Fixer Agent

A standalone AI agent that can be deployed anywhere to automatically:
1. Clone or pull a repository
2. Analyze all open GitHub issues (that don't have an open PR)
3. Fix bugs autonomously using AI
4. Create pull requests with fixes
5. Work completely independently with minimal configuration

Requirements:
- .env file with GITHUB_TOKEN and GEMINI_API_KEY
- Repository configuration in .env or command line args
"""

import os
import sys
import subprocess
import tempfile
import shutil
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

# Third-party imports
import requests
import google.generativeai as genai
from dotenv import load_dotenv

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

@dataclass
class BugIssue:
    """Represents a GitHub issue/bug to be fixed"""
    number: int
    title: str
    body: str
    labels: List[str]
    state: str
    created_at: str
    updated_at: str
    url: str
    author: str
    # START CHANGE: Added timeline_url to BugIssue if needed later, though not strictly necessary for current logic
    # timeline_url: str # Not strictly needed for BugIssue if only used during filtering
    # END CHANGE

@dataclass
class FixResult:
    """Represents the result of a bug fix attempt"""
    issue_number: int
    success: bool
    branch_name: str
    files_modified: List[str]
    commit_message: str
    pr_url: Optional[str] = None
    error_message: Optional[str] = None

class AutonomousBugFixer:
    """
    Autonomous AI Bug Fixer Agent
    
    This agent works completely independently to fix bugs in any repository.
    """
    
    def __init__(self, config_file: str = '.env'):
        """Initialize the autonomous bug fixer"""
        load_dotenv(config_file)
        
        # Load configuration
        self.github_token = os.getenv('GITHUB_TOKEN')
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        # Handle both GITHUB_REPO format and separate REPO_OWNER/REPO_NAME
        github_repo = os.getenv('GITHUB_REPO')
        if github_repo:
            if '/' in github_repo:
                self.repo_owner, self.repo_name = github_repo.split('/', 1)
            else:
                raise ValueError("GITHUB_REPO must be in format 'owner/repo'")
        else:
            self.repo_owner = os.getenv('REPO_OWNER', 'compsmart')
            self.repo_name = os.getenv('REPO_NAME', 'bug-fixer')
        
        self.repo_url = f"https://github.com/{self.repo_owner}/{self.repo_name}.git"
        
        # System instructions for the AI agent
        self.system_instructions = os.getenv('SYSTEM_INSTRUCTIONS', self._get_default_instructions())
        
        # Working directory for cloned repository
        self.work_dir = None
        self.repo_path = None
        
        # Validate configuration
        self._validate_config()
        
        # Initialize AI model
        self._initialize_ai()
        
        # GitHub API setup
        self.github_headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        logger.info(f"Autonomous Bug Fixer initialized for {self.repo_owner}/{self.repo_name}")
    
    def _get_default_instructions(self) -> str:
        """Get default system instructions for the AI agent"""
        return """
You are an expert software engineer and debugging specialist. Your job is to:

1. ANALYZE bugs thoroughly by examining the code, understanding the problem, and identifying root causes
2. IMPLEMENT precise, minimal fixes that solve the exact problem without introducing new issues
3. FOLLOW best practices: write clean, maintainable code with proper error handling
4. PRESERVE existing functionality while fixing the specific bug
5. WRITE clear, descriptive commit messages that explain what was fixed and why

For each bug fix:
- Read and understand the issue description completely
- Examine the relevant code files carefully
- Identify the exact problem and root cause
- Implement the minimal fix required
- Test your understanding by explaining the fix
- Ensure the fix doesn't break existing functionality

Be thorough but efficient. Focus on precision over speed.
"""
    
    def _validate_config(self):
        """Validate required configuration"""
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN not found in environment variables")
        if not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        logger.info("Configuration validated successfully")
    
    def _initialize_ai(self):
        """Initialize Google Gemini AI model"""
        try:
            genai.configure(api_key=self.gemini_api_key)
            self.model = genai.GenerativeModel(
                'gemini-pro', # Changed to gemini-pro as 'gemini-2.0-flash-exp' might not be universally available
                system_instruction=self.system_instructions
            )
            logger.info("AI model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize AI model: {e}")
            raise
    
    def setup_workspace(self) -> str:
        """Setup workspace by cloning or pulling the repository"""
        try:
            # Create temporary working directory
            self.work_dir = tempfile.mkdtemp(prefix='bug_fixer_')
            self.repo_path = os.path.join(self.work_dir, self.repo_name)
            
            logger.info(f"Setting up workspace in {self.work_dir}")
            
            # Clone the repository
            clone_cmd = [
                'git', 'clone', 
                f"https://{self.github_token}@github.com/{self.repo_owner}/{self.repo_name}.git",
                self.repo_path
            ]
            
            result = subprocess.run(clone_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to clone repository: {result.stderr}")
            
            # Configure git in the repository
            self._configure_git()
            
            logger.info(f"Repository cloned successfully to {self.repo_path}")
            return self.repo_path
            
        except Exception as e:
            logger.error(f"Failed to setup workspace: {e}")
            self.cleanup_workspace()
            raise
    
    def _configure_git(self):
        """Configure git for commits"""
        git_commands = [
            ['git', 'config', 'user.name', 'AI Bug Fixer'],
            ['git', 'config', 'user.email', 'ai-bug-fixer@automated.local'],
            ['git', 'config', 'push.default', 'current']
        ]
        
        for cmd in git_commands:
            subprocess.run(cmd, cwd=self.repo_path, capture_output=True)
    
    def cleanup_workspace(self):
        """Clean up temporary workspace"""
        if self.work_dir and os.path.exists(self.work_dir):
            try:
                shutil.rmtree(self.work_dir)
                logger.info("Workspace cleaned up")
            except Exception as e:
                logger.warning(f"Failed to cleanup workspace: {e}")

    # START NEW METHOD
    def _has_linked_open_pr(self, issue_number: int, timeline_url: str) -> bool:
        """
        Check if an issue has an associated open pull request by examining its timeline.
        An issue is considered to have a linked open PR if its timeline shows
        a 'cross-referenced' or 'connected' event from an open Pull Request.
        """
        try:
            logger.debug(f"Fetching timeline for issue #{issue_number} to check for linked open PRs.")
            
            current_page_url = timeline_url
            # Optimization: Check a limited number of pages/events. 
            # Most relevant links (like "fixes #X") are usually recent.
            max_pages_to_check = 3 
            pages_checked = 0

            while current_page_url and pages_checked < max_pages_to_check:
                pages_checked += 1
                logger.debug(f"Fetching timeline page {pages_checked} for issue #{issue_number} from {current_page_url}")
                
                response = requests.get(current_page_url, headers=self.github_headers, params={'per_page': 100})
                response.raise_for_status()
                events = response.json()

                if not events: # No more events on this page or subsequent pages
                    break

                for event in events:
                    event_type = event.get('event')
                    source = event.get('source')

                    # Relevant events: 'connected' (PR linked, e.g. by "fixes #X") or 
                    # 'cross-referenced' (PR mentions issue).
                    # We need to check if the source of this event is an OPEN PULL REQUEST.
                    if source and source.get('type') == 'issue' and source.get('issue'):
                        # In this context, source.issue is the referencing item (potentially a PR)
                        source_item_data = source['issue']
                        
                        # Check if the source_item is a PR and is open
                        is_pr = 'pull_request' in source_item_data and source_item_data['pull_request'] is not None
                        is_open = source_item_data.get('state') == 'open'

                        if is_pr and is_open:
                            pr_number = source_item_data.get('number')
                            pr_url = source_item_data.get('html_url')
                            logger.info(f"Issue #{issue_number} is linked to open PR #{pr_number} ({pr_url}) via timeline event '{event_type}'. Skipping this issue.")
                            return True
                
                # Get URL for the next page of timeline events
                if 'next' in response.links:
                    current_page_url = response.links['next']['url']
                else:
                    current_page_url = None # No more pages
            
            return False # No linked open PR found in the checked timeline events

        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API error while checking timeline for issue #{issue_number}: {e}. Assuming PR might exist to be safe.")
            return True # Be cautious: if API fails, assume a PR might exist.
        except Exception as e:
            logger.error(f"Unexpected error while checking timeline for issue #{issue_number}: {e}. Assuming PR might exist to be safe.")
            return True # Be cautious
    # END NEW METHOD
    
    # START MODIFIED METHOD
    def get_open_issues(self) -> List[BugIssue]:
        """Fetch all open issues from GitHub repository that do not have an associated open pull request."""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues"
            params = {
                'state': 'open',
                'per_page': 100, # Fetch up to 100 open issues
                'sort': 'created',
                'direction': 'asc' # Process older issues first
            }
            
            all_issues_data = []
            current_url = url
            page_num = 1
            # Handle pagination for issues list
            while current_url:
                logger.info(f"Fetching page {page_num} of open issues from {current_url}")
                response = requests.get(current_url, headers=self.github_headers, params=params if page_num == 1 else None)
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

            candidate_issues_data = []
            for issue_data in all_issues_data:
                # Skip items that are pull requests themselves
                if 'pull_request' in issue_data:
                    continue
                candidate_issues_data.append(issue_data)
            
            logger.info(f"Found {len(candidate_issues_data)} raw open issues (not PRs). Now filtering by linked open PRs.")
            
            final_issues = []
            for issue_data in candidate_issues_data:
                issue_number = issue_data['number']
                timeline_url = issue_data.get('timeline_url')

                if not timeline_url:
                    logger.warning(f"Issue #{issue_number} missing timeline_url. Cannot check for linked PRs. Skipping.")
                    continue

                # Check if this issue has an associated open PR by inspecting its timeline
                if not self._has_linked_open_pr(issue_number, timeline_url):
                    issue = BugIssue(
                        number=issue_data['number'],
                        title=issue_data['title'],
                        body=issue_data.get('body', ''), # Ensure body is present, default to empty string
                        labels=[label['name'] for label in issue_data.get('labels', [])],
                        state=issue_data['state'],
                        created_at=issue_data['created_at'],
                        updated_at=issue_data['updated_at'],
                        url=issue_data['html_url'],
                        author=issue_data['user']['login']
                    )
                    final_issues.append(issue)
                    logger.info(f"Issue #{issue_number} ({issue.title}) is suitable for fixing (no open PRs found linked).")
                # else: logger message is handled inside _has_linked_open_pr
            
            logger.info(f"Found {len(final_issues)} open issues suitable for fixing (no linked open PRs).")
            return final_issues
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch issues due to API error: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while fetching issues: {e}")
            return []
    # END MODIFIED METHOD
    
    def analyze_codebase(self) -> Dict[str, str]:
        """Analyze the codebase to understand structure and key files"""
        if not self.repo_path:
            logger.error("Repository path not set")
            return {}
            
        try:
            codebase_info = {
                'structure': self._get_directory_structure(),
                'key_files': self._identify_key_files(),
                'languages': self._detect_languages(),
                'dependencies': self._get_dependencies()
            }
            
            logger.info("Codebase analysis completed")
            return codebase_info
            
        except Exception as e:
            logger.error(f"Failed to analyze codebase: {e}")
            return {}
    
    def _get_directory_structure(self) -> str:
        """Get directory structure of the repository"""
        try:
            # Use tree command if available, otherwise use ls/dir
            if shutil.which('tree'):
                result = subprocess.run(['tree', '-L', '3'], 
                                      cwd=self.repo_path, 
                                      capture_output=True, text=True, check=False) # check=False to avoid exception on non-zero
                if result.returncode == 0:
                    return result.stdout
            
            # Fallback to manual directory listing
            structure = []
            for root, dirs, files in os.walk(self.repo_path):
                # Skip .git directory
                if '.git' in root.split(os.sep):
                    continue
                
                level = root.replace(self.repo_path, '').count(os.sep)
                if level < 3:  # Limit depth
                    indent = ' ' * 2 * level
                    structure.append(f"{indent}{os.path.basename(root)}/")
                    subindent = ' ' * 2 * (level + 1)
                    for file_count, file_name in enumerate(files):
                        if file_count < 10: # Limit files shown per directory
                             structure.append(f"{subindent}{file_name}")
                        else:
                            structure.append(f"{subindent}...")
                            break
                    # Limit directories shown per level
                    dirs_to_show = []
                    for dir_count, dir_name in enumerate(dirs):
                        if dir_name == '.git': # Skip .git when listing subdirs
                            continue
                        if dir_count < 5:
                            dirs_to_show.append(dir_name)
                        else:
                            # Indicate more directories exist
                            # structure.append(f"{subindent}[...more directories...]")
                            break
                    dirs[:] = dirs_to_show # Prune dirs to explore based on limit
            
            return '\n'.join(structure)
            
        except Exception as e:
            logger.warning(f"Could not get directory structure: {e}")
            return "Directory structure unavailable"
    
    def _identify_key_files(self) -> List[str]:
        """Identify key files in the repository"""
        key_files = []
        common_files = [
            'README.md', 'package.json', 'requirements.txt', 'setup.py',
            'index.html', 'main.py', 'app.py', 'server.py', 'index.js',
            'main.js', 'app.js', 'config.json', '.gitignore', 'pom.xml',
            'build.gradle', 'Dockerfile', 'docker-compose.yml'
        ]
        
        for file_name in common_files:
            # Check root
            file_path = Path(self.repo_path) / file_name
            if file_path.exists():
                key_files.append(file_name)
            # Check common subdirectories like 'src'
            for common_subdir in ['src', 'app', 'cmd', 'lib']:
                subdir_file_path = Path(self.repo_path) / common_subdir / file_name
                if subdir_file_path.exists() and str(subdir_file_path.relative_to(self.repo_path)) not in key_files:
                    key_files.append(str(subdir_file_path.relative_to(self.repo_path)))

        return key_files
    
    def _detect_languages(self) -> List[str]:
        """Detect programming languages used in the repository"""
        languages = set()
        extensions = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.html': 'HTML',
            '.css': 'CSS', '.java': 'Java', '.cpp': 'C++', '.c': 'C', '.cs': 'C#',
            '.go': 'Go', '.rs': 'Rust', '.php': 'PHP', '.rb': 'Ruby', '.kt': 'Kotlin',
            '.swift': 'Swift', '.scala': 'Scala', '.md': 'Markdown', '.json': 'JSON',
            '.yaml': 'YAML', '.yml': 'YAML', '.sh': 'Shell'
        }
        
        file_count_for_lang_detection = 0
        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in root.split(os.sep): # Skip .git
                continue
            for file_name in files:
                if file_count_for_lang_detection > 1000: # Limit files scanned for performance
                    return list(languages) if languages else ["Undetermined - too many files"]

                ext = os.path.splitext(file_name)[1].lower()
                if ext in extensions:
                    languages.add(extensions[ext])
                file_count_for_lang_detection +=1
        
        return list(languages) if languages else ["Undetermined"]
    
    def _get_dependencies(self) -> Dict[str, str]:
        """Get dependency information from common dependency files"""
        dependencies = {}
        
        dep_files = {
            'python': 'requirements.txt',
            'nodejs_package': 'package.json', # For 'dependencies' and 'devDependencies'
            'maven': 'pom.xml',
            'gradle': 'build.gradle', # or build.gradle.kts
        }

        for lang, file_name in dep_files.items():
            file_path = Path(self.repo_path) / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read(2048) # Read a snippet
                        if lang == 'nodejs_package':
                            try:
                                pkg_data = json.loads(content if len(content) < 2048 else f.read()) # re-read if snippet was too short
                                deps = pkg_data.get('dependencies', {})
                                dev_deps = pkg_data.get('devDependencies', {})
                                dependencies[lang] = json.dumps({'dependencies': deps, 'devDependencies': dev_deps}, indent=2)
                            except json.JSONDecodeError:
                                dependencies[lang] = "Could not parse package.json"
                        else:
                             dependencies[lang] = content.strip() + "\n..." if len(content) == 2048 else content.strip()
                except Exception as e:
                    logger.warning(f"Could not read dependency file {file_name}: {e}")
                    dependencies[lang] = f"Error reading {file_name}"
            # Check for .kts variant for gradle
            elif lang == 'gradle' and not file_path.exists():
                file_path_kts = Path(self.repo_path) / "build.gradle.kts"
                if file_path_kts.exists():
                    try:
                        with open(file_path_kts, 'r', encoding='utf-8') as f:
                            content = f.read(2048)
                            dependencies[lang] = content.strip() + "\n..." if len(content) == 2048 else content.strip()
                    except Exception as e:
                        logger.warning(f"Could not read dependency file build.gradle.kts: {e}")
                        dependencies[lang] = "Error reading build.gradle.kts"

        return dependencies

    def fix_bug(self, issue: BugIssue, codebase_info: Dict[str, str]) -> FixResult:
        """Fix a single bug using AI analysis with individual commit and PR"""
        logger.info(f"Attempting to fix issue #{issue.number}: {issue.title}")
        
        branch_name = f"fix-issue-{issue.number}-{int(time.time())}"
        
        try:
            # Step 1: Create fresh feature branch from main/master
            # Determine default branch name (main or master)
            default_branch = self._get_default_branch()
            self._create_feature_branch(branch_name, default_branch)
            logger.info(f"Created feature branch: {branch_name} from {default_branch}")
            
            # Step 2: Analyze the bug and generate fix
            fix_analysis = self._analyze_bug_with_ai(issue, codebase_info)
            
            if not fix_analysis or not self._validate_ai_response(fix_analysis):
                self._cleanup_failed_branch(branch_name, default_branch)
                error_msg = "Failed to analyze bug with AI or AI response invalid."
                if fix_analysis and not self._validate_ai_response(fix_analysis):
                    error_msg = "AI response was invalid."
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
            files_modified = self._apply_fix(fix_analysis)
            
            if not files_modified:
                self._cleanup_failed_branch(branch_name, default_branch)
                return FixResult(
                    issue_number=issue.number,
                    success=False,
                    branch_name=branch_name,
                    files_modified=[],
                    commit_message="",
                    error_message="No files were modified by AI fix attempt (or AI suggested no changes)"
                )
            
            # Step 4: Create commit with proper formatting
            commit_title = self._generate_commit_title(issue, fix_analysis)
            commit_message = f"Fix: #{issue.number} {commit_title}\n\n{fix_analysis.get('explanation', 'Automated fix for issue.')}\n\nRelated to issue: {issue.url}"
            self._commit_changes(commit_message, files_modified)
            logger.info(f"Committed changes for issue #{issue.number}")
            
            # Step 5: Push branch to remote
            self._push_branch(branch_name)
            logger.info(f"Pushed branch {branch_name} to remote")
            
            # Step 6: Create individual pull request
            pr_url = self._create_pull_request(issue, branch_name, fix_analysis, default_branch)
            
            if pr_url:
                logger.info(f"Created pull request for issue #{issue.number}: {pr_url}")
            else: # PR creation failed, but changes are pushed.
                logger.error(f"Failed to create PR for issue #{issue.number}, but branch {branch_name} was pushed.")

            return FixResult(
                issue_number=issue.number,
                success=True, # Success means code was changed and pushed. PR is bonus.
                branch_name=branch_name,
                files_modified=files_modified,
                commit_message=commit_message,
                pr_url=pr_url
            )
            
        except Exception as e:
            logger.error(f"Failed to fix issue #{issue.number}: {e}", exc_info=True)
            default_branch = getattr(self, '_last_default_branch', 'master') # Get cached or default
            self._cleanup_failed_branch(branch_name, default_branch)
            return FixResult(
                issue_number=issue.number,
                success=False,
                branch_name=branch_name,
                files_modified=[],
                commit_message="",
                error_message=str(e)
            )

    def _get_default_branch(self) -> str:
        """Determine the default branch (main or master) of the repository."""
        # Cache it after first determination
        if hasattr(self, '_default_branch_name'):
            return self._default_branch_name

        branches_output = subprocess.run(['git', 'branch', '-r'], cwd=self.repo_path, capture_output=True, text=True)
        if branches_output.returncode == 0:
            remote_branches = branches_output.stdout.splitlines()
            if any('origin/main' in b for b in remote_branches):
                self._default_branch_name = 'main'
                self._last_default_branch = 'main' # Cache for cleanup
                return 'main'
        self._default_branch_name = 'master' # Default to master
        self._last_default_branch = 'master' # Cache for cleanup
        return 'master'

    def _create_feature_branch(self, branch_name: str, base_branch: str):
        """Create and switch to a new feature branch from the specified base branch."""
        commands = [
            ['git', 'checkout', base_branch],
            ['git', 'pull', 'origin', base_branch], # Ensure base is up-to-date
            ['git', 'checkout', '-b', branch_name]
        ]
        
        for cmd_idx, cmd in enumerate(commands):
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                # If pulling base_branch fails, it might be because it's a fresh clone or local only.
                # If checkout -b fails, it's more critical.
                if cmd_idx == 1 and ("couldn't find remote ref" in result.stderr or "no upstream" in result.stderr):
                    logger.warning(f"Could not pull remote {base_branch}, proceeding with local version. Error: {result.stderr}")
                elif cmd_idx == 0 and "did not match any file(s) known to git" in result.stderr: # Base branch does not exist
                    # Try the other common default branch name
                    alternative_base = 'main' if base_branch == 'master' else 'master'
                    logger.warning(f"Base branch {base_branch} not found, trying {alternative_base}")
                    commands[0] = ['git', 'checkout', alternative_base]
                    commands[1] = ['git', 'pull', 'origin', alternative_base]
                    self._last_default_branch = alternative_base # Update cache
                    # Re-run from the checkout command
                    return self._create_feature_branch(branch_name, alternative_base)
                else:
                    raise Exception(f"Git command failed: {' '.join(cmd)}\nStdout: {result.stdout}\nStderr: {result.stderr}")
    
    def _analyze_bug_with_ai(self, issue: BugIssue, codebase_info: Dict[str, str]) -> Optional[Dict]:
        """Use AI to analyze the bug and generate a fix"""
        try:
            # Identify potentially relevant files to provide more context
            relevant_files_content = {}
            # Use files_to_examine from a pre-analysis if available, or make a guess
            # For now, let's keep it simple and rely on codebase_info and issue description.
            # To enhance, one could pre-parse issue for filenames or use AI to suggest files_to_examine first.

            context = f"""
You are an AI Software Engineer. Your task is to fix a bug in a Git repository.
Carefully analyze the provided repository information and the specific issue details.
Then, provide a precise fix.

CONTEXT:
Repository: {self.repo_owner}/{self.repo_name}
Main programming languages: {codebase_info.get('languages', 'N/A')}
Key files (examples): {codebase_info.get('key_files', 'N/A')}
Dependencies (examples): {json.dumps(codebase_info.get('dependencies', {}), indent=2)}
Directory Structure (partial):
{codebase_info.get('structure', 'N/A')}

ISSUE TO FIX:
Issue Number: #{issue.number}
Title: {issue.title}
URL: {issue.url}
Author: {issue.author}
Labels: {', '.join(issue.labels)}
Description:
---
{issue.body if issue.body else "No description provided."}
---

INSTRUCTIONS:
1.  **Analyze the Bug**: Understand the problem based on the issue description.
2.  **Identify Root Cause**: Determine the likely root cause.
3.  **Propose Fix Strategy**: Briefly explain your plan to fix it.
4.  **Specify File Modifications**:
    *   List ALL files that need to be modified.
    *   For each file, provide its FULL `path/to/file.ext` relative to the repository root.
    *   Provide the `new_content` for EACH modified file. This should be the ENTIRE file content after your changes.
    *   If you are only adding or deleting a few lines, still provide the complete new content for the file.
    *   If a file is new, its `new_content` is simply its content.
5.  **Explain Your Fix**: Clearly describe what you changed and why it fixes the bug.

OUTPUT FORMAT (Strict JSON):
Return your response as a single JSON object with the following structure:
{{
  "analysis": "Your detailed textual analysis of the bug, its impact, and how the issue description relates to the code.",
  "root_cause": "Your assessment of the root cause of the bug.",
  "fix_strategy": "Your strategy for fixing the bug. Be specific about the approach.",
  "files_to_modify": [
    {{
      "file": "path/to/file1.ext",
      "new_content": "The complete new content of file1.ext after your modifications."
    }},
    {{
      "file": "path/to/new_file.ext",
      "new_content": "The content of the new file."
    }}
    // Add more file objects as needed
  ],
  "explanation": "A clear and concise explanation of your fix, detailing what was changed and why these changes address the bug. This will be used in the Pull Request."
}}

IMPORTANT:
- Ensure `file` paths are correct and relative to the repository root.
- The `new_content` MUST be the complete content of the file. Do NOT provide diffs or partial snippets.
- If no files need to be changed (e.g., the bug is a misunderstanding or cannot be fixed with code changes), `files_to_modify` should be an empty list `[]`.
- Be precise. Your output will be used to directly modify files.
"""
            
            logger.info(f"Sending analysis request to AI for issue #{issue.number}...")
            # Configure safety settings to be less restrictive for code generation
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            response = self.model.generate_content(context, safety_settings=safety_settings)
            
            response_text = response.text
            logger.debug(f"AI Raw Response for issue #{issue.number}:\n{response_text}")

            # Extract JSON from response, robustly handling potential markdown code blocks
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text: # Generic code block
                 json_text = response_text.split("```")[1].split("```")[0].strip()
            else:
                json_text = response_text # Assume raw JSON if no backticks

            try:
                parsed_response = json.loads(json_text)
                if self._validate_ai_response(parsed_response):
                    logger.info(f"AI analysis and fix proposal received for issue #{issue.number}.")
                    return parsed_response
                else:
                    logger.error(f"AI response for issue #{issue.number} failed validation.")
                    logger.debug(f"Invalid AI JSON structure: {json_text}")
                    return None
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON for issue #{issue.number}: {e}")
                logger.debug(f"Problematic JSON text: {json_text}")
                return None
                
        except Exception as e:
            logger.error(f"AI analysis failed for issue #{issue.number}: {e}", exc_info=True)
            return None
    
    def _apply_fix(self, fix_analysis: Dict) -> List[str]:
        """Apply the fix based on AI analysis"""
        files_modified = []
        
        if 'files_to_modify' not in fix_analysis or not isinstance(fix_analysis['files_to_modify'], list):
            logger.warning("No 'files_to_modify' array found in AI response or it's not a list.")
            return []

        try:
            for file_change in fix_analysis.get('files_to_modify', []):
                file_path_str = file_change.get('file')
                new_content = file_change.get('new_content') # new_content can be None if AI fails to provide it
                
                if not file_path_str:
                    logger.warning(f"Missing 'file' path in AI response item: {file_change}")
                    continue
                if new_content is None: # Explicitly check for None, as empty string is valid content
                    logger.warning(f"Missing 'new_content' for file {file_path_str} in AI response. Skipping this file.")
                    continue

                # Sanitize file_path_str: remove leading slashes, ensure it's relative
                file_path_str = file_path_str.lstrip('/')
                if ".." in file_path_str or os.path.isabs(file_path_str):
                    logger.error(f"Invalid or unsafe file path from AI: {file_path_str}. Skipping.")
                    continue
                
                full_path = Path(self.repo_path) / file_path_str
                
                try:
                    # Ensure directory exists
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write new content
                    with open(full_path, 'w', encoding='utf-8', newline='') as f: # Use newline='' for universal newlines
                        f.write(new_content)
                    
                    files_modified.append(file_path_str)
                    logger.info(f"Applied fix to file: {file_path_str}")
                except IOError as e:
                    logger.error(f"IOError writing to file {full_path}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error applying fix to file {full_path}: {e}")

            if not files_modified and fix_analysis.get('files_to_modify'):
                logger.warning("AI suggested files to modify, but none were actually changed due to missing content or errors.")
            elif not fix_analysis.get('files_to_modify'):
                 logger.info("AI analysis indicated no files needed modification.")


            return files_modified
            
        except Exception as e:
            logger.error(f"Failed to apply fix due to an unexpected error: {e}", exc_info=True)
            return []
    
    def _generate_commit_title(self, issue: BugIssue, fix_analysis: Dict) -> str:
        """Generate a concise commit title from issue and fix analysis"""
        # Attempt to use a part of the AI's explanation or analysis if concise enough
        # For now, stick to a simpler title generation based on the issue.
        
        title = issue.title
        # Clean up common prefixes if they exist, and limit length
        prefixes_to_remove = ["bug:", "bug -", "fix:", "fix -", "issue:", "issue -"]
        for prefix in prefixes_to_remove:
            if title.lower().startswith(prefix):
                title = title[len(prefix):].strip()
        
        # Keep it relatively short, e.g., 50-70 chars
        max_len = 60
        if len(title) > max_len:
            title = title[:max_len-3] + "..."
        
        # Capitalize first letter if not already
        if title:
            title = title[0].upper() + title[1:]
        else: # Fallback if title becomes empty
            title = f"Address issue {issue.number}"
            
        return title
    
    def _cleanup_failed_branch(self, branch_name: str, base_branch: str):
        """Clean up failed branch by switching back to base_branch and deleting the local failed branch."""
        try:
            logger.info(f"Cleaning up failed branch: {branch_name}, switching to {base_branch}")
            # Switch back to base_branch
            checkout_cmd = ['git', 'checkout', base_branch]
            subprocess.run(checkout_cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            
            # Delete the failed local branch
            delete_branch_cmd = ['git', 'branch', '-D', branch_name]
            delete_result = subprocess.run(delete_branch_cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            if delete_result.returncode == 0:
                logger.info(f"Successfully deleted local branch: {branch_name}")
            else:
                logger.warning(f"Could not delete local branch {branch_name}. It might not exist or an error occurred: {delete_result.stderr}")

            # Optionally, try to delete remote branch if it was pushed
            # This is risky if we are not sure it was THIS agent's push or if PR was made
            # For now, only local cleanup.
        except Exception as e:
            logger.warning(f"Failed to cleanup branch {branch_name}: {e}")
    
    def _commit_changes(self, commit_message: str, files_modified: List[str]):
        """Commit changes to git with validation"""
        try:
            # Add only the modified files
            for file_path in files_modified:
                cmd = ['git', 'add', file_path]
                result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    logger.warning(f"Failed to 'git add' {file_path}: {result.stderr}")
                    # Potentially raise an error or remove from files_modified if add fails critically
            
            # Check if there are staged changes to commit
            status_cmd = ['git', 'status', '--porcelain']
            status_result = subprocess.run(status_cmd, cwd=self.repo_path, capture_output=True, text=True, check=True)
            
            if not status_result.stdout.strip():
                # This case should ideally be caught by _apply_fix returning empty list
                logger.warning("No changes staged for commit, though files were expected to be modified.")
                raise Exception("No changes to commit after 'git add'. Files might not have been successfully modified or added.")
            
            # Commit the changes
            commit_cmd = ['git', 'commit', '-m', commit_message]
            result = subprocess.run(commit_cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                # Provide more details on commit failure
                error_detail = f"Git commit failed. Stderr: {result.stderr.strip()}. Stdout: {result.stdout.strip()}"
                logger.error(error_detail)
                raise Exception(error_detail)
                
            logger.info(f"Successfully committed changes: {commit_message.splitlines()[0]}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed during commit process: {e.cmd} - {e.stderr}")
            raise
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            raise
    
    def _push_branch(self, branch_name: str):
        """Push branch to remote repository"""
        cmd = ['git', 'push', '-u', 'origin', branch_name] # Use -u to set upstream
        result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            error_message = f"Git push failed for branch {branch_name}. Stderr: {result.stderr.strip()}. Stdout: {result.stdout.strip()}"
            logger.error(error_message)
            # Check for common non-fatal errors like "already exists" if -f is not used
            if "already exists" in result.stderr and "set upstream" in result.stderr:
                 logger.warning(f"Branch {branch_name} may already exist on remote or upstream not set correctly. Push may have partially succeeded.")
                 # Don't raise exception here, PR creation might still be possible or desired.
            else:
                raise Exception(error_message)
        else:
            logger.info(f"Successfully pushed branch {branch_name} to origin.")
    
    def _create_pull_request(self, issue: BugIssue, branch_name: str, fix_analysis: Dict, base_branch: str) -> Optional[str]:
        """Create a pull request for the fix"""
        try:
            url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls"
            
            pr_title = f"Fix #{issue.number}: {self._generate_commit_title(issue, fix_analysis)}"
            
            # Construct PR body
            pr_body_parts = [
                f"## Automated Bug Fix for Issue #{issue.number}",
                f"**Closes:** #{issue.number}",
                f"**Issue URL:** {issue.url}",
                "\n### Problem Description (from issue):",
                f"> {issue.body.strip() if issue.body else 'No detailed description provided in the issue.'}",
                "\n### AI Analysis & Fix:",
                f"**Analysis:** {fix_analysis.get('analysis', 'N/A')}",
                f"**Root Cause Identified:** {fix_analysis.get('root_cause', 'N/A')}",
                f"**Fix Strategy:** {fix_analysis.get('fix_strategy', 'N/A')}",
                f"**Explanation of Changes:** {fix_analysis.get('explanation', 'Automated fix applied by AI agent.')}",
            ]

            modified_files_list = fix_analysis.get('files_to_modify', [])
            if modified_files_list:
                pr_body_parts.append("\n### Files Modified:")
                for f_item in modified_files_list:
                    pr_body_parts.append(f"- `{f_item.get('file', 'Unknown file')}`")
            
            pr_body_parts.append("\n---\n*This pull request was generated automatically by the AI Bug Fixer Agent.*")
            pr_body = "\n".join(pr_body_parts)

            pr_data = {
                'title': pr_title,
                'head': f"{self.repo_owner}:{branch_name}" if ":" not in branch_name else branch_name, # GH sometimes needs owner:branch
                'base': base_branch,
                'body': pr_body,
                'maintainer_can_modify': True,
                # 'draft': False # Set to true if you want draft PRs
            }
            
            response = requests.post(url, headers=self.github_headers, json=pr_data)
            
            if response.status_code == 201: # Created
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
                    pass # Keep original text content
                
                logger.error(f"Failed to create pull request (HTTP {response.status_code}): {response_content}")
                # Check if PR already exists for this branch
                if "A pull request already exists" in response_content:
                    logger.warning(f"A PR for branch {branch_name} might already exist.")
                    # Try to find existing PR
                    # This is complex, for now just return None
                return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API error during pull request creation: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error creating pull request: {e}", exc_info=True)
            return None
    
    def _identify_relevant_files(self, issue: BugIssue) -> List[str]:
        """(Helper - currently not directly used in core fix loop but can be for advanced AI context)
        Identify files that are likely relevant to the issue for more targeted AI analysis."""
        # This method is complex and error-prone if not carefully implemented.
        # For now, the AI gets general codebase info.
        # A future enhancement could use AI to suggest relevant files first, then fetch their content.
        logger.info(f"Identifying relevant files for issue #{issue.number} (basic implementation).")
        relevant_files = []
        
        # Simple keyword search in issue title and body for file extensions or common names
        issue_text = f"{issue.title.lower()} {issue.body.lower() if issue.body else ''}"
        
        # A more robust way would be to list all files in repo and match against terms
        # For now, a placeholder for more advanced logic
        common_extensions = ['.py', '.js', '.ts', '.java', '.html', '.css', '.go', '.rb']
        found_by_ext = set()
        for ext in common_extensions:
            if ext in issue_text:
                # This is very naive, would need to find actual filenames
                # Example: find all *.py files if ".py" is mentioned
                pass 

        # Try to find full filenames mentioned (e.g., "main.py", "src/utils.js")
        import re
        # Regex for typical file paths (simplified)
        # This regex is basic and might catch non-filenames or miss complex ones.
        # It looks for sequences like path/to/file.ext
        file_path_pattern = r'([\w\-\./]+\.[\w]+)' 
        potential_files = re.findall(file_path_pattern, issue_text)
        
        for pf in potential_files:
            # Basic validation: check if it looks like a plausible relative path and exists
            clean_pf = pf.strip('\'"` .,:;()[]{}')
            if not clean_pf or 'http' in clean_pf or clean_pf.startswith('/'): # Avoid URLs or absolute paths
                continue
            
            # Check if file exists in the cloned repo
            # This requires self.repo_path to be set up
            if self.repo_path and (Path(self.repo_path) / clean_pf).is_file():
                relevant_files.append(clean_pf)
            # Heuristic: if it has a common extension and isn't clearly not a file
            elif any(clean_pf.endswith(ext) for ext in common_extensions) and len(clean_pf.split('/')[-1]) > 2 :
                 relevant_files.append(clean_pf) # Add even if not verifiable, AI can filter

        relevant_files = list(set(relevant_files))[:5] # Limit to a few
        logger.info(f"Potentially relevant files for issue #{issue.number} based on text: {relevant_files}")
        return relevant_files
    
    def _validate_ai_response(self, response: Dict) -> bool:
        """Validate AI response has required structure for a fix."""
        if not isinstance(response, dict):
            logger.error("AI response is not a dictionary.")
            return False

        required_top_level_fields = ['analysis', 'root_cause', 'fix_strategy', 'files_to_modify', 'explanation']
        for field in required_top_level_fields:
            if field not in response:
                logger.error(f"Missing required field in AI response: '{field}'")
                return False
        
        if not isinstance(response['files_to_modify'], list):
            logger.error("'files_to_modify' must be a list.")
            return False
        
        for i, file_mod in enumerate(response['files_to_modify']):
            if not isinstance(file_mod, dict):
                logger.error(f"Item at index {i} in 'files_to_modify' is not a dictionary.")
                return False
            
            if 'file' not in file_mod or not isinstance(file_mod['file'], str) or not file_mod['file'].strip():
                logger.error(f"Item at index {i} in 'files_to_modify' is missing 'file' string or it's empty.")
                return False
            if 'new_content' not in file_mod or not isinstance(file_mod['new_content'], str): # Allow empty string for new_content
                logger.error(f"Item at index {i} in 'files_to_modify' is missing 'new_content' string (file: {file_mod.get('file')}).")
                return False
        
        logger.debug("AI response structure validated successfully.")
        return True
    
    def run(self, limit_issues: Optional[int] = None):
        """Main execution method - fix all bugs autonomously with individual commits and PRs"""
        logger.info("Starting Autonomous Bug Fixer Agent")
        
        try:
            # Setup workspace
            self.setup_workspace() # This sets self.repo_path
            if not self.repo_path:
                logger.error("Workspace setup failed. Exiting.")
                return

            default_branch = self._get_default_branch() # Determine default branch once
            logger.info(f"Determined default branch for repository: {default_branch}")

            # Get open issues that qualify for fixing
            issues_to_fix = self.get_open_issues()
            if not issues_to_fix:
                logger.info("No open issues found that qualify for fixing (e.g., no linked open PRs).")
                self.cleanup_workspace()
                return
            
            # Apply limit if specified
            if limit_issues is not None and limit_issues > 0:
                if len(issues_to_fix) > limit_issues:
                    logger.info(f"Limiting to the first {limit_issues} of {len(issues_to_fix)} suitable issues.")
                    issues_to_fix = issues_to_fix[:limit_issues]
                else:
                    logger.info(f"Processing all {len(issues_to_fix)} suitable issues (limit was {limit_issues}).")
            else:
                logger.info(f"Found {len(issues_to_fix)} open, suitable issues to process.")
            
            # Analyze codebase once (can be time-consuming)
            logger.info("Analyzing codebase structure and key components...")
            codebase_info = self.analyze_codebase()
            if not codebase_info:
                logger.warning("Codebase analysis returned empty. AI context will be limited.")

            # Fix each bug individually
            results = []
            for i, issue in enumerate(issues_to_fix, 1):
                logger.info(f"--- Processing issue {i}/{len(issues_to_fix)}: #{issue.number} - {issue.title} ---")
                
                # Ensure we're on a clean default branch before starting work on a new issue
                self._ensure_clean_default_branch(default_branch)
                
                # Fix the individual bug
                result = self.fix_bug(issue, codebase_info) # fix_bug handles its own branching
                results.append(result)
                
                if result.success:
                    logger.info(f"[SUCCESS] Fix attempt for issue #{issue.number} completed. PR URL (if any): {result.pr_url}")
                else:
                    logger.error(f"[FAILED] Failed to fix issue #{issue.number}: {result.error_message}")
                
                # Brief pause between fixes to be kind to APIs and allow for observation
                if i < len(issues_to_fix): # No sleep after the last issue
                    sleep_duration = 10
                    logger.info(f"Pausing for {sleep_duration} seconds before next issue...")
                    time.sleep(sleep_duration)
            
            # Print comprehensive summary
            self._print_summary(results)
            
        except Exception as e:
            logger.error(f"A fatal error occurred in the agent's main run loop: {e}", exc_info=True)
            # No raise here, main() will catch and exit.
        finally:
            logger.info("Cleaning up workspace...")
            self.cleanup_workspace()
            logger.info("Autonomous Bug Fixer Agent run finished.")
    
    def _ensure_clean_default_branch(self, default_branch_name: str):
        """Ensure we're on a clean default branch (e.g., main or master)."""
        try:
            logger.info(f"Ensuring clean state on default branch '{default_branch_name}'.")
            # Discard any local changes if any (should not happen if logic is correct)
            subprocess.run(['git', 'reset', '--hard'], cwd=self.repo_path, capture_output=True, text=True, check=False)
            
            # Checkout default branch
            checkout_cmd = ['git', 'checkout', default_branch_name]
            result = subprocess.run(checkout_cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.warning(f"Could not checkout {default_branch_name}, attempting to pull. Error: {result.stderr}")

            # Pull latest changes for the default branch
            pull_cmd = ['git', 'pull', 'origin', default_branch_name]
            result = subprocess.run(pull_cmd, cwd=self.repo_path, capture_output=True, text=True, check=False)
            if result.returncode != 0:
                logger.warning(f"Could not pull latest changes for {default_branch_name}. Proceeding with local version. Error: {result.stderr}")
            else:
                logger.info(f"Successfully checked out and updated {default_branch_name}.")

        except Exception as e:
            logger.warning(f"Could not ensure clean default branch {default_branch_name}: {e}", exc_info=True)
    
    def _print_summary(self, results: List[FixResult]):
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
        print(f"Repository: {self.repo_owner}/{self.repo_name}")
        print(f"Total Issues Processed: {len(results)}")
        print(f"Successfully Fixed (Code Pushed): {len(successful)}")
        print(f"Failed to Fix: {len(failed)}")
        print("-" * 80)
        
        if successful:
            print("\nSUCCESSFUL FIX ATTEMPTS (Code Pushed):")
            for result in successful:
                print(f"  [SUCCESS] Issue #{result.issue_number}")
                print(f"     Branch: {result.branch_name}")
                print(f"     Files Modified: {', '.join(result.files_modified) if result.files_modified else 'None'}")
                print(f"     Commit: \"{result.commit_message.splitlines()[0]}\"")
                if result.pr_url:
                    print(f"     Pull Request: {result.pr_url}")
                else:
                    print(f"     Pull Request: Not created or creation failed (branch pushed).")
                print()
        
        if failed:
            print("\nFAILED FIX ATTEMPTS:")
            for result in failed:
                print(f"  [FAILED] Issue #{result.issue_number}")
                print(f"     Branch Attempted: {result.branch_name}")
                print(f"     Error: {result.error_message}")
                print()
        print("="*80)
        print("Summary complete. Check bug_fixer.log for detailed logs.")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Autonomous AI Bug Fixer Agent. Fixes open GitHub issues without existing open PRs.')
    parser.add_argument('--config', default='.env', help='Path to the .env configuration file (default: .env)')
    parser.add_argument('--repo', help='Target repository in "owner/name" format (e.g., "octocat/Spoon-Knife"). Overrides .env settings.')
    # --dry-run is a bit tricky as the core logic involves cloning and AI calls. 
    # A true dry-run would only list issues it *would* process.
    parser.add_argument('--dry-run', action='store_true', 
                        help='List issues that would be processed, without making any changes or AI calls. Clones repo for issue filtering.')
    parser.add_argument('--limit', type=int, help='Limit the number of issues to attempt to fix in a single run.')
    
    args = parser.parse_args()
    
    try:
        # Override REPO_OWNER and REPO_NAME from .env if --repo is provided
        if args.repo:
            if '/' not in args.repo:
                print("Error: --repo argument must be in 'owner/name' format.")
                sys.exit(1)
            owner, name = args.repo.split('/', 1)
            os.environ['REPO_OWNER'] = owner
            os.environ['REPO_NAME'] = name
            logger.info(f"Overriding repository from command line: {owner}/{name}")
        
        agent = AutonomousBugFixer(config_file=args.config)
        
        if args.dry_run:
            print("\n--- DRY RUN MODE ---")
            logger.info("Starting DRY RUN. Will identify issues but not attempt fixes or create PRs.")
            try:
                agent.setup_workspace() # Needed to determine default branch for some logic, and for issue filtering if it uses local git info
                if not agent.repo_path:
                    print("Dry run: Workspace setup failed. Cannot list issues accurately.")
                    logger.error("Dry run: Workspace setup failed.")
                    return

                issues = agent.get_open_issues() # This will perform the filtering logic
                if issues:
                    print(f"\nFound {len(issues)} open issues that currently have no associated open PRs and would be processed:")
                    for i, issue in enumerate(issues):
                        print(f"  {i+1}. Issue #{issue.number}: {issue.title} ({issue.url})")
                        if args.limit and i + 1 >= args.limit:
                            print(f"  ...and potentially more (limit of {args.limit} reached for display).")
                            break
                else:
                    print("No open issues found that meet the criteria for processing.")
                print("\n--- END OF DRY RUN ---")
            finally:
                agent.cleanup_workspace()
        else:
            agent.run(limit_issues=args.limit)
            
    except ValueError as ve: # Config errors
        logger.error(f"Configuration error: {ve}")
        print(f"Error: {ve}. Please check your .env file or command line arguments.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user. Cleaning up...")
        # Agent cleanup might be handled by its own finally block if run was started
        sys.exit(130) # Standard exit code for Ctrl+C
    except Exception as e:
        logger.error(f"An unexpected critical error occurred in main: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}. Check bug_fixer.log for details.")
        sys.exit(1)

if __name__ == '__main__':
    main()