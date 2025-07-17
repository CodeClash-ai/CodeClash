import subprocess

from codegames.games.abstract import CodeGame
from codegames.games.utils import clone
from pathlib import Path


class BattlesnakeGame(CodeGame):
    name: str = "battlesnake"

    url_server: str = "git@github.com:emagedoc/battlesnake.git"
    url_starter: str = "git@github.com:emagedoc/battlesnake-starter.git"
    build_server: str = "go build -o battlesnake ./cli/battlesnake/main.go"
    run_cmd_player: str = "python main.py"

    def __init__(self, config):
        super().__init__(config)
        self.run_cmd_round: str = "./battlesnake play"
        self.artifacts: list[Path] = []
        for arg, val in config.get("args", {}).items():
            self.run_cmd_round += f" --{arg} {val}"
    
    def cleanup(self):
        self.logger.info("🧼 Cleaning up Battlesnake game environment...")
        for artifact in self.artifacts:
            if artifact.exists():
                subprocess.run(f"rm -rf {artifact}", shell=True)
        self.logger.info("✅ Cleaned up Battlesnake game environment")

    def setup(self):
        self.logger.info("🐍 Setting up Battlesnake game environment...")
        dest = clone(self.url_server)
        self.artifacts.append(dest)
        subprocess.run(self.build_server, shell=True, cwd=dest)
        self.logger.info("✅ Cloned and built Battlesnake local client")
        self.server_path = Path(dest)

    def setup_codebase(self, dest: str) -> Path:
        dest = clone(self.url_starter, dest)
        self.artifacts.append(dest)
        return dest

    def run_round(self, agents: list[any]) -> Path:
        self.logger.info(f"▶️ Running Battlesnake round {self.round}...")
        cmd = self.run_cmd_round
        server_processes = []
        
        for idx, agent in enumerate(agents):
            port = 8001 + idx
            # Start server in background and keep track of the process
            process = subprocess.Popen(f"PORT={port} {self.run_cmd_player}", shell=True, cwd=agent.codebase)
            server_processes.append(process)
            cmd += f" --url http://0.0.0.0:{port} -n {agent.name}"

        if self.config.get("visualize", False):
            cmd += " --browser"
        cmd += f" -o {self.round_log_path}"
        subprocess.run(f"touch {self.round_log_path}", shell=True)
        self.logger.info(f"Running command: {cmd}")
        
        try:
            # Run the actual game
            subprocess.run(cmd, shell=True, cwd=self.server_path)
        finally:
            # Shut down all server processes
            self.logger.info("🛑 Shutting down player servers...")
            for process in server_processes:
                if process.poll() is None:  # Process is still running
                    process.terminate()
                    try:
                        process.wait(timeout=5)  # Wait up to 5 seconds for graceful shutdown
                    except subprocess.TimeoutExpired:
                        process.kill()  # Force kill if it doesn't shut down gracefully
            self.logger.info("✅ All player servers shut down")
        self.logger.info(f"✅ Completed Battlesnake round {self.round}")
        self.round += 1
