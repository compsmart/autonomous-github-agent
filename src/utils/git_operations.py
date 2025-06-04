"""
Git operations for the bug fixer agent
"""
import os
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class GitOperations:
    """Handle all Git operations for the bug fixer"""
    
    def __init__(self, repo_url: str, github_token: str):
        self.repo_url = repo_url
        self.github_token = github_token
        self.work_dir: Optional[str] = None
        self.repo_path: Optional[str] = None
        self.repo_name = repo_url.split('/')[-1].replace('.git', '')
        self._default_branch_name: Optional[str] = None
    
    def setup_workspace(self) -> str:
        """Setup workspace by cloning the repository"""
        try:
            # Create temporary working directory
            self.work_dir = tempfile.mkdtemp(prefix='bug_fixer_')
            self.repo_path = os.path.join(self.work_dir, self.repo_name)
            
            logger.info(f"Setting up workspace in {self.work_dir}")
            
            # Clone the repository
            clone_url = f"https://{self.github_token}@{self.repo_url.replace('https://', '')}"
            clone_cmd = ['git', 'clone', clone_url, self.repo_path]
            
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
    def cleanup_workspace(self):
        """Clean up temporary workspace"""
        if self.work_dir and os.path.exists(self.work_dir):
            try:
                # On Windows, git files can be locked, so try multiple approaches
                if os.name == 'nt':  # Windows
                    self._cleanup_workspace_windows()
                else:
                    shutil.rmtree(self.work_dir)
                logger.debug("Workspace cleaned up successfully")
            except Exception as e:
                # Don't show warning for common Windows file permission issues
                if "WinError 5" in str(e) or "Access is denied" in str(e):
                    logger.debug(f"Workspace cleanup completed with some files remaining (Windows file locks): {e}")
                else:
                    logger.warning(f"Failed to cleanup workspace: {e}")
    
    def _cleanup_workspace_windows(self):
        """Clean up workspace on Windows with special handling for git files"""
        import time
        
        # First, try to make all files writable
        try:
            for root, dirs, files in os.walk(self.work_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.chmod(file_path, 0o777)
                    except:
                        pass  # Ignore individual file permission errors
        except:
            pass
        
        # Try to remove the directory
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                shutil.rmtree(self.work_dir)
                return  # Success
            except Exception as e:
                if attempt < max_attempts - 1:
                    time.sleep(0.5)  # Wait a bit for file locks to release
                else:
                    # Final attempt failed - this is expected on Windows with git repos
                    raise e
    
    def _configure_git(self):
        """Configure git for commits"""
        git_commands = [
            ['git', 'config', 'user.name', 'AI Bug Fixer'],
            ['git', 'config', 'user.email', 'ai-bug-fixer@automated.local'],
            ['git', 'config', 'push.default', 'current']
        ]
        
        for cmd in git_commands:
            subprocess.run(cmd, cwd=self.repo_path, capture_output=True)
    
    def get_default_branch(self) -> str:
        """Determine the default branch (main or master) of the repository"""
        if self._default_branch_name:
            return self._default_branch_name

        branches_output = subprocess.run(
            ['git', 'branch', '-r'], 
            cwd=self.repo_path, 
            capture_output=True, 
            text=True
        )
        
        if branches_output.returncode == 0:
            remote_branches = branches_output.stdout.splitlines()
            if any('origin/main' in b for b in remote_branches):
                self._default_branch_name = 'main'
                return 'main'
        
        self._default_branch_name = 'master'
        return 'master'
    
    def create_feature_branch(self, branch_name: str, base_branch: str):
        """Create and switch to a new feature branch from the specified base branch"""
        commands = [
            ['git', 'checkout', base_branch],
            ['git', 'pull', 'origin', base_branch],
            ['git', 'checkout', '-b', branch_name]
        ]
        
        for cmd_idx, cmd in enumerate(commands):
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                if cmd_idx == 1 and ("couldn't find remote ref" in result.stderr or "no upstream" in result.stderr):
                    logger.warning(f"Could not pull remote {base_branch}, proceeding with local version")
                elif cmd_idx == 0 and "did not match any file(s) known to git" in result.stderr:
                    # Try the other common default branch name
                    alternative_base = 'main' if base_branch == 'master' else 'master'
                    logger.warning(f"Base branch {base_branch} not found, trying {alternative_base}")
                    return self.create_feature_branch(branch_name, alternative_base)
                else:
                    raise Exception(f"Git command failed: {' '.join(cmd)}\nStderr: {result.stderr}")
    
    def apply_file_changes(self, file_changes: List[dict]) -> List[str]:
        """Apply file changes to the repository"""
        files_modified = []
        
        try:
            for file_change in file_changes:
                file_path_str = file_change.get('file')
                new_content = file_change.get('new_content')
                
                if not file_path_str or new_content is None:
                    logger.warning(f"Invalid file change: {file_change}")
                    continue

                # Sanitize file path
                file_path_str = file_path_str.lstrip('/')
                if ".." in file_path_str or os.path.isabs(file_path_str):
                    logger.error(f"Invalid file path: {file_path_str}")
                    continue
                
                if not self.repo_path:
                    logger.error("Repository path not set")
                    continue
                    
                full_path = Path(self.repo_path) / file_path_str
                
                try:
                    # Ensure directory exists
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write new content
                    with open(full_path, 'w', encoding='utf-8', newline='') as f:
                        f.write(new_content)
                    
                    files_modified.append(file_path_str)
                    logger.info(f"Applied changes to file: {file_path_str}")
                    
                except IOError as e:
                    logger.error(f"Error writing to file {full_path}: {e}")

            return files_modified
            
        except Exception as e:
            logger.error(f"Failed to apply file changes: {e}")
            return []
    
    def commit_changes(self, commit_message: str, files_modified: List[str]):
        """Commit changes to git"""
        try:
            # Add modified files
            for file_path in files_modified:
                cmd = ['git', 'add', file_path]
                result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Failed to add {file_path}: {result.stderr}")
            
            # Check if there are staged changes
            status_cmd = ['git', 'status', '--porcelain']
            status_result = subprocess.run(status_cmd, cwd=self.repo_path, capture_output=True, text=True)
            
            if not status_result.stdout.strip():
                raise Exception("No changes to commit")
            
            # Commit the changes
            commit_cmd = ['git', 'commit', '-m', commit_message]
            result = subprocess.run(commit_cmd, cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Git commit failed: {result.stderr}")
                
            logger.info(f"Successfully committed changes: {commit_message.splitlines()[0]}")
            
        except Exception as e:
            logger.error(f"Failed to commit changes: {e}")
            raise
    
    def push_branch(self, branch_name: str):
        """Push branch to remote repository"""
        cmd = ['git', 'push', '-u', 'origin', branch_name]
        result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            if "already exists" in result.stderr:
                logger.warning(f"Branch {branch_name} may already exist on remote")
            else:
                raise Exception(f"Git push failed: {result.stderr}")
        else:
            logger.info(f"Successfully pushed branch {branch_name}")
    
    def cleanup_failed_branch(self, branch_name: str, base_branch: str):
        """Clean up failed branch by switching back and deleting it"""
        try:
            logger.info(f"Cleaning up failed branch: {branch_name}")
            # Switch back to base branch
            subprocess.run(['git', 'checkout', base_branch], cwd=self.repo_path, capture_output=True)
            
            # Delete the failed local branch
            delete_result = subprocess.run(
                ['git', 'branch', '-D', branch_name], 
                cwd=self.repo_path, 
                capture_output=True, 
                text=True
            )
            
            if delete_result.returncode == 0:
                logger.info(f"Successfully deleted local branch: {branch_name}")
            else:
                logger.warning(f"Could not delete local branch {branch_name}")

        except Exception as e:
            logger.warning(f"Failed to cleanup branch {branch_name}: {e}")
    
    def ensure_clean_default_branch(self, default_branch_name: str):
        """Ensure we're on a clean default branch"""
        try:
            logger.info(f"Ensuring clean state on default branch '{default_branch_name}'")
            
            # Reset any local changes
            subprocess.run(['git', 'reset', '--hard'], cwd=self.repo_path, capture_output=True)
            
            # Checkout default branch
            checkout_cmd = ['git', 'checkout', default_branch_name]
            result = subprocess.run(checkout_cmd, cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"Could not checkout {default_branch_name}: {result.stderr}")

            # Pull latest changes
            pull_cmd = ['git', 'pull', 'origin', default_branch_name]
            result = subprocess.run(pull_cmd, cwd=self.repo_path, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning(f"Could not pull latest changes for {default_branch_name}")
            else:
                logger.info(f"Successfully updated {default_branch_name}")

        except Exception as e:
            logger.warning(f"Could not ensure clean default branch {default_branch_name}: {e}")
