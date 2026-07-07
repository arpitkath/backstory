# Contributing to Backstory

Thanks for your interest in Backstory! We welcome contributions from everyone, whether you're fixing a bug, adding a feature, or improving documentation.

## How to Report Issues

Found a bug or have a feature request? Open an issue on [GitHub](https://github.com/arpitkath/backstory/issues). Please include:

- A clear, descriptive title.
- Steps to reproduce the problem (if a bug).
- Expected vs. actual behavior.
- Your environment (OS, Python version, Backstory version).

## How to Submit Pull Requests

1. **Fork** the repository and create your branch from `master`.
2. **Make your changes** — keep them small and scoped.
3. **Run the tests** to make sure nothing is broken (see below).
4. **Commit** with a clear message describing what and why.
5. **Push** to your fork and open a pull request.

We'll review PRs as soon as possible. Please be responsive to feedback — we may suggest changes before merging.

## Development Setup

```bash
# Clone the repository
git clone https://github.com/arpitkath/backstory.git
cd backstory

# Run the CLI directly from source (no install needed)
python -m backstory <command>

# Run tests
PYTHONPATH=src python -m pytest
```

Make sure all tests pass before submitting your PR.

## Code Style Guidelines

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code.
- Keep functions and classes focused — prefer small, scoped changes.
- Write tests for new functionality and update existing tests when behavior changes.
- Use type hints where practical.
- Treat the codebase as the source of truth — update docs when you change behavior.

## Documentation

If you're changing a command or a feature, update the relevant docs in the same PR. For a deeper understanding of the architecture, read the [engineering walkthrough](docs/engineering-walkthrough.md).

## Questions?

Feel free to open a discussion or issue — we're happy to help.

<!-- backstory test commit -->
