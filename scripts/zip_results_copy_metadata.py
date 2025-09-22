#!/usr/bin/env python3
"""
Convert legacy log format.
"""

import argparse
import json
import sys
import tarfile
from pathlib import Path

def consolidate_rounds(target_folder):
    """
    Consolidate round results into metadata.json and archive rounds folder.
    
    Args:
        target_folder (str): Path to the target experiment folder
    """
    target_path = Path(target_folder)
    
    if not target_path.exists():
        print(f"Error: Target folder '{target_folder}' does not exist")
        return False
    
    rounds_tar_path = target_path / "rounds.tar.gz"
    
    # 1. Check if rounds.tar.gz already exists
    if rounds_tar_path.exists():
        print(f"rounds.tar.gz already exists in '{target_folder}', skipping")
        return True
    
    # Check if rounds folder exists
    rounds_folder = target_path / "rounds"
    if not rounds_folder.exists():
        print(f"Error: rounds folder does not exist in '{target_folder}'")
        return False
    
    # Load existing metadata.json
    metadata_path = target_path / "metadata.json"
    if not metadata_path.exists():
        print(f"Error: metadata.json does not exist in '{target_folder}'")
        return False
    
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse metadata.json: {e}")
        return False
    
    # 2. Process each round folder and collect results
    round_stats = {}
    
    # Find all round folders (rounds/0, rounds/1, etc.)
    round_folders = [d for d in rounds_folder.iterdir() if d.is_dir() and d.name.isdigit()]
    round_folders.sort(key=lambda x: int(x.name))
    
    for round_folder in round_folders:
        round_num = int(round_folder.name)
        results_path = round_folder / "results.json"
        
        if not results_path.exists():
            print(f"Warning: results.json not found in {round_folder}, skipping")
            continue
        
        try:
            with open(results_path, 'r') as f:
                results = json.load(f)
            
            # Extract the relevant data from results.json
            # Assuming results.json has the structure we need
            round_stats[str(round_num)] = {
                **results  # Include all data from results.json
            }
            
            print(f"Processed round {round_num}")
            
        except json.JSONDecodeError as e:
            print(f"Error: Failed to parse results.json in round {round_num}: {e}")
            continue
        except Exception as e:
            print(f"Error processing round {round_num}: {e}")
            continue
    
    if not round_stats:
        print("Error: No valid round results found")
        return False
    
    # Update metadata with round_stats
    metadata["round_stats"] = round_stats
    
    # Write updated metadata.json
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"Updated metadata.json with {len(round_stats)} rounds")
    except Exception as e:
        print(f"Error: Failed to write updated metadata.json: {e}")
        return False
    
    # 3. Create tar.gz archive of rounds folder
    try:
        print("Creating rounds.tar.gz archive...")
        with tarfile.open(rounds_tar_path, 'w:gz') as tar:
            tar.add(rounds_folder, arcname='rounds')
        
        print(f"Successfully created {rounds_tar_path}")
        
        # Optionally remove the original rounds folder after successful archiving
        # Uncomment the following lines if you want to delete the original folder:
        # shutil.rmtree(rounds_folder)
        # print("Removed original rounds folder")
        
    except Exception as e:
        print(f"Error: Failed to create rounds.tar.gz: {e}")
        return False
    
    print(f"Successfully consolidated rounds for '{target_folder}'")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Consolidate round results into metadata.json and archive rounds folder"
    )
    parser.add_argument(
        "target_folders",
        nargs="+",
        help="Path(s) to the target experiment folder(s)"
    )
    
    args = parser.parse_args()
    
    success_count = 0
    total_count = len(args.target_folders)
    
    for target_folder in args.target_folders:
        print(f"\nProcessing folder: {target_folder}")
        success = consolidate_rounds(target_folder)
        if success:
            success_count += 1
        else:
            print(f"Failed to process folder: {target_folder}")
    
    print(f"\nSummary: {success_count}/{total_count} folders processed successfully")
    
    if success_count < total_count:
        sys.exit(1)

if __name__ == "__main__":
    main()