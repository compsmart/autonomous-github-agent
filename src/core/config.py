"""
Configuration management for the bug fixer agent
"""
import os
import logging
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration for the bug fixer agent"""
    github_token: str
    gemini_api_key: str
    repo_owner: str
    repo_name: str
    system_instructions: Optional[str] = None
    use_fast_model: bool = False
    
    @property
    def repo_url(self) -> str:
        """Get the repository URL"""
        return f"https://github.com/{self.repo_owner}/{self.repo_name}.git"
    
    @property
    def repo_full_name(self) -> str:
        """Get the full repository name"""
        return f"{self.repo_owner}/{self.repo_name}"


class ConfigLoader:
    """Load configuration from environment variables"""
    
    @staticmethod
    def load_from_env(config_file: str = '.env', use_fast_model: bool = False) -> Config:
        """Load configuration from environment variables"""
        load_dotenv(config_file)
        
        github_token = os.getenv('GITHUB_TOKEN')
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        
        if not github_token:
            raise ValueError("GITHUB_TOKEN not found in environment variables")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        # Handle both GITHUB_REPO format and separate REPO_OWNER/REPO_NAME
        github_repo = os.getenv('GITHUB_REPO')
        if github_repo:
            if '/' in github_repo:
                repo_owner, repo_name = github_repo.split('/', 1)
            else:
                raise ValueError("GITHUB_REPO must be in format 'owner/repo'")
        else:
            repo_owner = os.getenv('REPO_OWNER', 'compsmart')
            repo_name = os.getenv('REPO_NAME', 'bug-fixer')
        
        system_instructions = os.getenv('SYSTEM_INSTRUCTIONS') or ConfigLoader._get_default_instructions()
        
        logger.info(f"Configuration loaded for repository: {repo_owner}/{repo_name}")        
        return Config(
            github_token=github_token,
            gemini_api_key=gemini_api_key,
            repo_owner=repo_owner,
            repo_name=repo_name,
            system_instructions=system_instructions,
            use_fast_model=use_fast_model
        )
    
    @staticmethod
    def _get_default_instructions() -> str:
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
