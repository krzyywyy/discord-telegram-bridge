# Contributing

Thanks for considering contributing!

## Getting started

1. Fork the repository and create a new branch.
2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # or .\.venv\\Scripts\\activate on Windows
pip install -r requirements.txt
```

3. Run basic checks:

```bash
python -m py_compile main.py bridge_config.py message_store.py
```

## Pull request guidelines

- Keep PRs focused and small.
- Update `README.md` when behavior changes.
- Do not commit secrets (`.env`, tokens, private IDs). If you accidentally do, rotate the tokens immediately.

