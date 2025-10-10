import argparse
from pathlib import Path

import yaml

config_path = Path(__file__).parent / "categorize_actions.yaml"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path, help="Path to the input dir")
    args = parser.parse_args()

    config = yaml.safe_load(config_path.read_text())
