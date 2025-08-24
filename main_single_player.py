"""
In single player mode, the agent runs always against its previous version.
"""

import argparse
import copy

import yaml

from codeclash.agents import get_agent
from codeclash.agents.abstract import Player
from codeclash.games import get_game
from codeclash.games.abstract import CodeGame
from codeclash.utils.environment import assert_zero_exit_code, create_file_on_container
from codeclash.utils.log import get_logger


def filter_git_diff(text: str) -> str:
    """Return a git diff with any file sections mentioning binary content removed."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    block: list[str] = []
    in_block = False
    prelude_copied = False

    def is_binary_block(bl: list[str]) -> bool:
        for ln in bl:
            s = ln.strip()
            if ln.startswith("Binary files "):
                return True
            if s == "GIT binary patch":
                return True
        return False

    for ln in lines:
        if ln.startswith("diff --git "):
            if in_block:
                if not is_binary_block(block):
                    out.extend(block)
                block = []
            else:
                if not prelude_copied:
                    prelude_copied = True
            in_block = True
        if in_block:
            block.append(ln)
        else:
            out.append(ln)

    if in_block and block:
        if not is_binary_block(block):
            out.extend(block)

    return "".join(out)


class SinglePlayerTraining:
    def __init__(self, config: dict, cleanup: bool = False):
        self.config = config
        self.cleanup_on_end = cleanup
        self.game: CodeGame = get_game(self.config)
        self.agent: Player = get_agent(
            self.config["player"], self.config["prompts"], self.game
        )
        mirror_agent_config = copy.deepcopy(self.config["player"])
        mirror_agent_config["name"] = "mirror"
        self.mirror_agent: Player = get_agent(
            mirror_agent_config, self.config["prompts"], self.game
        )
        self.logger = get_logger(self.game.name)

    def run(self):
        """Main execution function that runs all rounds."""
        try:
            for round_num in range(1, self.game.rounds + 1):
                self.run_round(round_num)
        finally:
            self.cleanup()

    def run_round(self, round_num: int):
        """Execute a single training round."""
        self.game.run_round([self.agent, self.mirror_agent])
        self.run_main_agent(round_num)
        self.run_mirror_agent(round_num)

    def run_main_agent(self, round_num: int):
        """Run the main agent for the current round."""
        self.agent.pre_run_hook(new_round=round_num)
        self.agent.run()
        self.agent.post_run_hook(round=round_num)

    def run_mirror_agent(self, round_num: int):
        """Update mirror agent's codebase with the main agent's changes."""
        if round_num == 1:
            self.logger.info("Skipping updating mirror agent for round 1")
            return

        # Set mirror agent's codebase to the main agent's codebase of the previous round
        full_diff = self.agent.get_metadata()["diff"][round_num - 1]

        full_diff = filter_git_diff(full_diff)

        if full_diff.strip():
            self.logger.debug(
                assert_zero_exit_code(
                    self.mirror_agent.environment.execute(
                        "git reset --hard && git clean -fd"
                    )
                )
            )

            create_file_on_container(
                container=self.mirror_agent.environment,  # type: ignore
                content=full_diff,
                dest_path="tmp_patch.txt",
            )

            self.logger.info("Applying patch to mirror agent's codebase")
            self.logger.debug(f"Full diff: {full_diff}")

            commands = ["git status", "git apply tmp_patch.txt", "rm -f tmp_patch.txt"]
            for cmd in commands:
                self.logger.debug(f"Executing command: {cmd}")
                out = assert_zero_exit_code(
                    self.mirror_agent.environment.execute(cmd), logger=self.logger
                )
                self.logger.debug(out)
        else:
            self.logger.info("No diff found for mirror agent, skipping update")

    def cleanup(self):
        """Clean up game resources."""
        self.game.end(self.cleanup_on_end)


def main(config_path: str, cleanup: bool = False):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    training = SinglePlayerTraining(config, cleanup)
    training.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CodeClash")
    parser.add_argument(
        "config_path",
        type=str,
        default="configs/battlesnake.yaml",
        help="Path to the config file.",
    )
    parser.add_argument(
        "-c",
        "--cleanup",
        action="store_true",
        help="If set, do not clean up the game environment after running.",
    )
    args = parser.parse_args()
    main(**vars(args))
