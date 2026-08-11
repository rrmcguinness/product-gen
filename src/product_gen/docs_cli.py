import argparse
import sys
from pathlib import Path
from mkdocs.config import load_config
from mkdocs.commands.build import build as mkdocs_build
from mkdocs.commands.serve import serve as mkdocs_serve


def get_config_file(custom_config: str | None = None) -> str:
    if custom_config:
        return custom_config
    root_dir = Path(__file__).resolve().parent.parent.parent
    config_path = root_dir / "mkdocs.yml"
    return str(config_path)


def serve() -> None:
    """Serve the MkDocs documentation site locally with live reloading."""
    parser = argparse.ArgumentParser(description="Serve the MkDocs documentation site.")
    parser.add_argument(
        "-a", "--dev-addr",
        default="127.0.0.1:8000",
        help="IP address and port to serve documentation locally (default: 127.0.0.1:8000)"
    )
    parser.add_argument(
        "-c", "--config-file",
        default=None,
        help="Path to the mkdocs.yml configuration file"
    )
    parser.add_argument(
        "--no-livereload",
        action="store_true",
        help="Disable live reloading"
    )
    parser.add_argument(
        "--dirty",
        action="store_true",
        help="Build only modified files (faster development)"
    )
    args = parser.parse_args()

    config_file = get_config_file(args.config_file)
    print(f"Loading MkDocs config from: {config_file}")
    mkdocs_serve(
        config_file=config_file,
        dev_addr=args.dev_addr,
        livereload=not args.no_livereload,
        build_type="dirty" if args.dirty else None
    )


def build() -> None:
    """Build the MkDocs documentation site to static HTML files."""
    parser = argparse.ArgumentParser(description="Build the MkDocs documentation site.")
    parser.add_argument(
        "-c", "--config-file",
        default=None,
        help="Path to the mkdocs.yml configuration file"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="Clean the output directory before building (default: True)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Enable strict mode (treat warnings as errors)"
    )
    parser.add_argument(
        "-d", "--site-dir",
        default=None,
        help="The directory to output the generated site into"
    )
    args = parser.parse_args()

    config_file = get_config_file(args.config_file)
    print(f"Building documentation site using config: {config_file}")
    config_kwargs = {}
    if args.site_dir:
        config_kwargs["site_dir"] = args.site_dir
    if args.strict:
        config_kwargs["strict"] = True

    config = load_config(config_file=config_file, **config_kwargs)
    mkdocs_build(config, dirty=not args.clean)
    print("Documentation build completed successfully.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        sys.argv.pop(1)
        build()
    else:
        if len(sys.argv) > 1 and sys.argv[1] == "serve":
            sys.argv.pop(1)
        serve()
