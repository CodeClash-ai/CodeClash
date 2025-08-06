import os

from dotenv import load_dotenv

load_dotenv()


def resolve_api_key(model: str) -> str:
    if "claude" in model:
        return os.getenv("ANTHROPIC_API_KEY")
    if "gpt" in model:
        return os.getenv("OPENAI_API_KEY")
