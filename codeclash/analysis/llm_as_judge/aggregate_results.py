#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from typing import Any

from codeclash.analysis.llm_as_judge.utils import Instance
from codeclash.utils.log import get_logger

logger = get_logger("AggregateResults", emoji="📊")


def aggregate_results(input_dir: Path) -> dict[str, Any]:
    """Aggregate all llm_as_judge.json results from the input directory.
    
    Returns:
        Dictionary with structure {data_id: {instance_id: result_data}}
    """
    aggregated = {}
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
            
            # Merge each data_id from this file into the aggregated results
            for data_id, instances in file_data.items():
                if data_id not in aggregated:
                    aggregated[data_id] = {}
                
                # Check for duplicate instance_ids
                for instance_id, instance_data in instances.items():
                    if instance_id in aggregated[data_id]:
                        logger.warning(f"Duplicate instance_id '{instance_id}' found in {file_path}")
                    
                    # Add model info
                    instance = Instance.model_validate(instance_data["instance"])
                    model_name, opponent_model_name = instance.get_lm_name_self_opponent()
                    instance_data.setdefault("info", {})
                    instance_data["info"]["model_name"] = model_name
                    instance_data["info"]["opponent_model_name"] = opponent_model_name
                    
                    aggregated[data_id][instance_id] = instance_data
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}", exc_info=True)
    
    total_instances = sum(len(instances) for instances in aggregated.values())
    logger.info(f"Aggregated {total_instances} instances across {len(aggregated)} data versions")
    
    return aggregated


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate LLM-as-judge evaluation results")
    parser.add_argument("input_dir", type=Path, help="Path to the input directory containing tournament results")
    parser.add_argument("-o", "--output-file", type=Path, 
                       help="Path to the output file", default="aggregated_results.json")
    args = parser.parse_args()
    
    if not args.input_dir.exists():
        logger.error(f"Input directory does not exist: {args.input_dir}")
        return
    
    logger.info(f"Aggregating results from {args.input_dir}")
    aggregated = aggregate_results(args.input_dir)
    
    args.output_file.write_text(json.dumps(aggregated, indent=2))
    logger.info(f"Wrote aggregated results to {args.output_file}")


if __name__ == "__main__":
    main()