import matplotlib.font_manager as fm

from codeclash import REPO_DIR

MODEL_TO_DISPLAY_NAME = {
    "anthropic/claude-sonnet-4-20250514": "Claude Sonnet 4",
    "anthropic/claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "x-ai/grok-code-fast-1": "Grok Code Fast",
    "google/gemini-2.5-pro": "Gemini 2.5 Pro",
    "openai/gpt-5": "GPT-5",
    "openai/gpt-5-mini": "GPT-5 Mini",
    "openai/o3": "o3",
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "grok-code-fast-1": "Grok Code Fast",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gpt-5": "GPT-5",
    "gpt-5-mini": "GPT-5 Mini",
    "qwen3-coder-plus-2025-09-23": "Qwen3 Coder",
    "o3": "o3",
}

MODEL_TO_COLOR = {
    "anthropic/claude-sonnet-4-20250514": "#FFD449",
    "anthropic/claude-sonnet-4-5-20250929": "#F75C03",
    "x-ai/grok-code-fast-1": "#031926",
    "google/gemini-2.5-pro": "#d62728",
    "openai/gpt-5": "#04A777",
    "openai/gpt-5-mini": "#69DDFF",
    "openai/o3": "#5E7CE2",
    "claude-sonnet-4-20250514": "#7D3B15",
    "claude-sonnet-4-5-20250929": "#F75C03",
    "grok-code-fast-1": "#031926",
    "gemini-2.5-pro": "#d62728",
    "gpt-5": "#04A777",
    "gpt-5-mini": "#69DDFF",
    "qwen3-coder-plus-2025-09-23": "#852aec",
    "o3": "#5E7CE2",
}

ASSETS_DIR = REPO_DIR / "assets"
FONT_REG = fm.FontProperties(fname=ASSETS_DIR / "texgyrepagella-regular.otf")
FONT_BOLD = fm.FontProperties(fname=ASSETS_DIR / "texgyrepagella-bold.otf")
