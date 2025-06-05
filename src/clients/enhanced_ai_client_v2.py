"""
Enhanced AI client for targeted bug analysis and fixing using Google Gemini
This version reads actual file contents and makes minimal, targeted changes
"""
import json
import logging
from typing import Optional, List, Dict
import google.generativeai as genai

from ..models.bug_models import BugIssue, CodebaseInfo, ImprovedFixAnalysis, TargetedFix
from ..models.review_models import ReviewAnalysis
from ..utils.ai_logger import ai_logger

logger = logging.getLogger(__name__)


class EnhancedAIClient:
    """Enhanced client for targeted bug fixing with Google Gemini AI"""
    
    def __init__(self, api_key: str, system_instructions: str, use_fast_model: bool = False):
        self.api_key = api_key
        self.system_instructions = system_instructions
        self.use_fast_model = use_fast_model
        self.current_model_name = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize Google Gemini AI model"""
        try:
            genai.configure(api_key=self.api_key)
            
            if self.use_fast_model:
                model_name = 'gemini-2.5-flash-preview-05-20'
                logger.info("Using fast model: gemini-2.5-flash-preview-05-20")
            else:
                model_name = 'gemini-2.5-pro-preview-05-06'
                logger.info("Using pro model: gemini-2.5-pro-preview-05-06")
            
            self.model = genai.GenerativeModel(
                model_name,
                system_instruction=self.system_instructions
            )
            self.current_model_name = model_name
            logger.info(f"Enhanced AI model initialized successfully with {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI model: {e}")
            raise

    def analyze_bug_with_file_contents(
        self, 
        issue: BugIssue, 
        codebase_info: CodebaseInfo, 
        file_contents: Dict[str, str],
        repo_owner: str, 
        repo_name: str
    ) -> Optional[ImprovedFixAnalysis]:
        """Use AI to analyze the bug with actual file contents and generate targeted fixes"""
        try:
            context = self._build_enhanced_analysis_context(
                issue, codebase_info, file_contents, repo_owner, repo_name
            )
            
            model_name = self.current_model_name or "unknown"
            ai_logger.log_bug_analysis_request(issue.number, issue.title, model_name)
            ai_logger.log_prompt_context("ENHANCED_BUG_ANALYSIS", f"#{issue.number}", context)
            
            logger.info(f"Sending enhanced analysis request to AI for issue #{issue.number}")
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            response = self.model.generate_content(context, safety_settings=safety_settings)
            
            if not response or not response.text:
                logger.error("Empty response from AI")
                return None
            
            ai_logger.log_bug_analysis_response(issue.number, response.text)
            
            # Parse the enhanced JSON response
            json_text = self._extract_json_from_response(response.text)
            parsed_response = json.loads(json_text)
            
            ai_logger.log_bug_analysis_response(issue.number, response.text, parsed_response)
            
            # Convert to ImprovedFixAnalysis
            targeted_fixes = []
            for fix_data in parsed_response.get('targeted_fixes', []):
                targeted_fix = TargetedFix(
                    file_path=fix_data.get('file_path', ''),
                    line_number=fix_data.get('line_number'),
                    start_line=fix_data.get('start_line'),
                    end_line=fix_data.get('end_line'),
                    old_content=fix_data.get('old_content', ''),
                    new_content=fix_data.get('new_content', ''),
                    fix_type=fix_data.get('fix_type', 'replace'),
                    explanation=fix_data.get('explanation', '')
                )
                targeted_fixes.append(targeted_fix)
            
            fix_analysis = ImprovedFixAnalysis(
                analysis=parsed_response.get('analysis', ''),
                root_cause=parsed_response.get('root_cause', ''),
                fix_strategy=parsed_response.get('fix_strategy', ''),
                targeted_fixes=targeted_fixes,
                explanation=parsed_response.get('explanation', ''),
                confidence_score=parsed_response.get('confidence_score', 0.8)
            )
            
            if not fix_analysis.is_valid():
                logger.error("AI response validation failed")
                return None
            
            logger.info(f"Successfully analyzed issue #{issue.number} with {len(targeted_fixes)} targeted fixes")
            return fix_analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response as JSON: {e}")
            ai_logger.log_ai_error("BUG_ANALYSIS", str(issue.number), f"JSON Parse Error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            ai_logger.log_ai_error("BUG_ANALYSIS", str(issue.number), f"Analysis Error: {e}")
            return None

    def _build_enhanced_analysis_context(
        self, 
        issue: BugIssue, 
        codebase_info: CodebaseInfo, 
        file_contents: Dict[str, str],
        repo_owner: str, 
        repo_name: str
    ) -> str:
        """Build enhanced analysis context with actual file contents"""
        
        dependencies_json = "N/A"
        if codebase_info.dependencies:
            try:
                dependencies_json = json.dumps(codebase_info.dependencies, indent=2)[:500]
            except Exception:
                dependencies_json = str(codebase_info.dependencies)[:500]
        
        # Build file contents section
        file_contents_section = ""
        if file_contents:
            file_contents_section = "\n\nACTUAL FILE CONTENTS:\n"
            for file_path, content in file_contents.items():
                file_contents_section += f"\n--- FILE: {file_path} ---\n"
                file_contents_section += content[:10000]  # Limit content size
                if len(content) > 10000:
                    file_contents_section += "\n... (content truncated)"
                file_contents_section += "\n--- END FILE ---\n"
        
        return f"""
