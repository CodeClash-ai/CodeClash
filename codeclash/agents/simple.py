from pathlib import Path

import litellm

from codeclash.agents.abstract import Agent
from codeclash.agents.utils import resolve_api_key

GAME_TO_FILE = {
    "Battlesnake": "main.py",
    "RoboCode": "robots/custom/MyTank.java",
    "RobotRumble": "robot.py",
}


class SimpleAgent(Agent):
    def __init__(self, config: dict, game):
        super().__init__(config, game)
        self.model = config["model"]
        self.api_key = config.get("api_key", resolve_api_key(self.model))
        self.temperature = config.get("temperature", 0)
        self.top_p = config.get("top_p", 1.0)
        self.game = game

        self.messages = []

    def step(self, round_log: Path):
        with open(round_log, "r") as f:
            log_content = f.read()
        self.messages.append(
            {
                "role": "user",
                "content": f"""Here is a recap of the last round:

{log_content}

Here is the existing implementation of your game bot:

{(self.codebase / GAME_TO_FILE[self.game.name]).read_text()}

You can now decide what to do next. You can either:
1. Keep the existing implementation and do nothing.
2. Write a new implementation of your game bot.

If you do (1), make sure to include "DO_NOTHING" somewhere in your response.

If you do (2), format your new implementation as follows:

The implementation of the game has been updated to <explanation>.

Here is the new implementation:
<implementation>
[Write the new implementation of your code here]
</implementation>
""",
            }
        )

        response: litellm.types.utils.ModelResponse = litellm.completion(
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
            max_tokens=1000,
            api_key=self.api_key,
            n=1,
        )

        content = response.choices[0].message.content.strip()
        if "DO_NOTHING" in content:
            self.messages.append(
                {"role": "assistant", "content": "The codebase was not edited."}
            )
            return

        explanation = content.split("<explanation>")[0]
        implementation = (
            content.split("<implementation>")[-1].split("</implementation>")[0].strip()
        )

        # If the agent decided to edit the codebase, we need to apply the changes
        with open(self.codebase / GAME_TO_FILE[self.game.name], "w") as f:
            f.write(implementation)
        self.messages.append(
            {
                "role": "assistant",
                "content": explanation,
            }
        )
