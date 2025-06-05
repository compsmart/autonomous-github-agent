"""
PROPOSED FIX: Modify the AI client to read actual file contents before making changes
"""

# Current broken approach (from ai_client.py):
broken_approach = """
1. Get issue description: "app.js line 163, e.keyCode === 13"
2. Tell AI: "Generate complete new file content"
3. AI hallucinates what it thinks the file should look like
4. Overwrite entire file with AI's guess
5. RESULT: Original functionality destroyed
"""

# Correct approach should be:
correct_approach = """
1. Get issue description: "app.js line 163, e.keyCode === 13"  
2. READ THE ACTUAL FILE CONTENT from the cloned repository
3. Give AI both the issue AND the current file content
4. Ask AI to make MINIMAL targeted changes
5. Apply only the specific fix, preserving everything else
6. RESULT: Bug fixed, functionality preserved
"""

def proposed_fix_for_ai_client():
    """
    The _build_analysis_context method should be modified to:
    1. Read the actual file content when a specific file is mentioned
    2. Include the file content in the prompt
    3. Ask for targeted changes instead of complete rewrites
    """
    
    example_improved_prompt = """
    ISSUE TO FIX:
    File: static/app.js
    Line: 163
    Problem: e.keyCode === 13 (deprecated)
    
    CURRENT FILE CONTENT:
    [ACTUAL FILE CONTENT HERE - 500+ lines of real code]
    
    INSTRUCTIONS:
    Make MINIMAL changes to fix the specific issue.
    Preserve ALL existing functionality.
    Only change the problematic line(s).
    
    OUTPUT FORMAT:
    {
      "target_line": 163,
      "old_code": "if (e.keyCode === 13)",
      "new_code": "if (e.key === 'Enter')",
      "explanation": "Replaced deprecated keyCode with modern key property"
    }
    """
    
    return example_improved_prompt

print("=== PROPOSED SOLUTION ===")
print("\n1. MODIFY CodebaseAnalyzer to read specific files mentioned in issues")
print("2. MODIFY AIClient._build_analysis_context to include actual file contents")  
print("3. CHANGE the prompt to request targeted fixes instead of complete rewrites")
print("4. MODIFY git_operations to apply line-specific changes instead of file overwrites")
print("\n5. This would fix the core issue: preserving existing functionality while fixing bugs")

print("\n=== FILES THAT NEED MODIFICATION ===")
print("- src/utils/codebase_analyzer.py: Add method to read specific files")
print("- src/clients/ai_client.py: Include file contents in prompt")
print("- src/utils/git_operations.py: Support targeted line changes")
print("- Change AI prompt from 'complete file' to 'minimal fix'")
