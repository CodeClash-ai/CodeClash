# CodeClash Documentation

This directory contains the source files for the CodeClash documentation, built with MkDocs Material.

## Local Development

### Prerequisites

Install documentation dependencies:

```bash
pip install mkdocs-material mkdocstrings[python] mkdocs-glightbox mkdocs-include-markdown-plugin
```

### Serve Locally

Run the development server:

```bash
mkdocs serve
```

Then open http://127.0.0.1:8000 in your browser. The site will automatically reload when you make changes.

### Build

Build the static site:

```bash
mkdocs build
```

The built site will be in the `site/` directory.

## Structure

```
docs/
├── index.md              # Homepage
├── quickstart.md         # Getting started guide
├── usage/               # Usage guides
│   ├── tournaments.md
│   └── viewer.md
├── reference/           # API documentation
│   ├── index.md
│   ├── arenas/         # Game implementations
│   ├── player/         # Agent implementations
│   └── tournament/     # Tournament types
└── assets/             # Static assets
    └── custom.css
```

## Deployment

Documentation is automatically deployed to GitHub Pages via GitHub Actions when changes are pushed to the `main` branch.

The deployed site is available at: https://docs.codeclash.io

## Writing Documentation

### Markdown

Use standard Markdown with Material for MkDocs extensions:

- Admonitions: `!!! note`, `!!! warning`, etc.
- Code blocks with syntax highlighting
- Tables
- Footnotes

### API Documentation

API documentation is auto-generated from Python docstrings using mkdocstrings:

```markdown
::: codeclash.games.game.CodeGame
    options:
      show_root_heading: true
      heading_level: 2
```

### Links

- Internal links: `[Text](page.md)`
- Anchors: `[Text](page.md#section)`
- External: `[Text](https://example.com)`

## Contributing

1. Edit markdown files in `docs/`
2. Test locally with `mkdocs serve`
3. Commit and push to `main`
4. GitHub Actions will automatically deploy
