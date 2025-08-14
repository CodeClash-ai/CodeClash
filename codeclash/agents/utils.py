import os
from dataclasses import asdict, dataclass
from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template

load_dotenv()


def resolve_api_key(model: str) -> str:
    if "claude" in model:
        return os.getenv("ANTHROPIC_API_KEY")
    if "gpt" in model:
        return os.getenv("OPENAI_API_KEY")


@dataclass
class GameContext:
    """
    A class that gives agent access to a partial view of the game state.

    NOTE: Instead of passing `game` directly as a reference to the agent,
    we create this interface instead to make the communication of game state
    more explicit and controlled. We go with this loose coupling to avoid
    making the agent too dependent on the entire game object.
    """

    id: str
    log_env: Path
    log_local: Path
    name: str
    player_id: str
    prompts: dict
    round: int
    rounds: int
    working_dir: str

    def render_and_set_prompts(self):
        """Render and set prompts using the current game context."""
        context = asdict(self)
        del context["prompts"]
        for key, template_str in self.prompts.items():
            rendered = Template(template_str).render(**context)
            setattr(self, key, rendered)

    def to_dict(self):
        """Convert the GameContext to a dictionary, including dynamically added attributes."""
        result = asdict(self)
        declared = set(self.__dataclass_fields__)
        for attr in dir(self):
            if (
                not attr.startswith("_")
                and attr not in declared
                and not callable(getattr(self, attr))
            ):
                result[attr] = getattr(self, attr)
        del result["prompts"]
        return result
