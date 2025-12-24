# CodeClash Documentation

This directory contains the source files for the CodeClash documentation, built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Local Development

### Setup

Install documentation dependencies with uv:

```bash
uv sync --extra docs
```

### Preview Locally

Run the development server with hot reload:

```bash
uv run mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser. The site automatically reloads when you make changes.

### Build Static Site

Build the static site for production:

```bash
uv run mkdocs build
```

The built site will be in the `site/` directory.

## Structure

```
docs/
├── index.md                  # Homepage
├── quickstart.md             # Getting started guide
├── usage/                    # Usage guides
│   ├── tournaments.md        # Running tournaments
│   └── codebase-tour.md      # Contributor orientation
├── reference/                # API documentation
│   ├── index.md
│   ├── arenas/               # Game implementations
│   ├── player/               # Agent implementations
│   └── tournament/           # Tournament types
├── assets/                   # Static assets
│   └── custom.css
└── README.md                 # This file
```

## Writing Documentation

### Markdown Extensions

We use Material for MkDocs extensions:

**Admonitions:**
```markdown
!!! note "Title"
    Note content here.

!!! warning
    Warning content here.

!!! tip
    Tip content here.
```

**Tabbed content:**
```markdown
=== "Tab 1"
    Content for tab 1

=== "Tab 2"
    Content for tab 2
```

**Code blocks:**
```markdown
```python
def hello():
    print("Hello, World!")
```
```

### API Documentation

API docs are auto-generated from Python docstrings using mkdocstrings:

```markdown
::: codeclash.arenas.arena.CodeArena
    options:
      show_root_heading: true
      heading_level: 2
```

Use Google-style docstrings:

```python
def my_function(arg1: str, arg2: int) -> bool:
    """Short description.

    Longer description if needed.

    Args:
        arg1: Description of arg1.
        arg2: Description of arg2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When something is wrong.
    """
```

### Internal Links

```markdown
[Link text](page.md)              # Same directory
[Link text](../page.md)           # Parent directory
[Link text](page.md#section)      # Specific section
```

### Including Snippets

Use the include directive for shared content:

```markdown
--8<-- "docs/_footer.md"
```

## Deployment

Documentation is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the `main` branch.

**Live site:** https://docs.codeclash.ai

## Quick Reference

| Command | Description |
|---------|-------------|
| `uv sync --extra docs` | Install doc dependencies |
| `uv run mkdocs serve` | Preview with hot reload |
| `uv run mkdocs build` | Build static site |
| `uv run mkdocs gh-deploy` | Deploy to GitHub Pages |

## Contributing

1. Edit markdown files in `docs/`
2. Test locally with `uv run mkdocs serve`
3. Ensure links work and formatting looks correct
4. Commit and push to `main`
5. GitHub Actions will automatically deploy

For code contributions, see the [Contributing Guide](../CONTRIBUTING.md).
