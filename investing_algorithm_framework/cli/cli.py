import click

from .deploy_to_aws_lambda import command as deploy_to_aws_lambda_command
from .deploy_to_azure_function import command as \
    deploy_to_azure_function_command
from .initialize_app import command as initialize_app_command
from .validate_backtest_checkpoints import command as \
    validate_backtest_checkpoints_command

"""
CLI for Investing Algorithm Framework

This module provides a command-line interface (CLI) for the
Investing Algorithm Framework.
"""


@click.group()
def cli():
    """CLI for Investing Algorithm Framework"""
    pass


@click.command()
@click.option(
    '--type',
    default="default",
    help="Type of app to create. "
    "Options are: 'default', 'default_web', 'azure_function', 'aws_lambda'."
)
@click.option(
    '--path', default=None, help="Path to directory to initialize the app in"
)
@click.option(
    '--replace',
    is_flag=True,
    default=False,
    help="If True, duplicate files will be replaced."
    "If False, files will not be replaced."
)
def init(type, path, replace):
    """
    Command-line tool for creating an app skeleton.

    Args:
        type (str): Type of app to create. Options are: 'default',
            'default-web', 'azure-function'.
        path (str): Path to directory to initialize the app in
        replace (bool): If True, existing files will be replaced.
            If False, existing files will not be replaced.

    Returns:
        None
    """
    initialize_app_command(path=path, app_type=type, replace=replace)


@click.command()
@click.option(
    '--resource_group',
    required=True,
    help='The name of the resource group.',
)
@click.option(
    '--subscription_id',
    required=False,
    help='The subscription ID. If not provided, the default will be used.'
)
@click.option(
    '--storage_account_name',
    required=False,
    help='The name of the storage account.',
)
@click.option(
    '--container_name',
    required=False,
    help='The name of the blob container.',
    default='iafcontainer'
)
@click.option(
    '--deployment_name',
    required=True,
    help='The name of the deployment. This will be" + \
        "used as the name of the Function App.'
)
@click.option(
    '--region',
    required=True,
    help='The Azure region for the resources.'
)
@click.option(
    '--create_resource_group_if_not_exists',
    is_flag=True,
    help='Flag to create the resource group if it does not exist.'
)
@click.option(
    '--skip_login',
    is_flag=True,
    help='Flag to create the resource group if it does not exist.',
    default=False
)
def deploy_azure_function(
    resource_group,
    subscription_id,
    storage_account_name,
    container_name,
    deployment_name,
    region,
    create_resource_group_if_not_exists,
    skip_login
):
    """
    Command-line tool for deploying a trading bot to Azure Function.

    Args:
        path (str): Path to directory to initialize the app in
        resource_group (str): The name of the resource group.
        subscription_id (str): The subscription ID. If not provided,
            the default will be used.
        storage_account_name (str): The name of the storage account.
        container_name (str): The name of the blob container.
        deployment_name (str): The name of the deployment. This will be
            used as the name of the Function App.
        region (str): The Azure region for the resources.
        create_resource_group_if_not_exists (bool): Flag to create the
            resource group if it does not exist.
        skip_login (bool): Flag to skip the login process. This is
            useful for CI/CD pipelines where the login is handled
            separately.
        region (str): The Azure region for the resources.
        create_resource_group_if_not_exists (bool): Flag to create the
            resource group if it does not exist.
        skip_login (bool): Flag to skip the login process. This is
            useful for CI/CD pipelines where the login is handled
            separately.

    Returns:
        None
    """
    crg = create_resource_group_if_not_exists
    deploy_to_azure_function_command(
        resource_group=resource_group,
        subscription_id=subscription_id,
        storage_account_name=storage_account_name,
        container_name=container_name,
        deployment_name=deployment_name,
        region=region,
        create_resource_group_if_not_exists=crg,
        skip_login=skip_login
    )


