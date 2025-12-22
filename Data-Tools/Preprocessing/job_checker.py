#!/usr/bin/env python3
"""
Script to check for empty replicate folders in Timing_Results directory.
Outputs ML model, OpenML task id, and SLURM array id for any empty folders.
"""

import os
import argparse
from pathlib import Path


# Task IDs from runner.sb in the correct order
TASK_IDS = [
    190412, 146818, 359955, 168757, 359956, 359958, 359962, 190137, 168911, 190392,
    189922, 359965, 359966, 359967, 190411, 146820, 359968, 359975, 359972, 168350,
    359973, 190410, 359971, 359988, 359989, 359979, 359980, 359992, 359982, 167120,
    359990, 189354, 360114, 359994
]

# Number of replicates per task
NUM_REPLICATES = 10

# Model folder names (7 models)
MODEL_FOLDERS = [
    "DT_Timing",
    "ET_Timing",
    "GB_Timing",
    "KSVC_Timing",
    "LSGD_Timing",
    "LSVC_Timing",
    "RF_Timing"
]


def is_folder_empty(folder_path):
    """
    Check if a folder is empty or doesn't exist.

    Args:
        folder_path: Path to the folder to check

    Returns:
        True if folder is empty or doesn't exist, False otherwise
    """
    if not os.path.exists(folder_path):
        return True

    if not os.path.isdir(folder_path):
        return True

    # Check if directory has any files or subdirectories
    return len(os.listdir(folder_path)) == 0


def calculate_array_id(task_index, replicate):
    """
    Calculate the SLURM array ID based on task index and replicate number.

    Formula: SLURM_ARRAY_TASK_ID = TASK_INDEX * NUM_REPLICATES + REP

    Args:
        task_index: Index in the TASK_IDS array
        replicate: Replicate number (0-9)

    Returns:
        The SLURM array ID
    """
    return task_index * NUM_REPLICATES + replicate


def check_timing_results(timing_results_dir):
    """
    Check all model folders for empty replicate directories.

    Args:
        timing_results_dir: Path to the Timing_Results directory
    """
    timing_results_path = Path(timing_results_dir)

    if not timing_results_path.exists():
        print(f"ERROR: Directory does not exist: {timing_results_dir}")
        return

    print("=" * 80)
    print("Checking for empty replicate folders...")
    print("=" * 80)
    print(f"{'Model':<15} {'Task ID':<10} {'Replicate':<10} {'Array ID':<10}")
    print("-" * 80)

    empty_count = 0
    # Dictionary to store array IDs per model
    model_array_ids = {model.replace("_Timing", ""): [] for model in MODEL_FOLDERS}

    # Iterate through each model folder
    for model_folder in MODEL_FOLDERS:
        model_path = timing_results_path / model_folder
        model_name = model_folder.replace("_Timing", "")

        if not model_path.exists():
            print(f"WARNING: Model folder not found: {model_folder}")
            continue

        # Iterate through task IDs in order
        for task_index, task_id in enumerate(TASK_IDS):
            task_folder_name = f"task_{task_id}"
            task_path = model_path / task_folder_name

            if not task_path.exists():
                # If task folder doesn't exist, all replicates are missing
                for rep in range(NUM_REPLICATES):
                    array_id = calculate_array_id(task_index, rep)
                    print(f"{model_name:<15} {task_id:<10} {rep:<10} {array_id:<10}")
                    model_array_ids[model_name].append(array_id)
                    empty_count += 1
                continue

            # Check each replicate folder
            for rep in range(NUM_REPLICATES):
                replicate_folder_name = f"Replicate_{rep}"
                replicate_path = task_path / replicate_folder_name

                if is_folder_empty(replicate_path):
                    array_id = calculate_array_id(task_index, rep)
                    print(f"{model_name:<15} {task_id:<10} {rep:<10} {array_id:<10}")
                    model_array_ids[model_name].append(array_id)
                    empty_count += 1

    print("-" * 80)
    print(f"Total empty replicate folders found: {empty_count}")
    print("=" * 80)
    
    # Print array IDs per model
    print("\n" + "=" * 80)
    print("Array IDs to Rerun by Model")
    print("=" * 80)
    
    for model_name in [m.replace("_Timing", "") for m in MODEL_FOLDERS]:
        array_ids = model_array_ids[model_name]
        if array_ids:
            # Sort array IDs for cleaner output
            array_ids.sort()
            print(f"\n{model_name}:")
            print(f"  Count: {len(array_ids)}")
            print(f"  Array IDs: {','.join(map(str, array_ids))}")
        else:
            print(f"\n{model_name}:")
            print(f"  Count: 0")
            print(f"  All replicates complete!")
    
    print("\n" + "=" * 80)


def main():
    """Main function to parse arguments and run the checker."""
    parser = argparse.ArgumentParser(
        description="Check for empty replicate folders in Timing_Results directory"
    )
    parser.add_argument(
        "--timing_results_dir",
        type=str,
        required=True,
        help="Path to the Timing_Results directory"
    )

    args = parser.parse_args()
    check_timing_results(args.timing_results_dir)


if __name__ == "__main__":
    main()
