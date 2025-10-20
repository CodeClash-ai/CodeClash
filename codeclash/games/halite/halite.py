import re
import shlex
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.constants import RESULT_TIE
from codeclash.games.game import CodeGame, RoundStats

HALITE_LOG = "sim_{idx}.log"
HALITE_SUBMISSION = "submission"
HALITE_HIDDEN_EXEC = ".codeclash_exec"

# Command to be run in each agent's `submission/` folder to compile agent
MAP_FILE_TYPE_TO_COMPILE = {
    ".cpp": "g++ -std=c++11 {path}.cpp -o {name}.o",
    ".c": "gcc {path}.c -o {name}.o",
    ".ml": "ocamlbuild -lib unix {name}.native",
    ".rs": "cargo build",
}

# Command to be run from `environment/` folder to run competition
MAP_FILE_TYPE_TO_RUN = {
    ".c": "{path}/{name}.o",
    ".cpp": "{path}/{name}.o",
    ".js": "node {path}/{name}.js",
    ".ml": "{path}/{name}.native",
    ".py": "python {path}/{name}.py",
    ".rs": "{path}/target/debug/{name}",
}


class HaliteGame(CodeGame):
    name: str = "Halite"
    description: str = f"""Halite is a multi-player turn-based strategy game where bots compete on a rectangular grid to capture territory and accumulate strength.
Players control pieces that can move across the map to conquer neutral and enemy territory, with each cell providing production that increases the strength of pieces occupying it.
The goal is to control the most territory by the end of the game through strategic expansion, consolidation of forces, and tactical combat decisions.

You have the choice of writing your Halite bot in one of four programming languages: C, C++, OCaml, or Rust.
Example implementations can be found under the `airesources/` folder.
Your submission should be stored in the `{HALITE_SUBMISSION}/` folder. This folder currently contains an example C bot, but feel free to use any of the supported languages.
Please make sure your main file is named `main.<ext>`, where `<ext>` is the appropriate file extension for your chosen programming language.
You may include additional files as needed, but please ensure:
1. The `submission/` folder contains only files relevant to your bot.
2. The `submission/` folder ONLY contains a single bot (no multiple bots in one submission).
3. Your bot can be compiled. See `runGame.sh` under the corresponding `submission/<language>/` folder to see how we will compile and run your bot.
"""
    default_args: dict = {}

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.run_cmd_round: str = f"./environment/halite --replaydirectory {self.log_env}"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_round += f" --{arg}"
            else:
                self.run_cmd_round += f" --{arg} {val}"

    def _run_single_simulation(self, agents: list[Player], idx: int, cmd: str):
        """Run a single halite simulation and return the output."""
        cmd = f"{cmd} > {self.log_env / HALITE_LOG.format(idx=idx)}"

        # Run the simulation and return the output
        try:
            response = self.environment.execute(cmd, timeout=120)
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Halite simulation {idx} timed out: {cmd}")
            return
        if response["returncode"] != 0:
            self.logger.warning(
                f"Halite simulation {idx} failed with exit code {response['returncode']}:\n{response['output']}"
            )

    def execute_round(self, agents: list[Player]):
        entries = []
        for agent in agents:
            executable = agent.environment.execute(f"cat {HALITE_HIDDEN_EXEC}")["output"].strip()
            entries.append(executable)
        cmd = f"{self.run_cmd_round} {shlex.join(entries)}"
        self.logger.info(f"Running game: {cmd}")
        with ThreadPoolExecutor(20) as executor:
            futures = [
                executor.submit(self._run_single_simulation, agents, idx, cmd)
                for idx in range(self.game_config["sims_per_round"])
            ]
            for future in tqdm(as_completed(futures), total=len(futures)):
                future.result()

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        winners = []
        pattern = r"Player\s#(\d+),\s(.*),\scame\sin\srank\s#(\d+)"
        for idx in range(self.game_config["sims_per_round"]):
            log_file = self.log_round(round_num) / HALITE_LOG.format(idx=idx)
            with open(log_file) as f:
                lines = f.readlines()[-len(agents) - 1 :]
                for line in lines:
                    match = re.search(pattern, line)
                    if match:
                        player_idx = int(match.group(1)) - 1
                        rank = int(match.group(3))
                        if rank == 1:
                            winners.append(agents[player_idx].name)

        # Count wins
        win_counts = Counter(winners)

        # Find all winners with the maximum count
        max_wins = max(win_counts.values(), default=0)
        overall_winners = [name for name, count in win_counts.items() if count == max_wins]

        # Update stats
        stats.winner = RESULT_TIE if len(overall_winners) > 1 else overall_winners[0]
        stats.scores = dict(win_counts)
        for player, score in win_counts.items():
            if player != RESULT_TIE:
                stats.player_stats[player].score = score

    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        # Check that there is a *single* file called "main.<ext>" in the submission folder
        # and that <ext> is one of the supported file types
        sub_path = Path(agent.environment.config.cwd) / HALITE_SUBMISSION
        ls_output = agent.environment.execute("ls", cwd=sub_path)["output"]
        main_files = [
            fname
            for fname in ls_output.splitlines()
            if fname.startswith("main.") and Path(fname).suffix in MAP_FILE_TYPE_TO_RUN
        ]
        supported_exts = "|".join(MAP_FILE_TYPE_TO_RUN.keys())
        if len(main_files) != 1:
            return (
                False,
                f"Exactly one main.[{supported_exts}] file must be present in submission, found {len(main_files)}",
            )
        main_ext = Path(main_files[0]).suffix

        # Check that the submission compiles if necessary
        if main_ext in MAP_FILE_TYPE_TO_COMPILE:
            compile_cmd = MAP_FILE_TYPE_TO_COMPILE[main_ext].format(path="main", name="main")
            try:
                compile_response = agent.environment.execute(compile_cmd, timeout=15, cwd=sub_path)
            except subprocess.TimeoutExpired:
                return False, f"Compilation failed (ran {compile_cmd} inside {HALITE_SUBMISSION}): timed out"
            if compile_response["returncode"] != 0:
                return (
                    False,
                    f"Compilation failed (ran {compile_cmd} inside {HALITE_SUBMISSION}): {compile_response['output']}",
                )

        # Check that submission runs in competition
        executable = MAP_FILE_TYPE_TO_RUN[main_ext].format(path=HALITE_SUBMISSION, name="main")
        run_cmd = f"./environment/halite {shlex.join([executable, executable])}"
        try:
            run_response = agent.environment.execute(run_cmd, timeout=15)
        except subprocess.TimeoutExpired:
            return False, f"Submission failed to run (ran {run_cmd}): timed out"
        if run_response["returncode"] != 0:
            return False, f"Submission failed to run (ran {run_cmd}): {run_response['output']}"

        # Record command to run executable to hidden file
        executable_comp = MAP_FILE_TYPE_TO_RUN[main_ext].format(path=f"/{agent.name}/{HALITE_SUBMISSION}", name="main")
        agent.environment.execute(f'echo "{executable_comp}" > {HALITE_HIDDEN_EXEC}')
        return True, None
