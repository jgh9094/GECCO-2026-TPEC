#!/usr/bin/env python3
"""
Script to aggregate ML model results and update tasks_summary.csv
with average test accuracies and failure information.
"""

import os
import json
import pandas as pd
import argparse
from pathlib import Path


def check_replicate_status(replicate_path):
    """
    Check the status of a replicate directory.

    Returns:
        tuple: (is_valid, failure_reason)
            - is_valid: True if replicate can be used for averaging
            - failure_reason: None, 'memory-limit', or 'time-limit'
    """
    replicate_dir = Path(replicate_path)

    # Check if directory is empty
    if not any(replicate_dir.iterdir()):
        return False, 'memory-limit'

    # Check if global_accuracy_results.json exists
    global_results_path = replicate_dir / 'global_accuracy_results.json'
    if not global_results_path.exists():
        return False, 'memory-limit'

    # Check if time_exceeded is True
    try:
        with open(global_results_path, 'r') as f:
            global_results = json.load(f)
            if global_results.get('time_exceeded', False):
                return False, 'time-limit'
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not read {global_results_path}: {e}")
        return False, 'memory-limit'

    # Check if best_model_results.json exists
    best_model_path = replicate_dir / 'best_model_results.json'
    if not best_model_path.exists():
        return False, 'memory-limit'

    return True, None


def get_test_accuracy(replicate_path):
    """
    Extract test_accuracy from best_model_results.json.

    Returns:
        float or None: test_accuracy value or None if not found
    """
    best_model_path = Path(replicate_path) / 'best_model_results.json'

    try:
        with open(best_model_path, 'r') as f:
            best_model_results = json.load(f)
            return best_model_results.get('test_accuracy', None)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Warning: Could not read {best_model_path}: {e}")
        return None


def process_task_model(timing_results_dir, model_name, task_id, num_replicates=10):
    """
    Process results for a specific task and model combination.

    Args:
        timing_results_dir: Path to Timing_Results directory
        model_name: Name of the ML model (e.g., 'DT_Timing')
        task_id: Task ID (e.g., '146818')
        num_replicates: Number of replicates to check (default: 10)

    Returns:
        tuple: (avg_test_accuracy, failure_reason)
            - avg_test_accuracy: float or None
            - failure_reason: 'None', 'memory-limit', or 'time-limit'
    """
    task_path = Path(timing_results_dir) / model_name / f'task_{task_id}'

    if not task_path.exists():
        return None, 'None'

    test_accuracies = []
    failure_reasons = set()

    for i in range(num_replicates):
        replicate_path = task_path / f'Replicate_{i}'

        if not replicate_path.exists():
            failure_reasons.add('memory-limit')
            continue

        is_valid, failure_reason = check_replicate_status(replicate_path)

        if not is_valid:
            failure_reasons.add(failure_reason)
        else:
            test_accuracy = get_test_accuracy(replicate_path)
            if test_accuracy is not None:
                test_accuracies.append(test_accuracy)

    # Determine overall failure status
    if 'memory-limit' in failure_reasons:
        overall_failure = 'memory-limit'
    elif 'time-limit' in failure_reasons:
        overall_failure = 'time-limit'
    else:
        overall_failure = 'None'

    # Calculate average test accuracy if we have valid data
    avg_test_accuracy = None
    if test_accuracies:
        avg_test_accuracy = sum(test_accuracies) / len(test_accuracies)

    return avg_test_accuracy, overall_failure


