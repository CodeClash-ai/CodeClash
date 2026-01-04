import re
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Literal

from tqdm.auto import tqdm

from codeclash.agents.player import Player
from codeclash.arenas.arena import CodeArena, RoundStats
from codeclash.constants import DIR_WORK, RESULT_TIE

BC24_LOG = "sim_{idx}.log"
BC24_FOLDER = "mysubmission"
BC24_TIE = "Reason: The winning team won arbitrarily (coin flip)."


@dataclass
class SimulationMeta:
    """Metadata for a single simulation, storing team assignments explicitly."""
    idx: int
    team_a: str  
    team_b: str 
    log_file: str


@dataclass
class RoundResult:
    """Result of execute_round, used to communicate status to get_results."""
    status: Literal["completed", "auto_win", "no_contest"]
    winner: str | None = None
    loser: str | None = None 
    reason: str = ""
    simulations: list[SimulationMeta] = field(default_factory=list)


class BattleCode24Arena(CodeArena):
    """BattleCode24 arena implementation.
    
    Lifecycle:
    1. validate_code() - Source-level structural checks only (in agent container)
    2. execute_round() - Compile and run simulations (in game container)
    3. get_results() - Parse logs and determine winner
    
    Failure handling:
    - If one agent fails to compile, the other wins automatically
    - If both fail to compile, round is a no-contest (tie)
    - Individual simulation failures don't count toward either player
    """
    
    name: str = "BattleCode24"
    description: str = """Battlecode 2024: Breadwars is a real-time strategy game where your Java bot controls a team of robots competing to capture the opponent's flags.
Your mission: capture all 3 of the opponent's flags before they capture yours. Robots can attack, heal, build traps, dig/fill terrain, and specialize in different skills through experience.
The game features a setup phase (first 200 rounds) where teams are separated by a dam, followed by open combat. Robots gain experience and level up their attack, build, and heal specializations."""
    default_args: dict = {
        "maps": "DefaultSmall",
    }
    submission: str = "src/mysubmission"

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        assert len(config["players"]) == 2, "BattleCode24 is a two-player game"
        
        # Build base run command
        self.run_cmd_base: str = "./gradlew --no-daemon run"
        for arg, val in self.game_config.get("args", self.default_args).items():
            if isinstance(val, bool):
                if val:
                    self.run_cmd_base += f" -P{arg}=true"
            else:
                self.run_cmd_base += f" -P{arg}={val}"
        
        # Round state (set by execute_round, used by get_results)
        self._round_result: RoundResult | None = None

    
    def validate_code(self, agent: Player) -> tuple[bool, str | None]:
        """Validate source structure. No compilation - that happens in execute_round.
        
        Checks:
        1. src/mysubmission/ directory exists
        2. RobotPlayer.java file exists
        3. run(RobotController rc) method signature present
        4. Correct package declaration
        """
        # Check for mysubmission directory
        ls_output = agent.environment.execute("ls src")["output"]
        if BC24_FOLDER not in ls_output:
            return False, f"There should be a `src/{BC24_FOLDER}/` directory"
        
        # Check for RobotPlayer.java file
        ls_mysubmission = agent.environment.execute(f"ls src/{BC24_FOLDER}")["output"]
        if "RobotPlayer.java" not in ls_mysubmission:
            return False, f"There should be a `src/{BC24_FOLDER}/RobotPlayer.java` file"
        
        # Check for run(RobotController rc) method
        robot_player_content = agent.environment.execute(f"cat src/{BC24_FOLDER}/RobotPlayer.java")["output"]
        if "public static void run(RobotController" not in robot_player_content:
            return False, f"There should be a `run(RobotController rc)` method implemented in `src/{BC24_FOLDER}/RobotPlayer.java`"
        
        # Check for correct package declaration
        if f"package {BC24_FOLDER};" not in robot_player_content:
            return False, f"The package declaration should be `package {BC24_FOLDER};` in `src/{BC24_FOLDER}/RobotPlayer.java`"
        
        return True, None

    
    def _compile_agent(self, agent: Player, idx: int) -> str | None:
        """Compile an agent's code in the game container.
        
        Args:
            agent: The agent to compile
            idx: Index for naming the output directory
            
        Returns:
            Path to compiled classes directory, or None if compilation failed
        """
        # Copy agent code to workspace
        src = f"/{agent.name}/src/{BC24_FOLDER}/"
        dest = str(DIR_WORK / "src" / BC24_FOLDER)
        self.environment.execute(f"rm -rf {dest}; mkdir -p {dest}; cp -r {src}* {dest}/")
        
        # Compile (use clean to ensure fresh compilation, avoiding stale cache)
        compile_result = self.environment.execute("./gradlew clean compileJava", timeout=120)
        if compile_result["returncode"] != 0:
            self.logger.warning(
                f"Failed to compile agent {agent.name}:\n{compile_result['output'][-1000:]}"
            )
            return None
        
        # Save compiled classes outside build/ (gradle clean deletes build/)
        classes_dir = f"/tmp/agent{idx}_classes"
        self.environment.execute(
            f"rm -rf {classes_dir}; mkdir -p {classes_dir}; cp -r build/classes/* {classes_dir}/"
        )
        
        self.logger.info(f"Successfully compiled {agent.name}")
        return classes_dir

    
    def _run_simulation(
        self,
        sim_meta: SimulationMeta,
        agents: list[Player],
        agent_classes: dict[str, str],
    ) -> None:
        """Run a single simulation.
        
        Args:
            sim_meta: Simulation metadata with team assignments
            agents: List of agents (for name lookup)
            agent_classes: Map of agent name -> compiled classes path
        """
        cmd = (
            f"{self.run_cmd_base} "
            f"-PteamA={sim_meta.team_a} "
            f"-PteamB={sim_meta.team_b} "
            f"-PpackageNameA=mysubmission "
            f"-PpackageNameB=mysubmission "
            f"-PclassLocationA={agent_classes[sim_meta.team_a]} "
            f"-PclassLocationB={agent_classes[sim_meta.team_b]}"
        )
        
        try:
            response = self.environment.execute(
                cmd + f" > {self.log_env / sim_meta.log_file} 2>&1",
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Simulation {sim_meta.idx} timed out")
            return
        
        if response["returncode"] != 0:
            self.logger.warning(
                f"Simulation {sim_meta.idx} failed with exit code {response['returncode']}"
            )

    def execute_round(self, agents: list[Player]):
        """Execute a round: compile all agents, then run simulations.
        
        Handles failures gracefully:
        - If one agent fails to compile, the other wins automatically
        - If both fail, round is a no-contest
        """
        # Phase 1: Compile all agents
        agent_classes: dict[str, str | None] = {}
        for idx, agent in enumerate(agents):
            classes_path = self._compile_agent(agent, idx)
            agent_classes[agent.name] = classes_path
        
        # Check compilation results
        compiled_agents = [a for a in agents if agent_classes[a.name] is not None]
        failed_agents = [a for a in agents if agent_classes[a.name] is None]
        
        if len(compiled_agents) == 0:
            self.logger.error("All agents failed to compile - no contest")
            self._round_result = RoundResult(
                status="no_contest",
                reason="all agents failed to compile",
            )
            return
        
        if len(compiled_agents) == 1:
            winner = compiled_agents[0]
            loser = failed_agents[0]
            self.logger.info(
                f"Only {winner.name} compiled successfully (opponent {loser.name} failed) - automatic win"
            )
            self._round_result = RoundResult(
                status="auto_win",
                winner=winner.name,
                loser=loser.name,
                reason=f"{loser.name} failed to compile",
            )
            return
        
        # Phase 2: Build simulation metadata with alternating team positions
        num_sims = self.game_config["sims_per_round"]
        simulations: list[SimulationMeta] = []
        
        for idx in range(num_sims):
            # Alternate team positions for fairness
            if idx % 2 == 0:
                team_a, team_b = agents[0].name, agents[1].name
            else:
                team_a, team_b = agents[1].name, agents[0].name
            
            simulations.append(SimulationMeta(
                idx=idx,
                team_a=team_a,
                team_b=team_b,
                log_file=BC24_LOG.format(idx=idx),
            ))
        
        # Phase 3: Run simulations in parallel
        self.logger.info(f"Running {num_sims} simulations with alternating team positions")
        
        # Filter to only compiled agents' classes
        valid_classes = {name: path for name, path in agent_classes.items() if path is not None}
        
        with ThreadPoolExecutor(5) as executor:
            futures = [
                executor.submit(self._run_simulation, sim, agents, valid_classes)
                for sim in simulations
            ]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Simulations"):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Simulation raised unexpected exception: {e}")
        
        self._round_result = RoundResult(
            status="completed",
            simulations=simulations,
        )
    
    def _parse_simulation_log(self, log_path, sim_meta: SimulationMeta) -> str | None:
        """Parse a single simulation log to determine the winner.
        
        Args:
            log_path: Path to the log file
            sim_meta: Simulation metadata with team assignments
            
        Returns:
            Winner agent name, RESULT_TIE, or None if parsing failed
        """
        if not log_path.exists():
            self.logger.debug(f"Simulation {sim_meta.idx}: log file missing")
            return None
        
        with open(log_path) as f:
            content = f.read().strip()
        
        lines = content.split("\n")
        if len(lines) < 2:
            self.logger.debug(f"Simulation {sim_meta.idx}: log too short (game crashed?)")
            return None
        
        # Find the winner line (contains "wins" and "[server]")
        winner_line = None
        reason_line = None
        for i, line in enumerate(lines):
            if "wins" in line and "[server]" in line:
                winner_line = line
                if i + 1 < len(lines):
                    reason_line = lines[i + 1]
                break
        
        if not winner_line:
            self.logger.debug(f"Simulation {sim_meta.idx}: no winner line found")
            return RESULT_TIE
        
        # Extract A or B from winner line: "mysubmission (A) wins" or "mysubmission (B) wins"
        match = re.search(r"\(([AB])\)\s+wins", winner_line)
        if not match:
            self.logger.debug(f"Simulation {sim_meta.idx}: could not parse winner from line")
            return RESULT_TIE
        
        winner_key = match.group(1)
        
        # Check for coin flip tie
        if reason_line and BC24_TIE in reason_line:
            return RESULT_TIE
        
        # Map A/B to agent names using stored metadata (no recalculation needed)
        if winner_key == "A":
            return sim_meta.team_a
        else:
            return sim_meta.team_b

    def get_results(self, agents: list[Player], round_num: int, stats: RoundStats):
        """Parse simulation results and determine the round winner."""
        
        # Handle early termination cases
        if self._round_result is None:
            self.logger.error("get_results called but execute_round didn't set _round_result")
            stats.winner = RESULT_TIE
            return
        
        if self._round_result.status == "no_contest":
            self.logger.info(f"Round ended in no-contest: {self._round_result.reason}")
            stats.winner = RESULT_TIE
            # Split points evenly
            points = self.game_config["sims_per_round"] / len(agents)
            for agent in agents:
                stats.scores[agent.name] = points
                stats.player_stats[agent.name].score = points
                stats.player_stats[agent.name].valid_submit = False
                stats.player_stats[agent.name].invalid_reason = "Compilation failed (no contest)"
            return
        
        if self._round_result.status == "auto_win":
            winner = self._round_result.winner
            loser = self._round_result.loser
            self.logger.info(f"Round auto-win: {winner} ({self._round_result.reason})")
            stats.winner = winner
            stats.scores[winner] = self.game_config["sims_per_round"]
            stats.player_stats[winner].score = self.game_config["sims_per_round"]
            if loser and loser in stats.player_stats:
                stats.player_stats[loser].valid_submit = False
                stats.player_stats[loser].invalid_reason = f"Compilation failed: {self._round_result.reason}"
            return
        
        # Normal case: parse simulation logs
        scores = defaultdict(int)
        
        tie_count = 0
        for sim in self._round_result.simulations:
            log_path = self.log_round(round_num) / sim.log_file
            winner = self._parse_simulation_log(log_path, sim)
            
            if winner is None:
                pass  
            elif winner == RESULT_TIE:
                tie_count += 1 
            else:
                scores[winner] += 1
        
        if tie_count > 0:
            self.logger.info(f"{tie_count} simulation(s) ended in tie")
        
        # Determine overall winner
        if scores:
            # Find max score, check for ties
            max_score = max(scores.values())
            leaders = [name for name, score in scores.items() if score == max_score]
            
            if len(leaders) == 1:
                stats.winner = leaders[0]
            else:
                stats.winner = RESULT_TIE
        else:
            # All simulations failed
            self.logger.warning("All simulations failed to produce results")
            stats.winner = RESULT_TIE
        
        for player, score in scores.items():
            stats.scores[player] = score
            if player != RESULT_TIE:
                stats.player_stats[player].score = score