You are an expert software engineer. Your task is to fix a bug with MINIMAL, TARGETED changes.

CRITICAL RULES:
1. Make the SMALLEST possible change to fix the issue
2. PRESERVE all existing functionality
3. Only modify the specific problematic code
4. Do NOT rewrite entire files
5. Focus on the exact problem described

CONTEXT:
Repository: {repo_owner}/{repo_name}
Main programming languages: {', '.join(codebase_info.languages) if codebase_info.languages else 'N/A'}
Key files: {', '.join(codebase_info.key_files) if codebase_info.key_files else 'N/A'}
Dependencies: {dependencies_json}

Directory Structure:
{codebase_info.structure}
{file_contents_section}

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
1. **Analyze**: Understand the specific problem
2. **Locate**: Find the exact problematic code using the file contents provided
3. **Target**: Identify the minimal change needed
4. **Preserve**: Ensure no existing functionality is lost

OUTPUT FORMAT (Strict JSON):
{{
  "analysis": "Detailed analysis of the bug and its impact",
  "root_cause": "Specific root cause of the bug",
  "fix_strategy": "Strategy for minimal targeted fix",
  "targeted_fixes": [
    {{
      "file_path": "path/to/file.ext",
      "line_number": 123,
      "old_content": "exact code to be replaced",
      "new_content": "exact replacement code",
      "fix_type": "replace",
      "explanation": "Why this specific change fixes the issue"
    }}
  ],
  "explanation": "Overall explanation of the fix",
  "confidence_score": 0.95
}}

