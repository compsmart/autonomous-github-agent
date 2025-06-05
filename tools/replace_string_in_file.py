#!/usr/bin/env python3
"""
Python script that replicates the replace_string_in_file functionality.
This script can find and replace exact string matches in files.
"""

import os
import sys
import argparse
from typing import Optional


def replace_string_in_file(file_path: str, old_string: str, new_string: str, 
                          encoding: str = 'utf-8') -> tuple[bool, str]:
    """
    Replace a string in a file with a new string.
    
    Args:
        file_path: Path to the file to edit
        old_string: The exact string to be replaced
        new_string: The replacement string
        encoding: File encoding (default: utf-8)
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return False, f"Error: File '{file_path}' does not exist"
        
        # Read the file content
        with open(file_path, 'r', encoding=encoding) as file:
            content = file.read()
        
        # Check if the old string exists in the file
        if old_string not in content:
            return False, f"Error: String not found in file '{file_path}'"
        
        # Count occurrences to ensure uniqueness
        occurrences = content.count(old_string)
        if occurrences > 1:
            return False, f"Error: String appears {occurrences} times in file. Please provide a more specific string that appears only once."
        
        # Replace the string
        new_content = content.replace(old_string, new_string)
        
        # Write the modified content back to the file
        with open(file_path, 'w', encoding=encoding) as file:
            file.write(new_content)
        
        return True, f"Successfully replaced string in '{file_path}'"
    
    except UnicodeDecodeError as e:
        return False, f"Error: Unable to decode file with {encoding} encoding: {e}"
    except PermissionError:
        return False, f"Error: Permission denied to modify file '{file_path}'"
    except Exception as e:
        return False, f"Error: {str(e)}"


def preview_replacement(file_path: str, old_string: str, new_string: str,
                       context_lines: int = 3, encoding: str = 'utf-8') -> tuple[bool, str]:
    """
    Preview what the replacement would look like without making changes.
    
    Args:
        file_path: Path to the file
        old_string: The string to be replaced
        new_string: The replacement string
        context_lines: Number of lines to show before/after the match
        encoding: File encoding
    
    Returns:
        tuple: (success: bool, preview_text: str)
    """
    try:
        if not os.path.exists(file_path):
            return False, f"Error: File '{file_path}' does not exist"
        
        with open(file_path, 'r', encoding=encoding) as file:
            content = file.read()
        
        if old_string not in content:
            return False, f"String not found in file '{file_path}'"
        
        # Split content into lines for context display
        lines = content.split('\n')
        
        # Find the line containing the old string
        match_line_idx = -1
        for i, line in enumerate(lines):
            if old_string in line:
                match_line_idx = i
                break
        
        if match_line_idx == -1:
            return False, "String not found"
        
        # Calculate context range
        start_idx = max(0, match_line_idx - context_lines)
        end_idx = min(len(lines), match_line_idx + context_lines + 1)
        
        # Build preview
        preview = "Preview of changes:\n"
        preview += "=" * 50 + "\n"
        preview += "BEFORE:\n"
        preview += "-" * 20 + "\n"
        
        for i in range(start_idx, end_idx):
            prefix = ">>> " if i == match_line_idx else "    "
            preview += f"{prefix}{i+1:4d}: {lines[i]}\n"
        
        preview += "\nAFTER:\n"
        preview += "-" * 20 + "\n"
        
        # Show what it would look like after replacement
        modified_line = lines[match_line_idx].replace(old_string, new_string)
        for i in range(start_idx, end_idx):
            prefix = ">>> " if i == match_line_idx else "    "
            line_content = modified_line if i == match_line_idx else lines[i]
            preview += f"{prefix}{i+1:4d}: {line_content}\n"
        
        return True, preview
    
    except Exception as e:
        return False, f"Error: {str(e)}"


def main():
    parser = argparse.ArgumentParser(
        description="Replace a string in a file (replicates replace_string_in_file functionality)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python replace_string_in_file.py file.txt "old text" "new text"
  python replace_string_in_file.py --preview file.py "def old_function" "def new_function"
  python replace_string_in_file.py --encoding utf-16 file.txt "old" "new"
        """
    )
    
    parser.add_argument('file_path', help='Path to the file to edit')
    parser.add_argument('old_string', help='The exact string to be replaced')
    parser.add_argument('new_string', help='The replacement string')
    parser.add_argument('--preview', action='store_true', 
                       help='Preview changes without making them')
    parser.add_argument('--encoding', default='utf-8',
                       help='File encoding (default: utf-8)')
    parser.add_argument('--context', type=int, default=3,
                       help='Number of context lines to show in preview (default: 3)')
    
    args = parser.parse_args()
    
    if args.preview:
        success, message = preview_replacement(
            args.file_path, args.old_string, args.new_string, 
            args.context, args.encoding
        )
        print(message)
        return 0 if success else 1
    else:
        success, message = replace_string_in_file(
            args.file_path, args.old_string, args.new_string, args.encoding
        )
        print(message)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
