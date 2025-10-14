#!/usr/bin/env python3

"""Aggregate results from multiple llm_as_judge.json files
and save as a compressed parquet file for efficient storage and loading.
"""

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from codeclash.analysis.llm_as_judge.utils import Instance
from codeclash.utils.log import get_logger

logger = get_logger("AggregateResults", emoji="📊")


def aggregate_results_to_dataframe(input_dir: Path) -> pd.DataFrame:
    """Aggregate all llm_as_judge.json results from the input directory into a DataFrame.
    
    Returns:
        DataFrame with flattened structure containing all evaluation data
    """
    rows = []
    llm_judge_files = list(input_dir.rglob("llm_as_judge.json"))
    
    logger.info(f"Found {len(llm_judge_files)} llm_as_judge.json files")
    
    for file_path in llm_judge_files:
        logger.debug(f"Processing {file_path}")
        
        try:
            content = file_path.read_text().strip()
            if not content:
                logger.warning(f"Skipping empty file: {file_path}")
                continue
                
            file_data = json.loads(content)
            
            # Process each data_id and instance
            for data_id, instances in file_data.items():
                for instance_id, instance_data in instances.items():
                    # Extract instance metadata
                    instance = Instance.model_validate(instance_data["instance"])
                    model_name, opponent_model_name = instance.get_lm_name_self_opponent()
                    
                    # Create a flat row with all information
                    row = {
                        "data_id": data_id,
                        "instance_id": instance_id,
                        "tournament_name": instance.tournament_name,
                        "player_name": instance.player_name,
                        "round_number": instance.round_number,
                        "model_name": model_name,
                        "opponent_model_name": opponent_model_name,
                    }
                    
                    # Add all evaluation results
                    if "result" in instance_data:
                        result_data = instance_data["result"]
                        for key, value in result_data.items():
                            row[key] = value
                    
                    rows.append(row)
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
    
    df = pd.DataFrame(rows)
    logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
    
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate LLM-as-judge evaluation results to Parquet")
    parser.add_argument("input_dir", type=Path, help="Path to the input directory containing tournament results")
    parser.add_argument("-o", "--output-file", type=Path, 
                       help="Path to the output Parquet file", default="aggregated_results.parquet")
    args = parser.parse_args()
    
    if not args.input_dir.exists():
        logger.error(f"Input directory does not exist: {args.input_dir}")
        return
    
    logger.info(f"Aggregating results from {args.input_dir}")
    df = aggregate_results_to_dataframe(args.input_dir)
    
    df.to_parquet(args.output_file, compression="snappy", index=False)
    logger.info(f"Wrote aggregated results to {args.output_file}")


if __name__ == "__main__":
    main()