"""
Data models for bug fixing operations
"""
from dataclasses import dataclass
from typing import List, Optional


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


@dataclass
class CodebaseInfo:
    """Information about the repository codebase"""
    structure: str
    key_files: List[str]
    languages: List[str]
    dependencies: dict


@dataclass
class FixAnalysis:
    """AI analysis result for bug fixing"""
    analysis: str
    root_cause: str
    fix_strategy: str
    files_to_modify: List[dict]
    explanation: str
    
    def is_valid(self) -> bool:
        """Validate the fix analysis structure"""
        if not all([self.analysis, self.root_cause, self.fix_strategy, self.explanation]):
            return False
            
        if not isinstance(self.files_to_modify, list):
            return False
            
        for file_mod in self.files_to_modify:
            if not isinstance(file_mod, dict):
                return False
            if 'file' not in file_mod or not isinstance(file_mod['file'], str) or not file_mod['file'].strip():
                return False
            if 'new_content' not in file_mod or not isinstance(file_mod['new_content'], str):
                return False
                
        return True
