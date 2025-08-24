"""
In single player mode, the agent runs always against its previous version.
"""

import copy
import traceback

from codeclash.agents import get_agent
from codeclash.agents.abstract import Player
from codeclash.games import get_game
from codeclash.games.abstract import CodeGame
from codeclash.tournaments.abstract import AbstractTournament
from codeclash.tournaments.utils.git_utils import filter_git_diff
from codeclash.utils.environment import assert_zero_exit_code, create_file_on_container
from codeclash.utils.log import get_logger


class SinglePlayerTraining(AbstractTournament):
    def __init__(self, config: dict, cleanup: bool = False):
        super().__init__(config, name="SinglePlayerTraining")
        self.cleanup_on_end = cleanup
        self.game: CodeGame = get_game(
            self.config,
            tournament_id=self.tournament_id,
            local_output_dir=self.local_output_dir,
        )
        # fixme: hack
        self.game.rounds = self.config["game"]["rounds"]
        self.agent: Player = get_agent(
            self.config["player"], self.config["prompts"], self.game
        )
        mirror_agent_config = copy.deepcopy(self.config["player"])
        mirror_agent_config["name"] = "mirror"
        self.mirror_agent: Player = get_agent(
            mirror_agent_config, self.config["prompts"], self.game
        )
        self.logger = get_logger(self.game.name)

    @property
    def rounds(self) -> int:
        return self.config["game"]["rounds"]

    def run(self):
        """Main execution function that runs all rounds."""
        try:
            for round_num in range(1, self.rounds + 1):
                self.run_training_round(round_num)
        finally:
            self.cleanup()

    def run_training_round(self, round_num: int) -> None:
        """Execute a single training round."""
        # Run the game round and get results
        result = self.game.run_round([self.agent, self.mirror_agent])
        log_output = result["log_output"]
        result_output = result["result_output"]
        winner = result["winner"]

        # Handle bookkeeping that was previously in the game
        self.game.scoreboard.append((round_num, winner))
        self.logger.info(f"Round {round_num} winner: {winner}")

        # Write log to file
        round_log_path = self.game.log_local / f"round_{round_num}.log"
        round_log_path.write_text(log_output)

        # Copy log to main agent environment only
        self._copy_game_log_to_agent([self.agent], round_num, log_output)

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

    def _copy_game_log_to_agent(
        self, agents: list, round_num: int, log_output: str
    ) -> None:
        """Copy round logs to agent environments and local directory."""
        for agent in agents:
            try:
                create_file_on_container(
                    container=agent.environment,
                    content=log_output,
                    dest_path=f"logs/round_{round_num}.log",
                )
            except Exception:
                self.logger.error(
                    f"Error creating round log in {agent.name}'s container: {traceback.format_exc()}"
                )
            else:
                self.logger.info(f"Created round log in {agent.name}'s container.")

        self.logger.info("Round completed.")

    def cleanup(self):
        """Clean up game resources."""
        self.game.end(self.cleanup_on_end)
