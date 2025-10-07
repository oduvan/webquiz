---
name: Bug Report
about: Report a bug to help us improve WebQuiz
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
<!-- Provide a clear and concise description of the bug -->


## Environment
**Python Version:**
<!-- e.g., 3.9, 3.10, 3.11, 3.12 -->

**Operating System:**
<!-- e.g., Ubuntu 22.04, macOS 13, Windows 11 -->

**Installation Method:**
<!-- Check one: -->
- [ ] Poetry
- [ ] pip
- [ ] Binary distribution (PyInstaller)

**WebQuiz Version:**
<!-- Run: webquiz --version OR check pyproject.toml -->


## Steps to Reproduce
<!-- Provide detailed steps to reproduce the issue -->
1. 
2. 
3. 

## Expected Behavior
<!-- Describe what you expected to happen -->


## Actual Behavior
<!-- Describe what actually happened -->


## Error Messages / Logs
<!-- Include any error messages, stack traces, or relevant log output -->
```
Paste error messages or logs here
```

## Affected Components
<!-- Check all that apply to help Copilot focus on the right areas -->
- [ ] Server (webquiz/server.py)
- [ ] CLI (webquiz/cli.py)
- [ ] Admin Interface (templates/admin.html)
- [ ] Quiz Interface (templates/index.html)
- [ ] File Manager (templates/files.html)
- [ ] Live Statistics (templates/live_stats.html)
- [ ] API Endpoints
- [ ] Configuration (YAML files)
- [ ] Database/CSV Storage
- [ ] WebSocket Connections
- [ ] Authentication
- [ ] Testing Infrastructure
- [ ] Binary Build (PyInstaller)

## Related Files
<!-- List specific files related to this issue -->
- 
- 

## Configuration
<!-- If relevant, include your configuration settings (remove sensitive data like master keys) -->
```yaml
Paste relevant config here
```

## Screenshots
<!-- If applicable, add screenshots to help explain the problem -->


## Additional Context
<!-- Add any other context about the problem here -->


## Possible Solution
<!-- Optional: If you have ideas on how to fix this, describe them here -->


## Testing Information
<!-- Help Copilot understand testing requirements -->
**Existing Tests Affected:**
<!-- List any existing tests that fail due to this bug -->
- 

**New Tests Needed:**
<!-- Describe what tests should be added to prevent regression -->
- 

**Test Command:**
<!-- How to run relevant tests -->
```bash
source venv/bin/activate && python -m pytest tests/test_*.py -v
```
