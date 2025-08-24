"""
In single player mode, the agent runs always against its previous version.
"""

import copy

from codeclash.agents import get_agent
from codeclash.agents.abstract import Player
from codeclash.games import get_game
from codeclash.games.abstract import CodeGame
from codeclash.tournaments.abstract import AbstractTournament
from codeclash.tournaments.utils.git_utils import filter_git_diff
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
            self.evaluate()
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
        self._copy_game_log_to_agent(self.agent, round_num, log_output)

        self.run_main_agent(round_num)
        mirror_agent_state = round_num - 1 if round_num > 1 else 0
        self.set_mirror_state_to_round(mirror_agent_state)

        self.logger.info("Round completed.")

    def run_main_agent(self, round_num: int):
        """Run the main agent for the current round."""
        self.agent.pre_run_hook(new_round=round_num)
        self.agent.run()
        self.agent.post_run_hook(round=round_num)

    def set_mirror_state_to_round(self, round_num: int):
        """Update mirror agent's codebase with the main agent's changes."""
        if round_num == 0:
            full_diff = ""
        else:
            full_diff = self.agent.get_metadata()["diff"][round_num]
            full_diff = filter_git_diff(full_diff)

        self.mirror_agent.reset_and_apply_patch(full_diff)

    def cleanup(self):
        """Clean up game resources."""
        self.game.end(self.cleanup_on_end)

    def evaluate(self, n_repetitions: int = 3):
        """Evaluate the agent's performance by
        calculating the matrix of every round against each other.
        """
        p1 = get_agent(self.config["player"], self.config["prompts"], self.game)
        p1.name = "p1"
        p2 = get_agent(self.config["player"], self.config["prompts"], self.game)
        p2.name = "p2"
        matrix = {
            p1_round: {p2_round: [] for p2_round in range(0, self.rounds + 1)}
            for p1_round in range(0, self.rounds + 1)
        }
        for p1_round in range(0, self.rounds + 1):
            for p2_round in range(0, self.rounds + 1):
                self.logger.info(
                    f"Evaluating agent at round {p1_round} against agent at round {p2_round}"
                )
                p1_patch = (
                    self.agent.get_metadata()["diff"][p1_round] if p1_round > 0 else ""
                )
                p2_patch = (
                    self.agent.get_metadata()["diff"][p2_round] if p2_round > 0 else ""
                )
                p1.reset_and_apply_patch(p1_patch)
                p2.reset_and_apply_patch(p2_patch)
                for i_repetition in range(n_repetitions):
                    result = self.game.run_round([p1, p2])
                    winner = result["winner"]
                    self.logger.info(
                        f"Round {p1_round} vs {p2_round} repetition {i_repetition} winner: {winner}"
                    )
                    matrix[p1_round][p2_round].append(winner)
        self.logger.info(f"Evaluation matrix: {matrix}")
        return matrix