@click.command()
@click.option(
    '--lambda_function_name',
    required=True,
    help='The name of the AWS Lambda function to deploy.'
)
@click.option(
    '--region',
    required=True,
    help='The AWS region where the Lambda function will be deployed.'
)
@click.option(
    '--project_dir',
    default=None,
    help='The path to the project directory containing '
         'the Lambda function code.'
)
@click.option(
    '--memory_size',
    default=3000,
    type=int,
    help='The memory size for the Lambda function in MB. Default is 3000 MB.'
)
@click.option(
    '--env',
    '-e',
    multiple=True,
    nargs=2,
    type=str,
    help='Environment variables to pass to the Lambda function. '
         'Can be used multiple times: -e KEY VALUE -e KEY2 VALUE2'
)
def deploy_aws_lambda(
    lambda_function_name,
    region,
    project_dir=None,
    memory_size=3000,
    env=None
):
    """
    Command-line tool for deploying a trading bot to AWS lambda

    Args:
        lambda_function_name (str): The name of the AWS Lambda function
            to deploy.
        region (str): The AWS region where the Lambda function will
            be deployed.
        project_dir (str): The path to the project directory containing the
            Lambda function code. If not provided, it defaults to
            the current directory.
        memory_size (int): The memory size for the Lambda function in MB.
            Default is 3000 MB.
        env (tuple): Environment variables as tuples of (KEY, VALUE).
            Can be specified multiple times.

    Returns:
        None
    """
    # Convert env tuples to dictionary
    env_vars = {}
    if env:
        for key, value in env:
            env_vars[key] = value

    deploy_to_aws_lambda_command(
        lambda_function_name=lambda_function_name,
        region=region,
        project_dir=project_dir,
        memory_size=memory_size,
        env_vars=env_vars
    )


cli.add_command(init)
cli.add_command(deploy_azure_function)
cli.add_command(deploy_aws_lambda)
cli.add_command(
    validate_backtest_checkpoints_command, name="validate-checkpoints"
)


@click.command()
@click.option(
    '--directory', '-d',
    required=True,
    multiple=True,
    help='Path to a backtest batch directory (can be repeated)'
)
def mcp(directory):
    """Start the MCP server for AI-powered backtest analysis.

    This lets GitHub Copilot, Claude, and other LLMs query your
    backtest data directly in VS Code.
    """
    from .mcp_server import main as mcp_main
    dirs = list(directory)
    mcp_main(directory=dirs if len(dirs) > 1 else dirs[0])


cli.add_command(mcp)


@click.command(name="migrate-backtests")
@click.option(
    "--src", "-s",
    required=True,
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    help="Source directory containing legacy backtest sub-directories.",
)
@click.option(
    "--dst", "-d",
    required=True,
    type=click.Path(file_okay=False, dir_okay=True),
    help="Destination directory for the new ``.iafbt`` bundle files.",
)
@click.option(
    "--workers", "-w", type=int, default=None,
    help="Number of parallel workers (default: min(8, CPU count)).",
)
@click.option(
    "--no-index", is_flag=True, default=False,
    help="Skip writing index.parquet at the destination.",
)
@click.option(
    "--include-ohlcv", is_flag=True, default=False,
    help="Include OHLCV data in the destination bundles.",
)
@click.option(
    "--no-skip-existing", is_flag=True, default=False,
    help="Re-migrate even if the destination bundle already exists.",
)
@click.option(
    "--delete-source", is_flag=True, default=False,
    help=(
        "Delete each source directory/bundle after its destination "
        "has been written successfully. Use with care."
    ),
)
def migrate_backtests_cmd(
    src, dst, workers, no_index, include_ohlcv, no_skip_existing,
    delete_source,
):
    """Convert a directory of legacy backtest folders into the bundled
    binary format introduced in issue #487.

    The new ``.iafbt`` format is a single zstd-compressed MessagePack
    file per backtest. Loading bundled directories is dramatically
    faster than the legacy multi-file layout for large batches.

    Migration is streamed (load+save fused per worker) so memory
    usage stays roughly constant regardless of source size, and
    interrupted runs can be resumed (existing destination bundles
    are skipped by default).
    """
    from investing_algorithm_framework.domain import migrate_backtests

    n = migrate_backtests(
        src,
        dst,
        workers=workers,
        show_progress=True,
        write_index=not no_index,
        include_ohlcv=include_ohlcv,
        skip_existing=not no_skip_existing,
        delete_source=delete_source,
    )
    click.echo(f"Migrated {n} backtest(s) from {src} to {dst}")


cli.add_command(migrate_backtests_cmd)


_STORE_KINDS = ["local-dir", "local-tiered"]


