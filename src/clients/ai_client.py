"""
AI client for bug analysis and fixing using Google Gemini
"""
import json
import logging
from typing import Optional
import google.generativeai as genai

from ..models.bug_models import BugIssue, CodebaseInfo, FixAnalysis

logger = logging.getLogger(__name__)


class AIClient:
    """Client for interacting with Google Gemini AI"""
    
    def __init__(self, api_key: str, system_instructions: str,
                 use_fast_model: bool = False):
        self.api_key = api_key
        self.system_instructions = system_instructions
        self.use_fast_model = use_fast_model
        self._initialize_model()

    def _initialize_model(self):
        """Initialize Google Gemini AI model"""
        try:
            genai.configure(api_key=self.api_key)
            
            # Choose model based on fast mode setting
            if self.use_fast_model:
                # Use fast flash model
                model_name = 'gemini-2.5-flash-preview-05-20'
                logger.info("Using fast model: gemini-2.5-flash-preview-05-20")
            else:
                # Use pro model (preferred as per user instructions)
                model_name = 'gemini-2.5-pro-preview-05-06'
                logger.info("Using pro model: gemini-2.5-pro-preview-05-06")
            
            self.model = genai.GenerativeModel(
                model_name,
                system_instruction=self.system_instructions
            )
            logger.info(f"AI model initialized successfully with {model_name}")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI model: {e}")
            # Fallback logic based on fast mode
            try:
                if self.use_fast_model:
                    # If fast mode failed, try the other flash model
                    fallback_model = 'gemini-1.5-flash'
                    logger.info("Falling back to gemini-1.5-flash")
                else:
                    # If pro mode failed, try flash model
                    fallback_model = 'gemini-2.5-flash-preview-05-20'
                    logger.info("Falling back to gemini-2.5-flash-preview-05-20")
                
                self.model = genai.GenerativeModel(
                    fallback_model,
                    system_instruction=self.system_instructions
                )
                logger.info(f"Fallback to {fallback_model} model successful")
                
            except Exception as fallback_error:
                logger.error(f"Failed to initialize fallback AI model: {fallback_error}")
                # Final fallback to most stable model
                try:
                    self.model = genai.GenerativeModel(
                        'gemini-1.5-pro',
                        system_instruction=self.system_instructions
                    )
                    logger.info("Final fallback to gemini-1.5-pro model successful")
                except Exception as final_error:
                    logger.error(f"All model initialization attempts failed: {final_error}")
                    raise
    
    def analyze_bug_and_generate_fix(self, issue: BugIssue, codebase_info: CodebaseInfo, repo_owner: str, repo_name: str) -> Optional[FixAnalysis]:
        """Use AI to analyze the bug and generate a fix"""
        try:
            context = self._build_analysis_context(issue, codebase_info, repo_owner, repo_name)
            
            logger.info(f"Sending analysis request to AI for issue #{issue.number}")
            
            # Configure safety settings for code generation
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
            
            response = self.model.generate_content(context, safety_settings=safety_settings)
            response_text = response.text
            
            logger.debug(f"AI Raw Response for issue #{issue.number}:\n{response_text}")

            # Extract JSON from response
            json_text = self._extract_json_from_response(response_text)
            
            try:
                parsed_response = json.loads(json_text)
                fix_analysis = FixAnalysis(
                    analysis=parsed_response.get('analysis', ''),
                    root_cause=parsed_response.get('root_cause', ''),
                    fix_strategy=parsed_response.get('fix_strategy', ''),
                    files_to_modify=parsed_response.get('files_to_modify', []),
                    explanation=parsed_response.get('explanation', '')
                )
                
                if fix_analysis.is_valid():
                    logger.info(f"AI analysis and fix proposal received for issue #{issue.number}")
                    return fix_analysis
                else:
                    logger.error(f"AI response for issue #{issue.number} failed validation")
                    return None
                    
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON for issue #{issue.number}: {e}")
                logger.debug(f"Problematic JSON text: {json_text}")
                return None
                
        except Exception as e:
            logger.error(f"AI analysis failed for issue #{issue.number}: {e}")
            return None
    
    def _build_analysis_context(self, issue: BugIssue, codebase_info: CodebaseInfo, repo_owner: str, repo_name: str) -> str:
        """Build the context prompt for AI analysis"""
        dependencies_json = json.dumps(codebase_info.dependencies, indent=2) if codebase_info.dependencies else "N/A"
        
        return f"""
You are an AI Software Engineer. Your task is to fix a bug in a Git repository.
Carefully analyze the provided repository information and the specific issue details.
Then, provide a precise fix.

CONTEXT:
Repository: {repo_owner}/{repo_name}
Main programming languages: {', '.join(codebase_info.languages) if codebase_info.languages else 'N/A'}
Key files (examples): {', '.join(codebase_info.key_files) if codebase_info.key_files else 'N/A'}
Dependencies (examples): {dependencies_json}
Directory Structure (partial):
{codebase_info.structure}

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
    
    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from AI response, handling markdown code blocks"""
        if "```json" in response_text:
            return response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            return response_text.split("```")[1].split("```")[0].strip()
        else:
            return response_text
