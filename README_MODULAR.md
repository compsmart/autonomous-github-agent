# Autonomous AI Bug Fixer Agent - Modular Version

A fully autonomous AI agent that automatically fixes bugs in GitHub repositories using Google Gemini AI.

## Overview

This modular version breaks down the original monolithic script into manageable, focused components:

### 🏗️ **Modular Architecture**

```
src/
├── core/                    # Core business logic
│   ├── agent.py            # Main agent controller
│   ├── bug_fixer_service.py # Bug fixing orchestration
│   └── config.py           # Configuration management
├── clients/                 # External API clients
│   ├── github_client.py    # GitHub API operations
│   └── ai_client.py        # Google Gemini AI client
├── models/                  # Data models
│   └── bug_models.py       # Issue, Fix, and Analysis models
└── utils/                   # Utility modules
    ├── git_operations.py   # Git repository operations
    └── codebase_analyzer.py # Repository analysis
```

## ✨ **Key Improvements**

### **1. Separation of Concerns**
- **GitHub API operations** isolated in `GitHubClient`
- **AI interactions** managed by `AIClient`
- **Git operations** handled by `GitOperations`
- **Business logic** orchestrated by `BugFixerService`

### **2. Better Error Handling**
- Granular error handling in each module
- Proper cleanup and rollback mechanisms
- Detailed logging at appropriate levels

### **3. Enhanced Testability**
- Each component can be unit tested independently
- Mock-friendly interfaces for external dependencies
- Clear data models with validation

### **4. Improved Maintainability**
- Single responsibility principle
- Clear module boundaries
- Type hints throughout
- Comprehensive documentation

## 🚀 **Usage**

### **Basic Usage**
```bash
python main.py
```

### **Advanced Options**
```bash
# Dry run to see what issues would be processed
python main.py --dry-run

# Limit to 5 issues
python main.py --limit 5

# Override repository
python main.py --repo octocat/Hello-World

# Custom config file
python main.py --config custom.env
```

## ⚙️ **Configuration**

Create a `.env` file with the required configuration:

```env
# Required
GITHUB_TOKEN=your_github_token_here
GEMINI_API_KEY=your_gemini_api_key_here

# Repository (choose one format)
GITHUB_REPO=owner/repo-name
# OR
REPO_OWNER=owner
REPO_NAME=repo-name

# Optional
SYSTEM_INSTRUCTIONS=custom_ai_instructions
```

## 🔧 **Component Details**

### **Core Components**

#### `AutonomousBugFixer` (agent.py)
- Main orchestrator
- Handles initialization and coordination
- Manages the overall fix workflow

#### `BugFixerService` (bug_fixer_service.py)
- Core business logic for bug fixing
- Orchestrates AI analysis, code changes, and PR creation
- Handles single and multiple bug fixes

#### `Config` & `ConfigLoader` (config.py)
- Environment variable management
- Configuration validation
- Default system instructions

### **Client Components**

#### `GitHubClient` (github_client.py)
- GitHub API interactions
- Issue fetching with PR conflict detection
- Pull request creation

#### `AIClient` (ai_client.py)
- Google Gemini AI integration
- Bug analysis and fix generation
- Response parsing and validation

### **Utility Components**

#### `GitOperations` (git_operations.py)
- Repository cloning and setup
- Branch management
- File modifications and commits
- Push operations and cleanup

#### `CodebaseAnalyzer` (codebase_analyzer.py)
- Repository structure analysis
- Language detection
- Dependency identification
- Key file discovery

### **Data Models**

#### `BugIssue`
- Represents a GitHub issue
- Contains all relevant issue metadata

#### `FixResult`
- Represents the outcome of a fix attempt
- Tracks success/failure and modified files

#### `FixAnalysis`
- AI-generated fix analysis
- Includes validation methods

#### `CodebaseInfo`
- Repository analysis results
- Structure, languages, and dependencies

## 🔍 **Benefits of Modular Design**

### **For Development**
- **Easier debugging**: Issues can be isolated to specific modules
- **Faster iteration**: Change one component without affecting others
- **Better testing**: Unit test individual components
- **Code reuse**: Components can be reused in other projects

### **For Maintenance**
- **Clear ownership**: Each module has a specific responsibility
- **Easier onboarding**: New developers can understand one module at a time
- **Simplified updates**: Update AI models, GitHub API, or Git operations independently
- **Better documentation**: Each module can be documented separately

### **For Scaling**
- **Parallel development**: Multiple developers can work on different modules
- **Performance optimization**: Optimize specific bottlenecks
- **Feature additions**: Add new capabilities without touching existing code
- **Alternative implementations**: Swap out components (e.g., different AI providers)

## 🐛 **Error Handling**

Each module includes comprehensive error handling:

- **Network errors**: Retry logic and graceful degradation
- **API errors**: Proper error messages and fallback behavior
- **Git errors**: Branch cleanup and state recovery
- **AI errors**: Fallback models and validation

## 📊 **Logging**

Structured logging throughout:
- **INFO**: High-level operations and progress
- **DEBUG**: Detailed operation traces
- **WARNING**: Non-fatal issues
- **ERROR**: Failures with context

## 🧪 **Testing Strategy**

The modular design enables comprehensive testing:

```python
# Example unit test structure
tests/
├── test_github_client.py
├── test_ai_client.py
├── test_git_operations.py
├── test_bug_fixer_service.py
└── test_integration.py
```

## 🔄 **Migration from Original**

The modular version maintains the same external interface:
- Same command-line arguments
- Same configuration format
- Same logging output
- Same functionality

**Key differences:**
- ✅ Better organized code
- ✅ Easier to extend and modify
- ✅ More robust error handling
- ✅ Better separation of concerns
- ✅ Enhanced maintainability

## 📈 **Future Enhancements**

The modular design makes it easy to add:

- **Multiple AI providers** (OpenAI, Claude, etc.)
- **Different Git hosting** (GitLab, Bitbucket)
- **Enhanced analysis** (static analysis, test running)
- **Monitoring and metrics**
- **Web interface**
- **Scheduled execution**

## 🏃‍♂️ **Getting Started**

1. **Clone the repository**
2. **Install dependencies**: `pip install -r requirements.txt`
3. **Create `.env` file** with your tokens
4. **Run**: `python main.py --dry-run` to test
5. **Execute**: `python main.py` to fix bugs

The modular design ensures you can start simple and scale up as needed!