@click.command(name="migrate-store")
@click.option(
    "--from", "src_kind",
    type=click.Choice(_STORE_KINDS),
    required=True,
    help="Source store kind.",
)
@click.option(
    "--src",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help="Path to the source store root.",
)
@click.option(
    "--to", "dst_kind",
    type=click.Choice(_STORE_KINDS),
    required=True,
    help="Destination store kind.",
)
@click.option(
    "--dst",
    type=click.Path(file_okay=False, dir_okay=True),
    required=True,
    help="Path to the destination store root (created if missing).",
)
@click.option(
    "--handles",
    default=None,
    help=(
        "Optional comma-separated subset of source handles to copy. "
        "When omitted, every handle is copied."
    ),
)
def migrate_store_cmd(src_kind, src, dst_kind, dst, handles):
    """Copy backtests between two :class:`BacktestStore` implementations.

    Uses the destination's :class:`SupportsCopyFrom` capability so the
    operation is incremental, restartable, and tier-aware: when copying
    into a ``local-tiered`` store, identical OHLCV chunks are written
    exactly once across the entire destination, regardless of how many
    bundles reference them (epic #540 phase 3c).

    Example::

        iaf migrate-store --from local-dir --src ./bt-old \\
                          --to local-tiered --dst ./bt-new
    """
    from .migrate_store_command import migrate_store

    handle_list = (
        [h.strip() for h in handles.split(",") if h.strip()]
        if handles else None
    )
    n = migrate_store(
        src_kind=src_kind,
        src_root=src,
        dst_kind=dst_kind,
        dst_root=dst,
        handles=handle_list,
    )
    click.echo(
        f"Migrated {n} backtest(s) from {src_kind}:{src} "
        f"to {dst_kind}:{dst}"
    )


cli.add_command(migrate_store_cmd)


@click.command(name="index")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--output", "-o",
    type=click.Path(file_okay=True, dir_okay=False),
    default=None,
    help="Path to the SQLite index file (default: <directory>/index.sqlite).",
)
@click.option(
    "--absolute-paths", is_flag=True, default=False,
    help="Store absolute bundle paths in the index "
         "(default: paths relative to <directory>, so the index stays "
         "portable when the folder is moved).",
)
@click.option(
    "--no-progress", is_flag=True, default=False,
    help="Suppress the progress bar.",
)
@click.option(
    "--rebuild", is_flag=True, default=False,
    help="Force a full rebuild instead of incremental refresh "
         "(default: skip bundles whose mtime+size match an existing "
         "row).",
)
def index_cmd(directory, output, absolute_paths, no_progress, rebuild):
    """Build a SQLite Tier-1 index over a folder of ``.iafbt`` bundles.

    The resulting ``index.sqlite`` file holds one row per bundle with
    identity / provenance / config columns and every scalar
    ``BacktestSummaryMetrics`` field promoted to its own column, so
    analysts can run ad-hoc SQL queries (e.g.
    ``SELECT bundle_path FROM backtest_index
    WHERE summary_sharpe_ratio > 1.0``) without opening any bundle.

    Each bundle is opened with ``summary_only=True`` so no Parquet
    metric blobs are decoded \u2014 indexing 12,500 bundles is bounded by
    msgpack header parsing, not metric reconstruction.
    """
    from .index_command import build_index

    out = build_index(
        directory=directory,
        output=output,
        relative_paths=not absolute_paths,
        show_progress=not no_progress,
        incremental=not rebuild,
    )
    click.echo(f"Wrote SQLite index to {out}")


cli.add_command(index_cmd)


