"""
Codebase analysis utilities for understanding repository structure
"""
import os
import json
import subprocess
import shutil
import logging
from pathlib import Path
from typing import List, Dict

from ..models.bug_models import CodebaseInfo

logger = logging.getLogger(__name__)


class CodebaseAnalyzer:
    """Analyze repository codebase structure and characteristics"""
    
    def __init__(self, repo_path: str):
        self.repo_path = repo_path
    
    def analyze(self) -> CodebaseInfo:
        """Perform complete codebase analysis"""
        try:
            return CodebaseInfo(
                structure=self._get_directory_structure(),
                key_files=self._identify_key_files(),
                languages=self._detect_languages(),
                dependencies=self._get_dependencies()
            )
        except Exception as e:
            logger.error(f"Failed to analyze codebase: {e}")
            return CodebaseInfo(
                structure="Analysis failed",
                key_files=[],
                languages=[],
                dependencies={}
                )

    def _get_directory_structure(self) -> str:
        """Get directory structure of the repository"""
        try:
            # Check if repository path exists and is accessible
            if not self.repo_path or not Path(self.repo_path).exists():
                logger.debug(f"Repository path does not exist: {self.repo_path}")
                return "Repository path not accessible"
            
            # Try tree command first (mainly for Unix/Linux systems)
            if shutil.which('tree'):
                try:
                    result = subprocess.run(
                        ['tree', '-L', '3'], 
                        cwd=self.repo_path, 
                        capture_output=True, 
                        text=True, 
                        check=False,
                        timeout=10  # Add timeout to prevent hanging
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        return result.stdout
                except (subprocess.TimeoutExpired, OSError):
                    logger.debug("Tree command failed, falling back to manual listing")
            
            # Fallback to manual directory listing
            structure = []
            repo_path = Path(self.repo_path)
            
            # Add root directory
            structure.append(f"{repo_path.name}/")
            
            for root, dirs, files in os.walk(self.repo_path):
                root_path = Path(root)
                
                # Skip .git directory and other hidden directories
                if any(part.startswith('.git') for part in root_path.parts):
                    continue
                
                # Calculate relative path from repo root
                try:
                    rel_path = root_path.relative_to(repo_path)
                    level = len(rel_path.parts)
                except ValueError:
                    # Skip if we can't determine relative path
                    continue
                
                if level < 3:  # Limit depth
                    indent = ' ' * 2 * level
                    if level > 0:  # Don't show root again
                        structure.append(f"{indent}{root_path.name}/")
                    
                    subindent = ' ' * 2 * (level + 1)
                    
                    # Show limited files per directory
                    for file_count, file_name in enumerate(files[:10]):  # Limit to first 10 files
                        structure.append(f"{subindent}{file_name}")
                    
                    if len(files) > 10:
                        structure.append(f"{subindent}... ({len(files) - 10} more files)")
                    
                    # Filter and limit directories for next iteration
                    dirs[:] = [d for d in dirs if not d.startswith('.')][:5]
            
            if len(structure) <= 1:  # Only root directory found
                return "Repository structure could not be analyzed"
            
            return '\n'.join(structure)
            
        except PermissionError:
            logger.debug("Permission denied accessing repository directory")
            return "Repository directory access denied"
        except Exception as e:
            logger.debug(f"Could not get directory structure: {e}")
            return "Directory structure unavailable"
    
    def _identify_key_files(self) -> List[str]:
        """Identify key files in the repository"""
        key_files = []
        common_files = [
            'README.md', 'package.json', 'requirements.txt', 'setup.py',
            'index.html', 'main.py', 'app.py', 'server.py', 'index.js',
            'main.js', 'app.js', 'config.json', '.gitignore', 'pom.xml',
            'build.gradle', 'Dockerfile', 'docker-compose.yml'
        ]
        
        for file_name in common_files:
            # Check root
            file_path = Path(self.repo_path) / file_name
            if file_path.exists():
                key_files.append(file_name)
            
            # Check common subdirectories
            for common_subdir in ['src', 'app', 'cmd', 'lib']:
                subdir_file_path = Path(self.repo_path) / common_subdir / file_name
                if subdir_file_path.exists():
                    relative_path = str(subdir_file_path.relative_to(self.repo_path))
                    if relative_path not in key_files:
                        key_files.append(relative_path)

        return key_files
    
    def _detect_languages(self) -> List[str]:
        """Detect programming languages used in the repository"""
        languages = set()
        extensions = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript', '.html': 'HTML',
            '.css': 'CSS', '.java': 'Java', '.cpp': 'C++', '.c': 'C', '.cs': 'C#',
            '.go': 'Go', '.rs': 'Rust', '.php': 'PHP', '.rb': 'Ruby', '.kt': 'Kotlin',
            '.swift': 'Swift', '.scala': 'Scala', '.md': 'Markdown', '.json': 'JSON',
            '.yaml': 'YAML', '.yml': 'YAML', '.sh': 'Shell'
        }
        
        file_count = 0
        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in root.split(os.sep):
                continue
                
            for file_name in files:
                if file_count > 1000:  # Limit for performance
                    return list(languages) if languages else ["Undetermined - too many files"]

                ext = os.path.splitext(file_name)[1].lower()
                if ext in extensions:
                    languages.add(extensions[ext])
                file_count += 1
        
        return list(languages) if languages else ["Undetermined"]
    
    def _get_dependencies(self) -> Dict[str, str]:
        """Get dependency information from common dependency files"""
        dependencies = {}
        
        dep_files = {
            'python': 'requirements.txt',
            'nodejs_package': 'package.json',
            'maven': 'pom.xml',
            'gradle': 'build.gradle',
        }

        for lang, file_name in dep_files.items():
            file_path = Path(self.repo_path) / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read(2048)  # Read snippet
                        
                        if lang == 'nodejs_package':
                            try:
                                if len(content) == 2048:
                                    # Re-read full file if snippet was truncated
                                    f.seek(0)
                                    content = f.read()
                                
                                pkg_data = json.loads(content)
                                deps = pkg_data.get('dependencies', {})
                                dev_deps = pkg_data.get('devDependencies', {})
                                dependencies[lang] = json.dumps({
                                    'dependencies': deps, 
                                    'devDependencies': dev_deps
                                }, indent=2)
                            except json.JSONDecodeError:
                                dependencies[lang] = "Could not parse package.json"
                        else:
                            dependencies[lang] = content.strip() + "\n..." if len(content) == 2048 else content.strip()
                            
                except Exception as e:
                    logger.warning(f"Could not read dependency file {file_name}: {e}")
                    dependencies[lang] = f"Error reading {file_name}"
            
            # Check for .kts variant for gradle
            elif lang == 'gradle':
                file_path_kts = Path(self.repo_path) / "build.gradle.kts"
                if file_path_kts.exists():
                    try:
                        with open(file_path_kts, 'r', encoding='utf-8') as f:
                            content = f.read(2048)
                            dependencies[lang] = content.strip() + "\n..." if len(content) == 2048 else content.strip()
                    except Exception as e:
                        logger.warning(f"Could not read dependency file build.gradle.kts: {e}")
                        dependencies[lang] = "Error reading build.gradle.kts"

        return dependencies
