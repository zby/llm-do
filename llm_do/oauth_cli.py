"""OAuth CLI for managing credentials.

Usage:
    llm-do-oauth login [--provider anthropic] [--open-browser]
    llm-do-oauth logout [--provider anthropic]
    llm-do-oauth status [--provider anthropic]
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser

from .oauth import (
    get_oauth_path,
    has_oauth_credentials,
    login_anthropic,
    load_oauth_credentials,
    remove_oauth_credentials,
)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse arguments for 'llm-do-oauth' command."""
    parser = argparse.ArgumentParser(
        prog="llm-do-oauth",
        description="Manage OAuth credentials for LLM providers",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login", help="Login with OAuth provider")
    login_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic"],
        help="OAuth provider to use (default: anthropic)",
    )
    login_parser.add_argument(
        "--open-browser",
        action="store_true",
        default=False,
        help="Attempt to open the authorization URL in a browser",
    )

    logout_parser = subparsers.add_parser("logout", help="Logout and clear OAuth credentials")
    logout_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic"],
        help="OAuth provider to clear (default: anthropic)",
    )

    status_parser = subparsers.add_parser("status", help="Show OAuth login status")
    status_parser.add_argument(
        "--provider",
        default="anthropic",
        choices=["anthropic"],
        help="OAuth provider to check (default: anthropic)",
    )

    return parser.parse_args(argv)


async def run_oauth_cli(argv: list[str]) -> int:
    """Handle the OAuth CLI entrypoint."""
    args = _parse_args(argv)

    if args.command == "login":
        if args.provider != "anthropic":
            print(f"Unsupported OAuth provider: {args.provider}", file=sys.stderr)
            return 2

        def on_auth_url(url: str) -> None:
            print("Open this URL in your browser to authorize:")
            print(url)
            if args.open_browser:
                webbrowser.open(url)

        async def on_prompt_code() -> str:
            return input("Paste the authorization code (format: code#state): ").strip()

        try:
            await login_anthropic(on_auth_url, on_prompt_code)
        except Exception as exc:
            print(f"OAuth login failed: {exc}", file=sys.stderr)
            return 1

        print(f"Saved OAuth credentials to {get_oauth_path()}")
        return 0

    if args.command == "logout":
        if args.provider != "anthropic":
            print(f"Unsupported OAuth provider: {args.provider}", file=sys.stderr)
            return 2
        if not has_oauth_credentials(args.provider):
            print(f"No OAuth credentials found for {args.provider}")
            return 0
        remove_oauth_credentials(args.provider)
        print(f"Cleared OAuth credentials for {args.provider}")
        return 0

    if args.command == "status":
        if args.provider != "anthropic":
            print(f"Unsupported OAuth provider: {args.provider}", file=sys.stderr)
            return 2
        credentials = load_oauth_credentials(args.provider)
        if not credentials:
            status = "not logged in"
        elif credentials.is_expired():
            status = "expired"
        else:
            status = "logged in"
        print(f"{args.provider}: {status}")
        return 0

    print(f"Unknown OAuth command: {args.command}", file=sys.stderr)
    return 2


def main() -> int:
    """Entry point for the llm-do-oauth command."""
    return asyncio.run(run_oauth_cli(sys.argv[1:]))


if __name__ == "__main__":
    raise SystemExit(main())
