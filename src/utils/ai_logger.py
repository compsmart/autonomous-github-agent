"""
AI Response Logger - Dedicated logging for AI model responses
"""
import logging
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

class AIResponseLogger:
    """Specialized logger for AI model responses"""
    
    def __init__(self, log_file: str = "ai_responses.log"):
        self.log_file = log_file
        self.logger = self._setup_logger()
    
    def _setup_logger(self) -> logging.Logger:
        """Set up dedicated AI response logger"""
        logger = logging.getLogger('ai_responses')
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplicates
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Create file handler
        handler = logging.FileHandler(self.log_file, encoding='utf-8')
        handler.setLevel(logging.INFO)
        
        # Create formatter for AI responses
        formatter = logging.Formatter(
            '%(asctime)s - AI_RESPONSE - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        logger.propagate = False  # Don't propagate to root logger
        
        return logger
    
    def log_bug_analysis_request(self, issue_number: int, issue_title: str, model_name: str):
        """Log the start of a bug analysis request"""
        self.logger.info(f"=== BUG ANALYSIS REQUEST ===")
        self.logger.info(f"Issue: #{issue_number} - {issue_title}")
        self.logger.info(f"Model: {model_name}")
        self.logger.info(f"Timestamp: {datetime.now().isoformat()}")
        self.logger.info(f"=" * 50)
    
    def log_bug_analysis_response(self, issue_number: int, raw_response: str, parsed_response: Optional[Dict[str, Any]] = None):
        """Log AI response for bug analysis"""
        self.logger.info(f"--- RAW AI RESPONSE (Issue #{issue_number}) ---")
        self.logger.info(raw_response)
        self.logger.info(f"--- END RAW RESPONSE ---")
        
        if parsed_response:
            self.logger.info(f"--- PARSED RESPONSE (Issue #{issue_number}) ---")
            self.logger.info(json.dumps(parsed_response, indent=2))
            self.logger.info(f"--- END PARSED RESPONSE ---")
        
        self.logger.info(f"")  # Empty line for separation
    def log_code_review_request(self, pr_number, pr_title: str, model_name: str):
        """Log the start of a code review request"""
        self.logger.info(f"=== CODE REVIEW REQUEST ===")
        self.logger.info(f"PR: #{pr_number} - {pr_title}")
        self.logger.info(f"Model: {model_name}")
        self.logger.info(f"Timestamp: {datetime.now().isoformat()}")
        self.logger.info(f"=" * 50)
    
    def log_code_review_response(self, pr_number, raw_response: str, parsed_response: Optional[Dict[str, Any]] = None):
        """Log AI response for code review"""
        self.logger.info(f"--- RAW AI RESPONSE (PR #{pr_number}) ---")
        self.logger.info(raw_response)
        self.logger.info(f"--- END RAW RESPONSE ---")
        
        if parsed_response:
            self.logger.info(f"--- PARSED RESPONSE (PR #{pr_number}) ---")
            self.logger.info(json.dumps(parsed_response, indent=2))
            self.logger.info(f"--- END PARSED RESPONSE ---")
        
        self.logger.info(f"")  # Empty line for separation
    
    def log_ai_error(self, request_type: str, identifier: str, error: str):
        """Log AI request errors"""
        self.logger.error(f"=== AI ERROR ===")
        self.logger.error(f"Type: {request_type}")
        self.logger.error(f"Identifier: {identifier}")
        self.logger.error(f"Error: {error}")
        self.logger.error(f"Timestamp: {datetime.now().isoformat()}")
        self.logger.error(f"=" * 30)
        self.logger.error(f"")
    
    def log_prompt_context(self, request_type: str, identifier: str, prompt: str):
        """Log the full prompt sent to AI (optional, for debugging)"""
        self.logger.info(f"=== PROMPT CONTEXT ({request_type} - {identifier}) ===")
        self.logger.info(prompt)
        self.logger.info(f"=== END PROMPT CONTEXT ===")
        self.logger.info(f"")

# Global AI logger instance
ai_logger = AIResponseLogger()