def aggregate_results(tasks_summary_path, timing_results_dir, output_path=None, threshold=None):
    """
    Main function to aggregate results and update tasks_summary.csv.

    Args:
        tasks_summary_path: Path to tasks_summary.csv
        timing_results_dir: Path to Timing_Results directory
        output_path: Path to save updated CSV (default: overwrites input)
        threshold: Float threshold to filter out tasks with any model performance >= threshold
    """
    # Read the tasks summary CSV
    df = pd.read_csv(tasks_summary_path)

    # Get list of ML models (directories ending in '_Timing')
    timing_results_path = Path(timing_results_dir)
    model_dirs = [d.name for d in timing_results_path.iterdir()
                  if d.is_dir() and d.name.endswith('_Timing')]
    model_dirs.sort()

    print(f"Found {len(model_dirs)} ML models: {', '.join(model_dirs)}")
    print(f"Processing {len(df)} tasks...")

    # Initialize new columns
    for model_dir in model_dirs:
        # Extract model name (e.g., 'DT' from 'DT_Timing')
        model_name = model_dir.replace('_Timing', '')
        df[model_name] = None

    # Add single Failure column for all models
    df['Failure'] = 'None'

    # Process each task
    for idx, row in df.iterrows():
        task_id = str(row['task_id'])
        print(f"Processing task {task_id}...")

        task_failures = set()

        for model_dir in model_dirs:
            model_name = model_dir.replace('_Timing', '')

            avg_accuracy, failure = process_task_model(
                timing_results_dir, model_dir, task_id
            )

            df.at[idx, model_name] = avg_accuracy

            # Track failures across all models for this task
            if failure != 'None':
                task_failures.add(failure)

        # Set overall failure status for the task
        # Priority: memory-limit > time-limit > None
        if 'memory-limit' in task_failures:
            df.at[idx, 'Failure'] = 'memory-limit'
        elif 'time-limit' in task_failures:
            df.at[idx, 'Failure'] = 'time-limit'
        else:
            df.at[idx, 'Failure'] = 'None'

    # Filter out tasks with failures (keep only tasks where Failure == 'None')
    df_filtered = df[df['Failure'] == 'None'].copy()

    # Apply threshold filtering if specified
    if threshold is not None:
        print(f"\nApplying threshold filter: removing tasks with any model performance >= {threshold}")
        tasks_to_keep = []
        for idx, row in df_filtered.iterrows():
            exceeds_threshold = False
            for model_dir in model_dirs:
                model_name = model_dir.replace('_Timing', '')
                accuracy = row[model_name]
                if accuracy is not None and accuracy >= threshold:
                    exceeds_threshold = True
                    break
            if not exceeds_threshold:
                tasks_to_keep.append(idx)

        df_filtered = df_filtered.loc[tasks_to_keep].copy()

    # Print test performance for tasks that made it to the final CSV
    print("\n" + "="*60)
    print("Tasks included in final CSV:")
    print("="*60)
    for idx, row in df_filtered.iterrows():
        task_id = str(row['task_id'])
        print(f"\nTask {task_id} Results:")
        for model_dir in model_dirs:
            model_name = model_dir.replace('_Timing', '')
            accuracy = row[model_name]
            if accuracy is not None:
                print(f"  {model_name}: {accuracy:.6f}")
            else:
                print(f"  {model_name}: N/A")

    # Drop the Failure column from the filtered results
    df_filtered = df_filtered.drop(columns=['Failure'])

    print(f"\n" + "="*60)
    print(f"Filtering Summary:")
    print(f"="*60)
    print(f"Total tasks processed: {len(df)}")
    print(f"Tasks in final CSV: {len(df_filtered)}")
    print(f"Tasks excluded: {len(df) - len(df_filtered)}")
    if threshold is not None:
        print(f"  - Threshold filter applied: >= {threshold}")

    # Save the filtered CSV
    if output_path is None:
        output_path = tasks_summary_path

    df_filtered.to_csv(output_path, index=False)
    print(f"\nResults saved to: {output_path}")
    print(f"Added {len(model_dirs)} model columns (Failure column excluded from final output)")


def main():
    parser = argparse.ArgumentParser(
        description='Aggregate ML model results and update tasks_summary.csv'
    )
    parser.add_argument(
        '--tasks-csv',
        type=str,
        default='/Users/hernandezj45/Desktop/Repositories/GECCO-2026-TPEC/Data/Raw_OpenML_Suite_271_Binary_Classification/tasks_summary.csv',
        help='Path to tasks_summary.csv file'
    )
    parser.add_argument(
        '--timing-results',
        type=str,
        default='/Users/hernandezj45/Desktop/Repositories/GECCO-2026-TPEC/Data/Timing_Results',
        help='Path to Timing_Results directory'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Output path for updated CSV (default: overwrites input)'
    )
    parser.add_argument(
        '--threshold',
        type=float,
        default=None,
        help='Threshold to filter out tasks where any model performance >= threshold'
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.tasks_csv):
        print(f"Error: Tasks CSV file not found: {args.tasks_csv}")
        return 1

    if not os.path.exists(args.timing_results):
        print(f"Error: Timing results directory not found: {args.timing_results}")
        return 1

    # Run aggregation
    aggregate_results(args.tasks_csv, args.timing_results, args.output, args.threshold)
    return 0


if __name__ == '__main__':
    exit(main())
