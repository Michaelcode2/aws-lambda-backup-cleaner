# Contributing to AWS Lambda Backup Cleaner

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to this project.

## Development Setup

### Prerequisites

- Python 3.11+
- AWS CLI configured
- AWS SAM CLI installed
- Git

### Local Development

1. **Clone the repository**:
   ```bash
   git clone https://github.com/YOUR_ORG/aws-lambda-backup-cleaner.git
   cd aws-lambda-backup-cleaner
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-cov  # For testing
   ```

4. **Install SAM CLI**:
   ```bash
   # macOS
   brew install aws-sam-cli
   
   # Linux
   pip install aws-sam-cli
   ```

## Testing

### Run Unit Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Test Lambda Locally

```bash
# Test with example event
sam local invoke BackupCleanerFunction \
  -e example-event.json \
  --parameter-overrides \
    BucketName=test-bucket \
    RetentionConfigPath='{"retention_policies":[{"folder":"test/","days_to_keep":30,"min_backups_to_keep":5}]}'
```

### Validate SAM Template

```bash
sam validate --lint
```

## Code Style

### Python

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Include docstrings for all functions and classes
- Maximum line length: 100 characters

```python
def example_function(param: str) -> dict:
    """
    Brief description of the function.
    
    Args:
        param: Description of parameter
        
    Returns:
        Description of return value
    """
    pass
```

### Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(lambda): add support for custom S3 storage classes

fix(retention): correct calculation of backup age

docs(readme): update deployment instructions
```

## Pull Request Process

1. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**:
   - Write clean, well-documented code
   - Add or update tests as needed
   - Update documentation if necessary

3. **Test your changes**:
   ```bash
   # Run tests
   python -m pytest tests/ -v
   
   # Validate SAM template
   sam validate --lint
   
   # Test locally
   sam local invoke BackupCleanerFunction -e example-event.json
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: description of your feature"
   ```

5. **Push to GitHub**:
   ```bash
   git push origin feature/your-feature-name
   ```

6. **Create a Pull Request**:
   - Go to GitHub and create a PR from your branch to `develop`
   - Fill in the PR template with details about your changes
   - Link any related issues
   - Wait for review and CI checks to pass

7. **Address review comments**:
   - Make requested changes
   - Push additional commits to your branch
   - Request re-review when ready

8. **Merge**:
   - Once approved, squash and merge your PR
   - Delete your feature branch

## Branch Strategy

- `main`: Production-ready code, deploys to prod
- `develop`: Integration branch, deploys to dev
- `feature/*`: Feature branches (branch from `develop`)
- `bugfix/*`: Bug fix branches (branch from `develop` or `main`)
- `hotfix/*`: Emergency fixes (branch from `main`)

## Release Process

1. Ensure `develop` is stable and tested
2. Create a release PR from `develop` to `main`
3. Update version numbers and CHANGELOG
4. Get approval from maintainers
5. Merge to `main` (triggers production deployment)
6. Tag the release: `git tag -a v1.0.0 -m "Release version 1.0.0"`
7. Push tags: `git push origin v1.0.0`

## Testing Checklist

Before submitting a PR, ensure:

- [ ] All unit tests pass
- [ ] New features have corresponding tests
- [ ] Code follows PEP 8 style guidelines
- [ ] Docstrings are added for new functions/classes
- [ ] SAM template validates successfully
- [ ] Lambda function tested locally with SAM
- [ ] Documentation updated (README, SETUP, etc.)
- [ ] No sensitive information in code or commits
- [ ] CHANGELOG updated (if applicable)

## Feature Requests and Bug Reports

### Bug Reports

When reporting bugs, please include:

1. **Description**: Clear description of the bug
2. **Steps to reproduce**: Detailed steps to reproduce the issue
3. **Expected behavior**: What you expected to happen
4. **Actual behavior**: What actually happened
5. **Environment**: AWS region, Python version, SAM CLI version
6. **Logs**: Relevant CloudWatch logs or error messages
7. **Configuration**: Retention policy config (sanitized)

### Feature Requests

When requesting features, please include:

1. **Use case**: Why you need this feature
2. **Proposed solution**: How you think it should work
3. **Alternatives**: Other solutions you've considered
4. **Impact**: Who would benefit from this feature

## Code Review Guidelines

### For Reviewers

- Be respectful and constructive
- Focus on code quality, not personal preferences
- Suggest improvements with examples
- Approve when code meets standards

### For Contributors

- Respond to feedback promptly
- Ask questions if feedback is unclear
- Don't take criticism personally
- Thank reviewers for their time

## AWS Resources

When testing, use separate AWS resources:

- **Dev account**: For development and testing
- **Staging account**: For pre-production validation
- **Production account**: For production deployments

Never test destructive operations on production resources.

## Security

### Reporting Security Issues

**Do not** open public issues for security vulnerabilities.

Instead, email security concerns to: [your-security-email@example.com]

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Best Practices

- Never commit AWS credentials
- Use IAM roles, not access keys
- Follow principle of least privilege
- Encrypt sensitive data
- Keep dependencies updated
- Review CloudFormation template changes carefully

## Documentation

### When to Update Documentation

Update documentation when you:
- Add new features
- Change configuration options
- Modify deployment process
- Fix bugs that were unclear in docs
- Add new dependencies

### Documentation Locations

- `README.md`: Project overview and quick start
- `SETUP.md`: Detailed setup instructions
- `CONTRIBUTING.md`: This file
- Code comments: Inline explanations
- Docstrings: Function/class documentation

## Questions?

If you have questions about contributing:

1. Check existing documentation
2. Search closed issues and PRs
3. Ask in a new issue with the `question` label
4. Reach out to maintainers

## License

By contributing, you agree that your contributions will be licensed under the same license as the project.

## Thank You!

Your contributions make this project better for everyone. Thank you for taking the time to contribute!

