import os

import click

from .deploy_to_aws_lambda import command as deploy_to_aws_lambda_command
from .deploy_to_azure_function import command as \
    deploy_to_azure_function_command
from .initialize_app import command as initialize_app_command
from .validate_backtest_checkpoints import command as \
    validate_backtest_checkpoints_command
from investing_algorithm_framework.domain.backtesting import backtest_utils

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


# ---------------------------------------------------------------------------
# `iaf migrate-bundles --to v3 <dir>` — in-place format upgrade (v9.0)
# ---------------------------------------------------------------------------


@click.command(name="migrate-bundles")
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--to",
    "target_version",
    required=True,
    type=click.Choice(["v3", "v4"]),
    help=(
        "Target bundle format version. The current writer always "
        "emits v4 (a superset of v3); ``--to v3`` is preserved as a "
        "legacy alias and produces v4 bundles too."
    ),
)
@click.option(
    "--workers", "-w", type=int, default=None,
    help="Number of parallel workers (default: min(8, CPU count)).",
)
@click.option(
    "--keep-source", is_flag=True, default=False,
    help=(
        "Keep legacy source directories after they have been "
        "rewritten as ``.iafbt`` bundles. By default the legacy "
        "directory is removed once the bundle is on disk."
    ),
)
@click.option(
    "--no-index", is_flag=True, default=False,
    help="Skip writing index.parquet at the destination.",
)
@click.option(
    "--dry-run", is_flag=True, default=False,
    help="List the bundles/directories that would be upgraded and exit.",
)
def migrate_bundles_cmd(
    directory, target_version, workers, keep_source, no_index, dry_run,
):
    """Upgrade bundles in DIRECTORY to the v9.0 ``.iafbt`` format **in place**.

    Walks DIRECTORY and rewrites:

    \b
    * ``.iafbt`` bundles in older v1/v2 envelopes → v3 envelope.
    * Legacy backtest directories (``algorithm_id.json`` + ``runs/``
      or per-engine ``vector_runs/`` / ``event_runs/``) → ``.iafbt``
      bundles.

    Bundles already at the target version are skipped via a cheap
    8-byte header read (no Parquet decoded), so the command is safe
    to re-run.

    Each write is atomic (tmp file + fsync + os.replace), so an
    interrupted run leaves the source intact.

    Example::

        iaf migrate-bundles --to v3 ./backtest_results
    """
    from investing_algorithm_framework.domain.backtesting.bundle import (
        BUNDLE_EXT, BUNDLE_FORMAT_VERSION, peek_bundle_format_version,
    )
    target_int = {"v3": 3, "v4": 4}[target_version]
    if target_int > BUNDLE_FORMAT_VERSION:
        # The writer can only emit the version it was compiled
        # against; refuse to forge a higher target.
        raise click.ClickException(
            f"Writer currently targets v{BUNDLE_FORMAT_VERSION} only; "
            f"cannot migrate to {target_version}."
        )
    # ``target_int`` doubles as the discovery filter (skip bundles
    # whose header already meets it). The writer emits
    # ``BUNDLE_FORMAT_VERSION`` regardless — passing ``--to v3`` to a
    # v9.0+ binary therefore still yields v4 on disk.

    # ----- discovery + filter ------------------------------------------------
    bundles_to_upgrade: list[str] = []
    legacy_dirs: list[str] = []
    skipped_current = 0

    for root, dirs, files in os.walk(directory):
        for fname in files:
            if not fname.endswith(BUNDLE_EXT):
                continue
            path = os.path.join(root, fname)
            ver = peek_bundle_format_version(path)
            if ver is None:
                # Unreadable / not actually a bundle — leave alone.
                continue
            if ver >= target_int:
                skipped_current += 1
                continue
            bundles_to_upgrade.append(path)
        for dname in list(dirs):
            d = os.path.join(root, dname)
            has_id = os.path.isfile(os.path.join(d, "algorithm_id.json"))
            has_runs = (
                os.path.isdir(os.path.join(d, "runs"))
                or os.path.isdir(os.path.join(d, "vector_runs"))
                or os.path.isdir(os.path.join(d, "event_runs"))
            )
            if has_id and has_runs:
                legacy_dirs.append(d)
                dirs.remove(dname)

    todo = bundles_to_upgrade + legacy_dirs
    if not todo:
        click.echo(
            f"No upgrades needed in {directory} "
            f"({skipped_current} bundle(s) already at v{target_int})."
        )
        return

    if dry_run:
        click.echo(
            (
                f"Would upgrade {len(todo)} item(s) in {directory} "
                f"(skipping {skipped_current} already at v{target_int}):"
            )
        )
        for p in bundles_to_upgrade:
            click.echo(f"  bundle  {p}")
        for p in legacy_dirs:
            click.echo(f"  legacy  {p}")
        return

    # ----- in-place rewrite --------------------------------------------------
    # ``migrate_backtests`` with src_dir == dst_dir handles both the
    # bundle rewrite (atomic tmp+replace inside ``save_bundle``) and
    # the legacy directory → bundle conversion. ``skip_existing=False``
    # is required so already-named ``.iafbt`` targets get rewritten in
    # place; we have already filtered out same-version bundles above
    # so this re-encodes only what needs upgrading.
    #
    # Note: we cannot pre-filter which paths ``migrate_backtests``
    # discovers, so it will still find the already-current bundles
    # and re-encode them. To honour the cheap-skip filter, hide them
    # from discovery by temporarily renaming, OR call ``_migrate_one``
    # directly. The latter is cleaner — do that.
    from concurrent.futures import ProcessPoolExecutor
    from investing_algorithm_framework.domain import tqdm

    plan = []
    for src in todo:
        base = os.path.basename(os.path.normpath(src))
        if base.endswith(BUNDLE_EXT):
            base = base[: -len(BUNDLE_EXT)]
        dst = os.path.join(directory, f"{base}{BUNDLE_EXT}")
        # delete_source=True only meaningful for legacy dirs; for
        # bundles src == dst and ``_migrate_one`` no-ops the delete.
        delete = (not keep_source) and (os.path.isdir(src))
        plan.append((src, dst, False, None, delete))

    resolved_workers = workers or min(8, (os.cpu_count() or 1))
    resolved_workers = min(resolved_workers, len(plan))

    rows = []
    pbar = tqdm(
        total=len(plan),
        desc=f"Upgrading to v{target_int}",
        disable=False,
    )
    try:
        if resolved_workers > 1:
            with ProcessPoolExecutor(max_workers=resolved_workers) as ex:
                for out, new_rows in ex.map(backtest_utils._migrate_one, plan):
                    rows.extend(new_rows)
                    pbar.update(1)
        else:
            for args in plan:
                out, new_rows = backtest_utils._migrate_one(args)
                rows.extend(new_rows)
                pbar.update(1)
    finally:
        pbar.close()

    if not no_index:
        # Refresh the SQLite index so subsequent ``iaf list``/``rank``
        # reflect the upgraded engine layout.
        try:
            from investing_algorithm_framework.cli.index_command import (
                build_index,
            )
            build_index(str(directory), show_progress=False, incremental=False)
        except Exception as exc:  # pragma: no cover - best effort
            click.echo(
                f"Warning: index refresh failed ({exc}); "
                f"run `iaf index {directory}` manually.",
                err=True,
            )

    click.echo(
        f"Upgraded {len(plan)} item(s) to v{target_int} in {directory} "
        f"(skipped {skipped_current} already current)."
    )


cli.add_command(migrate_bundles_cmd)


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
@click.option(
    "--engine",
    type=click.Choice(["vector", "event"]),
    default=None,
    help="Restrict to a single engine slot. v9.0 dual-engine "
         "bundles index one row per engine; pass \"vector\" or "
         "\"event\" to scope the listing.",
)
def list_cmd(
    index_path, sort_by, ascending, limit, where, columns, as_json,
    engine,
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
        engine=engine,
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
@click.option(
    "--engine",
    type=click.Choice(["vector", "event"]),
    default=None,
    help="Restrict ranking to a single engine slot. v9.0 dual-"
         "engine bundles produce one index row per engine; pass "
         "\"vector\" or \"event\" to produce engine-specific "
         "rankings. Call twice (once per engine) for parallel "
         "vector/event leaderboards.",
)
def rank_cmd(index_path, by, limit, ascending, where, columns, as_json,
             prune, archive_dir, dry_run, engine):
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
        engine=engine,
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
