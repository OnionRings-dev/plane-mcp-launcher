#!/usr/bin/env python3
"""Run the official Plane MCP server with a named local connection profile."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.parse import urlsplit

PACKAGE = "plane-mcp-server==0.3.4"
CONFIG_DIR = Path.home() / ".config/plane-mcp"


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(1)


def load_profile(name):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        fail("Profile names must contain only letters, digits, underscores or hyphens.")
    path = CONFIG_DIR / "profiles" / (name + ".json")
    try:
        profile = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        fail("Cannot read profile JSON: " + str(path))
    required = {"base_url", "workspace_slug", "token_file"}
    if not isinstance(profile, dict) or set(profile) != required:
        fail("Profile must contain exactly base_url, workspace_slug and token_file.")
    if any(not isinstance(value, str) or not value or value != value.strip() for value in profile.values()):
        fail("Profile values must be nonempty strings without surrounding whitespace.")
    if any(ord(character) < 32 or ord(character) == 127 for value in profile.values() for character in value):
        fail("Profile values must not contain control characters.")
    try:
        url = urlsplit(profile["base_url"])
        url.port  # Validate malformed or out-of-range ports too.
    except ValueError:
        fail("base_url is not a valid root URL.")
    if (url.scheme not in {"http", "https"} or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or url.path not in {"", "/"}
            or any(character.isspace() for character in profile["base_url"])):
        fail("base_url must be the Plane instance root URL, without credentials or a workspace path.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", profile["workspace_slug"]):
        fail("workspace_slug must be the workspace URL slug, not its display name or URL.")
    try:
        token_file = Path(profile["token_file"]).expanduser()
    except RuntimeError:
        fail("Cannot expand token_file home directory; use an absolute path or ~/.")
    if not token_file.is_absolute():
        fail("token_file must be an absolute path or start with ~/.")
    return profile["base_url"].rstrip("/"), profile["workspace_slug"], token_file


def read_token(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                fail("Token file must be a private regular file owned by you (mode 600): " + str(path))
            if info.st_size > 16384:
                fail("Token file is too large; expected a single access token.")
            token = handle.read(16385).strip()
    except (OSError, UnicodeError):
        fail("Cannot read token file. Run this profile with --set-token.")
    if not valid_token(token):
        fail("Token must contain only visible ASCII characters. Run this profile with --set-token.")
    return token


def valid_token(token):
    return bool(token) and len(token) <= 16384 and all(33 <= ord(character) <= 126 for character in token)


def store_token(path):
    if not sys.stdin.isatty():
        fail("Run --set-token in your own terminal; input will be hidden.")
    token = getpass.getpass("Plane token (hidden): ").strip()
    if not valid_token(token):
        fail("Token must contain only visible ASCII characters; existing file was preserved.")
    temporary = None
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            os.chmod(temporary, 0o600)
            handle.write(token + "\n")
        os.replace(temporary, path)
    except OSError:
        fail("Cannot save token file; check the parent directory and its permissions.")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    print("Token saved with mode 600: " + str(path))


class NoRedirect(HTTPRedirectHandler):
    """Never forward the API key to a redirect destination."""

    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def check_connection(base_url, workspace, token):
    """Make one read-only Plane REST request without printing its payload."""
    request = Request(base_url + "/api/v1/workspaces/" + workspace + "/projects/",
                      headers={"x-api-key": token, "Accept": "application/json",
                               "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                             "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                                             "Version/18.0 Safari/605.1.15"})
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            if response.status != 200 or "application/json" not in response.headers.get("Content-Type", "").lower():
                fail("Unexpected Plane response; check the API root and reverse proxy routing.")
    except HTTPError as error:
        status = error.code
        error.close()
        fail("Plane connection check failed (HTTP " + str(status) + "). Check URL, token and workspace access; redirects are not followed.")
    except (URLError, OSError, ValueError, UnicodeError):
        fail("Cannot reach Plane; check DNS, network/VPN, TLS certificates and the instance URL.")
    print("Plane projects endpoint returned HTTP 200 JSON for this workspace. No changes were made.")


def main():
    if os.name != "posix":
        fail("This launcher requires macOS, Linux or WSL; native Windows is not supported.")
    if sys.version_info < (3, 10):
        fail("Python 3.10 or newer is required. Select a supported Python interpreter.")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", help="Name of ~/.config/plane-mcp/profiles/<name>.json")
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--set-token", action="store_true", help="Store a token using hidden terminal input")
    options.add_argument("--check-profile", action="store_true", help="Validate local config and token; does not authenticate")
    options.add_argument("--check-connection", action="store_true", help="Read the Plane projects endpoint to check URL, token and workspace access")
    args = parser.parse_args()
    base_url, workspace, token_file = load_profile(args.profile)
    if args.set_token:
        store_token(token_file)
        return
    token = read_token(token_file)
    if args.check_profile:
        print("Profile and token file valid; Plane authentication has not been checked.")
        return
    if args.check_connection:
        check_connection(base_url, workspace, token)
        return
    candidates = [shutil.which("uvx"), str(Path.home() / ".local/bin/uvx"),
                  "/opt/homebrew/bin/uvx", "/usr/local/bin/uvx"]
    uvx = next((path for path in candidates if path and os.path.isfile(path) and os.access(path, os.X_OK)), None)
    if uvx is None:
        fail("uvx was not found. Install uv, then restart the MCP client.")
    environment = os.environ.copy()
    # Upstream gives this variable precedence over PLANE_BASE_URL. A profile
    # must remain bound to its own instance even if the parent exports it.
    environment.pop("PLANE_INTERNAL_BASE_URL", None)
    environment.update({"PLANE_API_KEY": token, "PLANE_BASE_URL": base_url,
                        "PLANE_WORKSPACE_SLUG": workspace, "LOG_PAYLOADS": "false", "LOG_USER_INFO": "false"})
    try:
        os.execve(uvx, [uvx, "--no-config", "--no-env-file", "--python", sys.executable,
                       "--from", PACKAGE, "plane-mcp-server", "stdio"], environment)
    except OSError:
        fail("Cannot execute uvx. Check its executable path and permissions.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        fail("Cancelled.")
