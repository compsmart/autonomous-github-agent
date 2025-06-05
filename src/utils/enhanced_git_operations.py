"""
Enhanced Git operations for targeted file changes
This version applies minimal, precise changes instead of complete file replacement
"""
import os
import subprocess
import tempfile
import shutil
import logging
from pathlib import Path
from typing import List, Optional, Dict

from ..models.bug_models import TargetedFix

logger = logging.getLogger(__name__)


class EnhancedGitOperations:
    """Enhanced Git operations with targeted file modification support"""
    
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
            self.work_dir = tempfile.mkdtemp(prefix='enhanced_bug_fixer_')
            self.repo_path = os.path.join(self.work_dir, self.repo_name)
            
            logger.info(f"Setting up enhanced workspace in {self.work_dir}")
            
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

    def apply_targeted_fixes(self, targeted_fixes: List[TargetedFix]) -> List[str]:
        """Apply targeted fixes to files instead of complete replacement"""
        files_modified = []
        
        try:
            for fix in targeted_fixes:
                try:
                    success = self._apply_single_targeted_fix(fix)
                    if success:
                        files_modified.append(fix.file_path)
                        logger.info(f"Successfully applied targeted fix to: {fix.file_path}")
                    else:
                        logger.error(f"Failed to apply targeted fix to: {fix.file_path}")
                        
                except Exception as e:
                    logger.error(f"Error applying targeted fix to {fix.file_path}: {e}")
                    continue
            
            return files_modified
            
        except Exception as e:
            logger.error(f"Failed to apply targeted fixes: {e}")
            return []

    def _apply_single_targeted_fix(self, fix: TargetedFix) -> bool:
        """Apply a single targeted fix to a file"""
        try:
            # Sanitize file path
            safe_path = self._sanitize_file_path(fix.file_path)
            if not safe_path:
                logger.error(f"Invalid file path: {fix.file_path}")
                return False
                
            if not self.repo_path:
                logger.error("Repository path not set")
                return False
                
            full_path = Path(self.repo_path) / safe_path
            
            # Ensure file exists
            if not full_path.exists():
                logger.error(f"File does not exist: {fix.file_path}")
                return False
            
            # Read current file content
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                current_content = f.read()
            
            # Apply the fix based on type
            if fix.fix_type == 'replace':
                new_content = self._apply_replace_fix(current_content, fix)
            elif fix.fix_type == 'insert':
                new_content = self._apply_insert_fix(current_content, fix)
            elif fix.fix_type == 'delete':
                new_content = self._apply_delete_fix(current_content, fix)
            else:
                logger.error(f"Unknown fix type: {fix.fix_type}")
                return False
            
            if new_content is None:
                logger.error(f"Failed to apply fix to {fix.file_path}")
                return False
            
            # Verify the change makes sense
            if new_content == current_content:
                logger.warning(f"No changes made to {fix.file_path} - content identical")
                return False
            
            # Write the modified content back
            with open(full_path, 'w', encoding='utf-8', newline='') as f:
                f.write(new_content)
            
            logger.info(f"Applied {fix.fix_type} fix to {fix.file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error in _apply_single_targeted_fix: {e}")
            return False

    def _apply_replace_fix(self, content: str, fix: TargetedFix) -> Optional[str]:
        """Apply a replacement fix"""
        if not fix.old_content:
            logger.error("Replace fix missing old_content")
            return None
        
        # Count occurrences to ensure uniqueness
        occurrences = content.count(fix.old_content)
        if occurrences == 0:
            logger.error(f"old_content not found in file: {fix.file_path}")
            logger.debug(f"Looking for: {repr(fix.old_content)}")
            return None
        elif occurrences > 1:
            logger.error(f"old_content appears {occurrences} times, ambiguous replacement")
            return None
        
        # Perform the replacement
        new_content = content.replace(fix.old_content, fix.new_content)
        logger.info(f"Replaced content in {fix.file_path}: {len(fix.old_content)} chars -> {len(fix.new_content)} chars")
        return new_content

    def _apply_insert_fix(self, content: str, fix: TargetedFix) -> Optional[str]:
        """Apply an insertion fix"""
        lines = content.splitlines(keepends=True)
        
        if fix.line_number is not None:
            # Insert at specific line number
            insert_line = fix.line_number - 1  # Convert to 0-based index
            if 0 <= insert_line <= len(lines):
                lines.insert(insert_line, fix.new_content + '\n')
                return ''.join(lines)
            else:
                logger.error(f"Invalid line number {fix.line_number} for file {fix.file_path}")
                return None
        else:
            # Insert at end of file
            return content + fix.new_content + '\n'

    def _apply_delete_fix(self, content: str, fix: TargetedFix) -> Optional[str]:
        """Apply a deletion fix"""
        if fix.old_content:
            # Delete specific content
            if fix.old_content in content:
                return content.replace(fix.old_content, '')
            else:
                logger.error(f"Content to delete not found in {fix.file_path}")
                return None
        elif fix.line_number is not None:
            # Delete specific line
            lines = content.splitlines(keepends=True)
            delete_line = fix.line_number - 1  # Convert to 0-based index
            if 0 <= delete_line < len(lines):
                del lines[delete_line]
                return ''.join(lines)
            else:
                logger.error(f"Invalid line number {fix.line_number} for deletion")
                return None
        else:
            logger.error("Delete fix missing both old_content and line_number")
            return None

    def _sanitize_file_path(self, file_path: str) -> str:
        """Sanitize file path to prevent directory traversal"""
        if not file_path:
            return ""
            
        # Remove dangerous patterns
        file_path = file_path.replace('..', '').replace('~', '')
        file_path = file_path.lstrip('/')
        
        # Ensure it's a reasonable file path
        if len(file_path) > 200 or not file_path:
            return ""
            
        return file_path

    def create_feature_branch(self, branch_name: str, default_branch: str):
        """Create a new feature branch"""
        try:
            cmd = ['git', 'checkout', '-b', branch_name, f'origin/{default_branch}']
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to create branch: {result.stderr}")
            logger.info(f"Created branch: {branch_name}")
        except Exception as e:
            logger.error(f"Error creating branch: {e}")
            raise

    def commit_changes(self, commit_message: str, files_modified: List[str]):
        """Commit changes to git"""
        try:
            # Add modified files
            for file_path in files_modified:
                cmd = ['git', 'add', file_path]
                result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
                if result.returncode != 0:
                    logger.warning(f"Failed to add file {file_path}: {result.stderr}")
            
            # Commit changes
            cmd = ['git', 'commit', '-m', commit_message]
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to commit: {result.stderr}")
                
            logger.info("Changes committed successfully")
            
        except Exception as e:
            logger.error(f"Error committing changes: {e}")
            raise

    def push_branch(self, branch_name: str):
        """Push branch to remote"""
        try:
            cmd = ['git', 'push', 'origin', branch_name]
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to push branch: {result.stderr}")
            logger.info(f"Branch {branch_name} pushed successfully")
        except Exception as e:
            logger.error(f"Error pushing branch: {e}")
            raise

    def get_default_branch(self) -> str:
        """Get the default branch name"""
        if self._default_branch_name:
            return self._default_branch_name
            
        try:
            cmd = ['git', 'symbolic-ref', 'refs/remotes/origin/HEAD']
            result = subprocess.run(cmd, cwd=self.repo_path, capture_output=True, text=True)
            if result.returncode == 0:
                self._default_branch_name = result.stdout.strip().split('/')[-1]
            else:
                self._default_branch_name = 'main'  # fallback
            return self._default_branch_name
        except Exception:
            return 'main'

    def cleanup_workspace(self):
        """Clean up temporary workspace"""
        if self.work_dir and os.path.exists(self.work_dir):
            try:
                shutil.rmtree(self.work_dir)
                logger.debug("Enhanced workspace cleaned up successfully")
            except Exception as e:
                logger.warning(f"Failed to cleanup workspace: {e}")

    def _configure_git(self):
        """Configure git for commits"""
        try:
            subprocess.run(['git', 'config', 'user.name', 'Enhanced AI Bug Fixer'], 
                          cwd=self.repo_path, check=True)
            subprocess.run(['git', 'config', 'user.email', 'ai-bug-fixer@enhanced.ai'], 
                          cwd=self.repo_path, check=True)
            logger.debug("Git configured successfully")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to configure git: {e}")
            raise