@click.command(name="list")
@click.argument(
    "index_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
)
@click.option(
    "--sort", "sort_by", default=None,
    help="Metric / column to sort by (e.g. sharpe_ratio, "
         "summary_total_net_gain_percentage, algorithm_id). "
         "Bare metric names are auto-prefixed with 'summary_'.",
)
@click.option(
    "--asc", "ascending", is_flag=True, default=False,
    help="Sort ascending (default: descending / best-first).",
)
@click.option(
    "--limit", "-n", type=int, default=None,
    help="Maximum number of rows to print.",
)
@click.option(
    "--where", default=None,
    help='Raw SQL WHERE fragment (no leading WHERE). '
         'Example: --where "summary_sharpe_ratio > 1.0 AND tag = \'demo\'"',
)
@click.option(
    "--columns", default=None,
    help="Comma-separated list of columns to print "
         "(default: a curated set of identity + summary metrics).",
)
@click.option(
    "--json", "as_json", is_flag=True, default=False,
    help="Emit JSON instead of a text table.",
)
def list_cmd(
    index_path, sort_by, ascending, limit, where, columns, as_json,
):
    """List rows from a SQLite Tier-1 index built by ``iaf index``.

    ``INDEX_PATH`` may be either an ``index.sqlite`` file or the
    directory it lives in.

    Examples:

        iaf list ./backtests --sort sharpe_ratio -n 20

        iaf list index.sqlite --where "summary_max_drawdown > -0.1" \\
            --sort sortino_ratio
    """
    from .index_command import list_index, format_table
    cols = (
        [c.strip() for c in columns.split(",")] if columns else None
    )
    rows = list_index(
        index_path=index_path,
        sort_by=sort_by,
        ascending=ascending,
        limit=limit,
        where=where,
        columns=cols,
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps(rows, indent=2, default=str))
    else:
        click.echo(format_table(rows, columns=cols))


cli.add_command(list_cmd)


@click.command(name="rank")
@click.argument(
    "index_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=True),
)
@click.option(
    "--by", "by", required=True,
    help="Metric to rank by (e.g. sharpe_ratio, sortino_ratio, "
         "calmar_ratio, profit_factor). Bare metric names are "
         "auto-prefixed with 'summary_'.",
)
@click.option(
    "--limit", "-n", type=int, default=10,
    help="Number of rows to return (default: 10).",
)
@click.option(
    "--asc", "ascending", is_flag=True, default=False,
    help="Rank ascending (e.g. for max_drawdown where smaller is "
         "better the user typically wants ascending order on the "
         "magnitude). Default: descending / best-first.",
)
@click.option(
    "--where", default=None,
    help='Optional SQL WHERE fragment to filter candidates before '
         'ranking. Example: --where "tag = \'walk-forward\'".',
)
@click.option(
    "--columns", default=None,
    help="Comma-separated list of columns to print "
         "(default: identity + key risk-adjusted metrics).",
)
@click.option(
    "--json", "as_json", is_flag=True, default=False,
    help="Emit JSON instead of a text table.",
)
@click.option(
    "--prune", is_flag=True, default=False,
    help="Remove bundles that fall outside the ranked results. "
         "Combine with --archive-dir to move instead of delete.",
)
@click.option(
    "--archive-dir", "archive_dir", default=None,
    type=click.Path(file_okay=False),
    help="Move pruned bundles here instead of deleting them. "
         "Implies --prune.",
)
@click.option(
    "--dry-run", is_flag=True, default=False,
    help="Show what --prune would do without touching files.",
)
def rank_cmd(index_path, by, limit, ascending, where, columns, as_json,
             prune, archive_dir, dry_run):
    """Rank backtests in a Tier-1 index by a single metric.

    Sugar over ``iaf list --sort <by> --limit <n>`` with a column set
    geared toward strategy comparison (Sharpe / Sortino / Calmar /
    return / drawdown).

    Examples:

        iaf rank ./backtests --by sharpe_ratio -n 5

        iaf rank index.sqlite --by profit_factor \\
            --where "summary_number_of_trades > 50"
    """
    from .index_command import rank_index, format_table
    cols = (
        [c.strip() for c in columns.split(",")] if columns else None
    )
    rows = rank_index(
        index_path=index_path,
        by=by,
        limit=limit,
        where=where,
        columns=cols,
        ascending=ascending,
    )
    if as_json:
        import json as _json
        click.echo(_json.dumps(rows, indent=2, default=str))
    else:
        click.echo(format_table(rows, columns=cols))

    if prune or archive_dir:
        from .index_command import prune_backtests
        result = prune_backtests(
            directory=index_path,
            keep=rows,
            archive_dir=archive_dir,
            dry_run=dry_run,
            show_progress=True,
        )
        action = "Would prune" if dry_run else "Pruned"
        dest = (
            f" → {result['archive_dir']}" if result["archive_dir"]
            else " (deleted)"
        )
        click.echo(
            f"\n{action} {result['pruned']} bundle(s){dest}, "
            f"kept {result['kept']}."
        )


cli.add_command(rank_cmd)
