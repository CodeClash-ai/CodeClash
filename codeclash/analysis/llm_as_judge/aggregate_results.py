#!/usr/bin/env python3

"""Aggregate results from multiple llm_as_judge.json files
and save as a compressed parquet file for efficient storage and loading.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from codeclash.analysis.llm_as_judge.categorize_actions import _all_categories as ACTION_CATEGORIES
from codeclash.analysis.llm_as_judge.utils import Instance
from codeclash.utils.log import get_logger

logger = get_logger("AggregateResults", emoji="📊")

# Version constants for specific data_ids
BIG_QUESTIONS_VERSION = 7
ACTION_CATEGORIES_VERSION = 3


class ResultsAggregator:
    """Class for aggregating LLM-as-judge evaluation results."""

    def __init__(self):
        self.big_questions_data_id = f"big_questions_v{BIG_QUESTIONS_VERSION}"
        self.action_categories_data_id = f"action_categories_v{ACTION_CATEGORIES_VERSION}"

    def aggregate_results_to_dataframe(self, input_dir: Path) -> pd.DataFrame:
        """Aggregate all llm_as_judge.json results from the input directory into a DataFrame.

        Returns:
            DataFrame with flattened structure containing all evaluation data merged by instance_id
        """
        # Dictionary to collect all data by instance_id
        instance_data_dict = {}
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
                    # Only process allowed data_ids
                    if data_id not in [self.action_categories_data_id, self.big_questions_data_id]:
                        continue

                    for instance_id, instance_data in instances.items():
                        # Initialize instance data if not seen before
                        if instance_id not in instance_data_dict:
                            instance_data_dict[instance_id] = self._initialize_instance_row(instance_data)

                        # Add data specific to this data_id
                        self._add_data_id_results(instance_data_dict[instance_id], data_id, instance_data)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON in {file_path}: {e}")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}", exc_info=True)

        # Convert to list of rows for DataFrame
        rows = list(instance_data_dict.values())
        df = pd.DataFrame(rows)

        # Count instances for each data_id source
        action_categories_count = 0
        big_questions_count = 0

        for row in rows:
            data_ids = row.get("data_ids", [])
            if self.action_categories_data_id in data_ids:
                action_categories_count += 1
            if self.big_questions_data_id in data_ids:
                big_questions_count += 1

        logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
        logger.info(f"Instances with {self.action_categories_data_id}: {action_categories_count}")
        logger.info(f"Instances with {self.big_questions_data_id}: {big_questions_count}")

        return df

    def _initialize_instance_row(self, instance_data: dict) -> dict:
        """Initialize a row with basic instance metadata and NaN values for all data types."""
        instance = Instance.model_validate(instance_data["instance"])
        model_name, opponent_model_name = instance.get_lm_name_self_opponent()
        current_round_win_rate, next_round_win_rate = instance.get_current_next_round_win_rate()

        # Create base row with instance metadata
        row = {
            "instance_id": instance.instance_id,
            "tournament_name": instance.tournament_name,
            "player_name": instance.player_name,
            "round_number": instance.round_number,
            "model_name": model_name,
            "opponent_model_name": opponent_model_name,
            "current_round_win_rate": current_round_win_rate,
            "next_round_win_rate": next_round_win_rate,
        }

        # Initialize all action category counts to NaN (will be overwritten if action categories data exists)
        for category in ACTION_CATEGORIES:
            row[f"category_count_{category}"] = pd.NA

        return row

    def _add_data_id_results(self, row: dict, data_id: str, instance_data: dict) -> None:
        """Add results from a specific data_id to the row."""
        # Add the data_id information
        if "data_ids" not in row:
            row["data_ids"] = []
        row["data_ids"].append(data_id)

        # Delegate to specific handlers based on data_id type
        if data_id == self.action_categories_data_id:
            self._add_action_categories_results(row, instance_data)
        elif data_id == self.big_questions_data_id:
            self._add_big_questions_results(row, instance_data)
        # Ignore other data_ids that are not handled

    def _add_action_categories_results(self, row: dict, instance_data: dict) -> None:
        """Add action categories results to the row."""
        if "result" in instance_data:
            result_data = instance_data["result"]

            # Handle action category counts specially
            categories = result_data.get("categories", [])
            self._add_action_category_counts(row, categories)

            # Add all other result data without prefix
            for key, value in result_data.items():
                row[key] = value

    def _add_big_questions_results(self, row: dict, instance_data: dict) -> None:
        """Add big questions results to the row."""
        if "result" in instance_data:
            result_data = instance_data["result"]

            # Add all result data without prefix
            for key, value in result_data.items():
                row[key] = value

    def _add_action_category_counts(self, row: dict, categories: list) -> None:
        """Add category counts to the row for action categories data."""
        # Initialize all category counts to 0 (this ensures missing categories are 0, not NaN)
        for category in ACTION_CATEGORIES:
            row[f"c_{category}"] = 0

        # Count occurrences of each category
        if categories:
            category_counts = Counter(cat.get("category") for cat in categories if cat.get("category"))
            for category, count in category_counts.items():
                if category in ACTION_CATEGORIES:
                    row[f"c_{category}"] = count


def aggregate_results_to_dataframe(input_dir: Path) -> pd.DataFrame:
    """Convenience function for backward compatibility."""
    aggregator = ResultsAggregator()
    return aggregator.aggregate_results_to_dataframe(input_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate LLM-as-judge evaluation results to Parquet")
    parser.add_argument("input_dir", type=Path, help="Path to the input directory containing tournament results")
    parser.add_argument(
        "-o", "--output-file", type=Path, help="Path to the output Parquet file", default="aggregated_results.parquet"
    )
    args = parser.parse_args()

    if not args.input_dir.exists():
        logger.error(f"Input directory does not exist: {args.input_dir}")
        return

    logger.info(f"Aggregating results from {args.input_dir}")
    aggregator = ResultsAggregator()
    df = aggregator.aggregate_results_to_dataframe(args.input_dir)

    df.to_parquet(args.output_file, compression="snappy", index=False)
    logger.info(f"Wrote aggregated results to {args.output_file}")


if __name__ == "__main__":
    main()