IMPORTANT:
- Use exact line numbers when possible
- Make minimal changes only
- Preserve all formatting and style
- Test logic should remain unchanged unless it's the bug
- old_content must match exactly what's in the file
- If old_content might appear multiple times, include 3-5 lines of context before and after to make it unique
- For CSS/HTML: include the full rule or element to avoid ambiguity
- For code: include the full function signature or class definition when targeting methods
""" 
    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from AI response, handling markdown code blocks"""
        if "```json" in response_text:
            return response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            return response_text.split("```")[1].split("```")[0].strip()
        else:
            return response_text

    def analyze_code_changes(self, pr_title: str, pr_body: str, file_changes: list, pr_number: int) -> Optional[ReviewAnalysis]:
        """Analyze code changes in a pull request for review
        
        Args:
            pr_title: Title of the pull request
            pr_body: Description/body of the pull request  
            file_changes: List of FileChange objects with the changes
            pr_number: Pull request number
            
        Returns:
            ReviewAnalysis object with the review results
        """
        try:
            # Build the prompt for code review
            files_content = ""
            for file_change in file_changes:
                files_content += f"\n\n--- File: {file_change.filename} ---\n"
                files_content += f"Status: {file_change.status}\n"
                files_content += f"Changes: +{file_change.additions} -{file_change.deletions}\n"
                if hasattr(file_change, 'patch') and file_change.patch:
                    files_content += f"Patch:\n{file_change.patch}\n"
                else:
                    files_content += "No patch data available\n"

            prompt = f"""
PULL REQUEST CODE REVIEW

**PR Title:** {pr_title}

**PR Description:**
{pr_body if pr_body else "No description provided."}

**Changed Files:**
{files_content}

INSTRUCTIONS:
1. **Review Quality**: Assess code quality, best practices, and potential issues
2. **Security Analysis**: Check for security vulnerabilities or concerns
3. **Performance Impact**: Evaluate potential performance implications
4. **Logic Review**: Verify the logic makes sense and handles edge cases
5. **Style & Standards**: Check adherence to coding standards
6. **Overall Assessment**: Provide an overall recommendation

OUTPUT FORMAT (Strict JSON):
Return your response as a single JSON object:
{{
  "overall_quality": "Brief assessment of code quality",
  "security_concerns": ["List of security concerns if any"],
  "performance_issues": ["Performance-related issues"],
  "code_style_issues": ["Style and standards issues"],
  "logic_concerns": ["Logic or correctness issues"],
  "maintainability_issues": ["Maintainability concerns"],
  "positive_aspects": ["List of positive aspects"],
  "suggestions": ["List of improvement suggestions"],
  "complexity_assessment": "Assessment of change complexity",
  "test_coverage_notes": "Notes about test coverage"
}}

Be thorough but constructive in your review.
"""
            
            # Log the request to AI logger
            ai_logger.log_code_review_request(pr_number, pr_title, self.current_model_name)
            ai_logger.log_prompt_context("CODE_REVIEW", f"PR#{pr_number}", prompt)
            
            logger.info(f"Sending code review request to AI for PR #{pr_number}")
            response = self.model.generate_content(prompt)
            response_text = response.text
            
            # Extract JSON from response
            json_text = self._extract_json_from_response(response_text)
            
            try:
                analysis_dict = json.loads(json_text)
                
                # Log AI response to dedicated logger
                ai_logger.log_code_review_response(pr_number, response_text, analysis_dict)
                
                # Convert to ReviewAnalysis object
                review_analysis = ReviewAnalysis(
                    overall_quality=analysis_dict.get("overall_quality", "Code review completed"),
                    security_concerns=analysis_dict.get("security_concerns", []),
                    performance_issues=analysis_dict.get("performance_issues", []),
                    code_style_issues=analysis_dict.get("code_style_issues", []),
                    logic_concerns=analysis_dict.get("logic_concerns", []),
                    maintainability_issues=analysis_dict.get("maintainability_issues", []),
                    positive_aspects=analysis_dict.get("positive_aspects", []),
                    suggestions=analysis_dict.get("suggestions", []),
                    complexity_assessment=analysis_dict.get("complexity_assessment", "Medium complexity"),
                    test_coverage_notes=analysis_dict.get("test_coverage_notes", "Test coverage not assessed")
                )
                
                logger.info(f"Successfully parsed AI code review response for PR #{pr_number}")
                return review_analysis
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Raw response: {response_text}")
                
                # Log the error and raw response
                ai_logger.log_ai_error("CODE_REVIEW", f"PR#{pr_number}", f"JSON parsing failed: {e}")
                ai_logger.log_code_review_response(pr_number, response_text)
                
                # Return a fallback ReviewAnalysis
                return ReviewAnalysis(
                    overall_quality="Unable to parse detailed review, but changes appear reasonable",
                    security_concerns=[],
                    performance_issues=[],
                    code_style_issues=["AI review parsing failed"],
                    logic_concerns=[],
                    maintainability_issues=[],
                    positive_aspects=[],
                    suggestions=["Manual review recommended"],
                    complexity_assessment="Unable to assess",
                    test_coverage_notes="Automated review encountered parsing issues. Please conduct manual review."
                )
                
        except Exception as e:
            logger.error(f"Error during AI code analysis for PR #{pr_number}: {e}")
            ai_logger.log_ai_error("CODE_REVIEW", f"PR#{pr_number}", str(e))
            
            # Return a fallback ReviewAnalysis
            return ReviewAnalysis(
                overall_quality="Error during automated review",
                security_concerns=[],
                performance_issues=[],
                code_style_issues=[],
                logic_concerns=[f"Review error: {str(e)}"],
                maintainability_issues=[],
                positive_aspects=[],
                suggestions=["Manual review required"],
                complexity_assessment="Unable to assess due to error",
                test_coverage_notes=f"Automated review failed with error: {str(e)}"
            )
