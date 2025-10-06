import matplotlib.font_manager as fm

from codeclash import REPO_DIR

MODEL_TO_DISPLAY_NAME = {
    "claude-sonnet-4-20250514": "Claude Sonnet 4",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "grok-code-fast-1": "Grok Code Fast",
    "gemini-2.5-pro": "Gemini 2.5 Pro",
    "gpt-5": "GPT-5",
    "gpt-5-mini": "GPT-5 Mini",
    "qwen3-coder-plus-2025-09-23": "Qwen3 Coder",
    "o3": "o3",
}

FONT_REG = fm.FontProperties(fname=REPO_DIR / "assets/texgyrepagella-regular.otf")
FONT_BOLD = fm.FontProperties(fname=REPO_DIR / "assets/texgyrepagella-bold.otf")
