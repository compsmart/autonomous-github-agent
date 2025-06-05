"""
Data models for code review functionality
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class PullRequest:
    """Represents a GitHub pull request"""
    number: int
    title: str
    body: str
    url: str
    author: str
    branch: str
    base_branch: str
    created_at: datetime
    updated_at: datetime
    additions: int
    deletions: int
    changed_files: int
    mergeable: bool
    draft: bool
    labels: List[str]
    raw_data: Dict[str, Any]


@dataclass
class FileChange:
    """Represents changes in a single file"""
    filename: str
    status: str  # 'added', 'modified', 'removed', 'renamed'
    additions: int
    deletions: int
    changes: int
    patch: Optional[str]
    previous_filename: Optional[str] = None


@dataclass
class ReviewComment:
    """Represents a single code review comment"""
    file_path: str
    line_number: Optional[int]
    comment: str
    severity: str  # 'info', 'warning', 'error', 'suggestion'
    category: str  # 'security', 'performance', 'style', 'logic', 'maintainability'


@dataclass
class CodeReviewResult:
    """Result of an automated code review"""
    pr_number: int
    overall_assessment: str
    recommendation: str  # 'approve', 'request_changes', 'comment'
    summary: str
    comments: List[ReviewComment]
    score: int  # 1-10 rating
    review_url: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


@dataclass
class ReviewAnalysis:
    """AI analysis of code changes"""
    overall_quality: str
    security_concerns: List[str]
    performance_issues: List[str]
    code_style_issues: List[str]
    logic_concerns: List[str]
    maintainability_issues: List[str]
    positive_aspects: List[str]
    suggestions: List[str]
    complexity_assessment: str
    test_coverage_notes: str
