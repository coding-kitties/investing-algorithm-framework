"""
CLI command to validate backtest checkpoints from a directory.

This command scans a directory for backtest results and creates or updates
a checkpoints.json file with all found backtests organized by date ranges.
"""
import json
import os
from typing import Dict, List

import click

from investing_algorithm_framework.domain import Backtest


def validate_and_create_checkpoints(
    directory_path: str,
    output_file: str = None,
    verbose: bool = False
) -> Dict[str, List[str]]:
    """
    Validate a directory for backtest checkpoints and create a checkpoint file.

    Args:
        directory_path (str): Path to the directory containing
            backtest results.
        output_file (str, optional): Custom path for the output
            checkpoint file. If None, will create 'checkpoints.json'
            in the directory_path.
        verbose (bool): Whether to print detailed information.

    Returns:
        Dict[str, List[str]]: Dictionary mapping date range
        keys to algorithm IDs.
    """
    if not os.path.exists(directory_path):
        raise click.ClickException(
            f"Directory {directory_path} does not exist."
        )

    # Determine output file path
    if output_file is None:
        output_file = os.path.join(directory_path, "checkpoints.json")

    checkpoints = {}
    valid_backtests = 0
    invalid_dirs = 0

    if verbose:
        click.echo(f"Scanning directory: {directory_path}")
        click.echo("-" * 60)

    # Scan all subdirectories in the target directory
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)

        # Skip files, only process directories
        if not os.path.isdir(item_path):
            continue

        # Skip the checkpoints.json file itself
        if item == "checkpoints.json":
            continue

        try:
            # Try to load the backtest
            backtest = Backtest.open(item_path)

            if backtest.algorithm_id is None:
                if verbose:
                    click.echo(
                        f"⚠️  Warning: {item} - No "
                        f"algorithm_id found, skipping"
                    )
                invalid_dirs += 1
                continue

            # Process each backtest run to extract date ranges
            if backtest.backtest_runs:
                for run in backtest.get_all_backtest_runs():
                    # Create date range key in the format used by the framework
                    start_date = run.backtest_start_date.isoformat()
                    end_date = run.backtest_end_date.isoformat()
                    date_range_key = f"{start_date}_{end_date}"

                    # Add algorithm_id to the checkpoint for this date range
                    if date_range_key not in checkpoints:
                        checkpoints[date_range_key] = []

                    if backtest.algorithm_id \
                            not in checkpoints[date_range_key]:
                        checkpoints[date_range_key].append(
                            backtest.algorithm_id
                        )

                        if verbose:
                            click.echo(
                                f"✓ {item} - Algorithm: "
                                f"{backtest.algorithm_id}, "
                                f"Range: {start_date} to {end_date}"
                            )

                valid_backtests += 1
            else:
                if verbose:
                    click.echo(
                        f"⚠️  Warning: {item} - No backtest runs found"
                    )
                invalid_dirs += 1

        except Exception as e:
            if verbose:
                click.echo(f"✗ {item} - Not a valid backtest: {str(e)}")
            invalid_dirs += 1
            continue

    # Sort algorithm IDs in each checkpoint for consistency
    for date_range_key in checkpoints:
        checkpoints[date_range_key].sort()

    # Write checkpoint file
    with open(output_file, 'w') as f:
        json.dump(checkpoints, f, indent=4)

    # Print summary
    if verbose:
        click.echo("-" * 60)

    click.echo("\n✓ Checkpoint validation complete!")
    click.echo(f"  Valid backtests found: {valid_backtests}")
    click.echo(f"  Invalid/skipped directories: {invalid_dirs}")
    click.echo(f"  Total date ranges: {len(checkpoints)}")
    click.echo(f"  Checkpoint file saved to: {output_file}\n")

    if verbose and checkpoints:
        click.echo("Date ranges found:")
        for date_range_key, algorithm_ids in sorted(checkpoints.items()):
            click.echo(
                f"  {date_range_key}: {len(algorithm_ids)} algorithm(s)"
            )

    return checkpoints


@click.command()
@click.argument(
    'directory',
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True
)
@click.option(
    '--output',
    '-o',
    type=click.Path(),
    default=None,
    help='Output path for the checkpoint file. '
         'Defaults to checkpoints.json in the target directory.'
)
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    default=False,
    help='Print detailed information about each backtest found.'
)
def command(directory, output, verbose):
    """
    Validate a directory for backtest checkpoints and create/update
    checkpoints.json.

    This command scans DIRECTORY for backtest results, validates
    each subdirectory to check if it contains a valid backtest, and
    creates a checkpoints.json file mapping date ranges to algorithm IDs.

    Example usage:

    \b
        # Validate backtests in a directory
        iaf validate-checkpoints /path/to/backtest/results

    \b
        # With verbose output
        iaf validate-checkpoints /path/to/backtest/results --verbose

    \b
        # Save to a custom location
        iaf validate-checkpoints /path/to/backtest/results -o
        /path/to/checkpoints.json
    """
    try:
        validate_and_create_checkpoints(
            directory_path=directory,
            output_file=output,
            verbose=verbose
        )
    except Exception as e:
        raise click.ClickException(f"Error validating checkpoints: {str(e)}")
