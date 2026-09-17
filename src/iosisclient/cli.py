from __future__ import annotations

import argparse
import sys
from pathlib import Path

from iosisclient.config import load_config


def _add_mode_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["local", "cloud"],
        help="Execution mode (default: from config)",
    )


def _add_yaml_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("yaml", help="Path to strategy YAML file")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="iosis",
        description="Iosis strategy CLI",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to config file (default: platform config dir)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init
    init_p = sub.add_parser("init", help="Store API key in config")
    init_p.add_argument("api_key", help="Iosis API key")

    # run
    run_p = sub.add_parser("run", help="Execute a strategy")
    run_sub = run_p.add_subparsers(dest="run_mode", required=True)

    run_local = run_sub.add_parser("local", help="Execute locally via iosislib")
    _add_yaml_arg(run_local)
    run_local.add_argument("-o", "--output", help="Write result to parquet file")
    run_local.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Cache directory or S3 URI (e.g. s3://bucket/cache)",
    )
    run_local.add_argument(
        "--no-cache",
        action="store_true",
        default=False,
        help="Disable node caching for this run",
    )

    run_cloud = run_sub.add_parser("cloud", help="Submit to Iosis Cloud")
    _add_yaml_arg(run_cloud)
    run_cloud.add_argument("-d", "--output-dir", help="Download artifacts to directory")

    # validate
    val_p = sub.add_parser("validate", help="Validate a strategy YAML")
    _add_yaml_arg(val_p)

    # catalog
    cat_p = sub.add_parser("catalog", help="List available TSFNs/operations")
    _add_mode_arg(cat_p)

    # datasets
    sub.add_parser("datasets", help="List cloud datasets")

    # credits
    sub.add_parser("credits", help="Show remaining credits")

    # status
    stat_p = sub.add_parser("status", help="Check cloud run status")
    stat_p.add_argument("run_id", help="Run ID to check")

    # render
    rend_p = sub.add_parser("render", help="Render strategy graph as SVG (cloud)")
    _add_yaml_arg(rend_p)
    rend_p.add_argument("-o", "--output", help="Write SVG to file")

    # cache
    cache_p = sub.add_parser("cache", help="Manage the local node cache")
    cache_sub = cache_p.add_subparsers(dest="cache_action", required=True)
    cache_sub.add_parser("info", help="Show cache directory and entry count")
    cache_sub.add_parser("clear", help="Delete all cache entries")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(getattr(args, "config", None))

    if args.command == "init":
        from iosisclient.commands.init import init
        return init(args, config)

    if args.command == "run":
        if args.run_mode == "local":
            from iosisclient.commands.run import run_local
            return run_local(args, config)
        from iosisclient.commands.run import run_cloud
        return run_cloud(args, config)

    if args.command == "validate":
        from iosisclient.commands.validate import validate
        return validate(args, config)

    if args.command == "catalog":
        from iosisclient.commands.catalog import catalog
        return catalog(args, config)

    if args.command == "datasets":
        from iosisclient.commands.datasets import datasets
        return datasets(args, config)

    if args.command == "credits":
        from iosisclient.commands.credits import credits
        return credits(args, config)

    if args.command == "status":
        from iosisclient.commands.status import status
        return status(args, config)

    if args.command == "render":
        from iosisclient.commands.render import render
        return render(args, config)

    if args.command == "cache":
        from iosisclient.commands.cache import cache
        return cache(args, config)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
