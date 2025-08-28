from pathlib import Path

from dotenv import load_dotenv
from jinja2 import Template
from pydantic import BaseModel

load_dotenv()


class GameContext(BaseModel):
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

    def _render_prompt_templates(self) -> dict:
        context = self.dict()
        return {key: Template(template_str).render(**context) for key, template_str in self.prompts.items()}

    def to_template_vars(self) -> dict[str, str]:
        """Convert the GameContext to a dictionary for rendering prompts in the agent"""
        out = self.dict() | self._render_prompt_templates()
        out.pop("prompts")
        return out
