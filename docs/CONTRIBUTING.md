# Contributing to Causal Sentinel

First off, thank you for considering contributing to Causal Sentinel! 🎉

## 🤝 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues. When you create a bug report, include as many details as possible:

**Template:**
```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., macOS 13.4]
- Python version: [e.g., 3.11.2]
- Browser: [e.g., Chrome 119]
- Version: [e.g., 2.0]

**Additional context**
Any other context about the problem.
```

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

- **Use a clear and descriptive title**
- **Provide a detailed description** of the suggested enhancement
- **Explain why this enhancement would be useful**
- **List some examples** of how it would be used

### Pull Requests

1. **Fork the repo** and create your branch from `main`
2. **Make your changes**
3. **Add tests** if applicable
4. **Update documentation** if needed
5. **Ensure the test suite passes**
6. **Submit your pull request**

## 🏗️ Development Setup

### Quick Setup

```bash
# Clone your fork
git clone https://github.com/your-username/causal-sentinel.git
cd causal-sentinel

# Run setup script
bash setup.sh  # macOS/Linux
setup.bat      # Windows

# Create a branch
git checkout -b feature/your-feature-name
```

### Running Tests

```bash
# Run dashboard in development mode
streamlit run dashboard.py --logger.level=debug

# Test with sample data
python -c "
import pandas as pd
# Generate test data
dates = pd.date_range('2024-11-01', '2024-11-30', freq='D')
df = pd.DataFrame({'date': dates, 'revenue': [50000]*30})
df.loc[14, 'revenue'] = 25000  # Inject anomaly
df.to_csv('test_metrics.csv', index=False)
"
```

## 📝 Style Guide

### Python Code Style

We follow PEP 8 with some modifications:

```python
# Use descriptive variable names
crash_date = detect_crashes(df_metrics)  # Good
cd = detect_crashes(df_metrics)          # Bad

# Add docstrings to functions
def detect_crashes(df, threshold=2.0, window=7):
    """
    Detects anomalies in time-series data using rolling Z-score.
    
    Args:
        df: DataFrame with 'date' and 'daily_revenue' columns
        threshold: Z-score threshold for anomaly detection (default: 2.0)
        window: Rolling window size in days (default: 7)
        
    Returns:
        DataFrame containing detected anomalies
    """
    pass

# Use type hints where helpful
from typing import Optional, Dict, List

def analyze_log(log_message: str) -> Dict[str, str]:
    """Analyzes a log message and returns risk assessment."""
    pass
```

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
feat: add multi-metric support
fix: correct Z-score calculation for small datasets
docs: update deployment guide
refactor: simplify anomaly detection logic
test: add unit tests for causal inference
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, missing semicolons, etc.)
- `refactor`: Code change that neither fixes a bug nor adds a feature
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

## 🎯 Priority Areas

We're especially interested in contributions in these areas:

### High Priority
- [ ] **Multi-metric support** (analyze revenue + latency simultaneously)
- [ ] **Alert system** (email/Slack notifications)
- [ ] **Real-time streaming** (Kafka/websocket integration)
- [ ] **Unit tests** (pytest coverage)

### Medium Priority
- [ ] **Additional visualizations** (better charts, insights)
- [ ] **More causal methods** (DML, IV, RDD)
- [ ] **Export functionality** (PDF reports, CSV exports)
- [ ] **User authentication** (for deployment)

### Nice to Have
- [ ] **Dark mode toggle** (currently always dark)
- [ ] **Mobile optimization**
- [ ] **Internationalization** (i18n)
- [ ] **Plugin system** (custom data sources)

## 🧪 Testing Guidelines

### Manual Testing Checklist

Before submitting a PR, verify:

- [ ] Upload CSV with valid data → Works
- [ ] Upload Excel with valid data → Works
- [ ] Upload empty file → Shows error
- [ ] Upload file with 1 row → Shows error
- [ ] Upload file with invalid dates → Reports errors gracefully
- [ ] Upload metrics with no crashes → Shows "healthy"
- [ ] Upload metrics with 1 crash → Detects correctly
- [ ] Upload metrics with multiple crashes → Detects all
- [ ] Adjust sensitivity slider → Updates detection
- [ ] Generate sample data → Downloads work

### Edge Cases to Test

```python
# Test with minimal data
df_tiny = pd.DataFrame({
    'date': ['2024-11-01', '2024-11-02'],
    'revenue': [50000, 25000]
})

# Test with constant revenue (no variance)
df_flat = pd.DataFrame({
    'date': pd.date_range('2024-11-01', periods=30),
    'revenue': [50000] * 30
})

# Test with all negative revenue
df_negative = pd.DataFrame({
    'date': pd.date_range('2024-11-01', periods=30),
    'revenue': [-1000] * 30
})
```

## 📚 Documentation

If you're adding a new feature:

1. **Update README.md** with usage examples
2. **Add docstrings** to new functions
3. **Update DEPLOYMENT.md** if relevant
4. **Consider adding a tutorial** in the docs/ folder

## 🐛 Bug Triage Process

1. **Reproduce the bug** locally
2. **Identify the root cause** (which function/line)
3. **Write a test** that demonstrates the bug
4. **Fix the bug** and verify test passes
5. **Submit PR** with test + fix

## 🎨 Design Philosophy

When contributing, keep these principles in mind:

### 1. Simplicity First
- Prefer readable code over clever code
- Avoid premature optimization
- Keep functions focused on one task

### 2. Robustness
- Validate inputs
- Handle errors gracefully
- Provide helpful error messages

### 3. User Experience
- Minimize clicks and configuration
- Show progress for long operations
- Make errors actionable

### 4. Performance
- Cache expensive operations
- Use vectorized operations (pandas/numpy)
- Sample large datasets for visualization

## 🏆 Recognition

Contributors will be:
- Listed in README.md
- Mentioned in release notes
- Credited in documentation

## 📞 Questions?

- Open a [Discussion](https://github.com/yourusername/causal-sentinel/discussions)
- Join our [Discord](#) (if available)
- Email: your.email@example.com

## 📜 Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all.

### Our Standards

**Positive behavior:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

**Unacceptable behavior:**
- Trolling, insulting/derogatory comments, personal attacks
- Public or private harassment
- Publishing others' private information
- Other conduct which could reasonably be considered inappropriate

## 🙏 Thank You!

Your contributions make Causal Sentinel better for everyone. We appreciate your time and effort! 🎉

---

**Happy Contributing! 🚀**