"""
Integration test for main.py with BattleSnake configuration.

This test verifies that the main execution flow works without exceptions,
using DeterministicModel instead of real LLM models.
"""

import os
import tempfile
from unittest.mock import patch

import pytest
import yaml
from minisweagent.models.test_models import DeterministicModel

from main import main


def test_main_battlesnake_integration():
    """
    Integration test for main.py with configs/battlesnake.yaml.
    Success criterion: execution completes without exceptions.
    """
    # Create a temporary config file with DeterministicModel settings
    config_path = "configs/battlesnake.yaml"

    # Read the original config
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Create a temporary directory for test artifacts
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_config_path = os.path.join(temp_dir, "test_battlesnake.yaml")

        # Reduce rounds to 1 for faster testing
        config["game"]["rounds"] = 1

        # Write the modified config
        with open(temp_config_path, "w") as f:
            yaml.dump(config, f)

        def mock_get_agent(original_get_agent):
            """Wrapper to replace agent models with DeterministicModel"""

            def wrapper(agent_config, game):
                agent = original_get_agent(agent_config, game)
                print("In wrapper, got agent of type ", type(agent))

                # Replace model if the agent has one (specifically for MiniSWEAgent)
                if hasattr(agent, "agent") and hasattr(agent.agent, "model"):
                    print(f"Replacing model for agent {agent.name}")
                    # Create DeterministicModel with the specified command
                    deterministic_model = DeterministicModel(
                        outputs=[
                            "```bash\necho 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'\n```"
                        ]
                    )
                    agent.agent.model = deterministic_model

                return agent

            return wrapper

        # Import the get_agent function and patch it where it's used in main
        from codeclash.agents import get_agent

        # Run the main function with cleanup enabled
        with patch("main.get_agent", side_effect=mock_get_agent(get_agent)):
            # This should complete without raising any exceptions
            main(temp_config_path, cleanup=True, push_agent=False)
