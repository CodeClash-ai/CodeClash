"""
Pushes diffs as a branch to Github.
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

from unidiff import PatchSet

from codeclash.constants import GH_ORG


def remove_binaries(patch: PatchSet) -> PatchSet:
    """Remove binary files from diff patch string"""
    return PatchSet("\n".join([str(file) for file in patch if "Binary files" not in str(file)]))


def main(cc_folder: Path):
    folder_contents = [f.name for f in list(cc_folder.iterdir())]
    assert "metadata.json" in folder_contents, "No metadata.json found"
    assert "players" in folder_contents, "No players/ folder found"

    arena = cc_folder.name.split(".", 2)[1]

    # Clone GitHub repository if it doesn't exist
    if arena not in os.listdir():
        clone_cmd = f"git clone git@github.com:{GH_ORG}/{arena}.git"
        subprocess.run(clone_cmd, shell=True, check=True)

    # Get existing remote branches
    remote_branches = (
        subprocess.run(
            "git branch -r",
            shell=True,
            check=True,
            capture_output=True,
            cwd=arena,
        )
        .stdout.decode("utf-8")
        .splitlines()
    )
    remote_branches = [b.split("/")[-1] for b in remote_branches if "PvpTournament" in b]

    # Identify players
    with open(cc_folder / "metadata.json") as f:
        metadata = json.load(f)
    players = [x["name"] for x in metadata["config"]["players"]]

    # Push diffs for each player
    for player in players:
        player_log_folder = cc_folder / "players" / player
        branch_name = f"{cc_folder.name}.{player}"
        if branch_name in remote_branches:
            print(f"Branch {branch_name} already exists, skipping...")
            continue
        subprocess.run(
            f"git checkout main; git branch {branch_name} -D; git checkout -b {branch_name}",
            shell=True,
            check=True,
            cwd=arena,
        )
        for idx in range(1, 16):
            changes_file = player_log_folder / f"changes_r{idx}.json"
            if not changes_file.exists():
                continue
            with open(changes_file) as f:
                changes = json.load(f)
            # Remove any binary files from the patch
            patch = remove_binaries(PatchSet(changes["incremental_diff"]))
            with open("temp.diff", "w") as f:
                f.write(str(patch))

            apply_cmd = "git apply ../temp.diff"
            subprocess.run(apply_cmd, shell=True, check=True, cwd=arena)
            subprocess.run("git add .", shell=True, check=True, cwd=arena)
            subprocess.run(f"git commit -m 'Round {idx} changes'", shell=True, check=True, cwd=arena)
            subprocess.run(f"git push origin {branch_name}", shell=True, check=True, cwd=arena)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("cc_folder", type=Path, help="Path to the CodeClash log folder")
    args = parser.parse_args()
    main(args.cc_folder)
