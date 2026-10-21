# Plane MCP Launcher

A small, independent **launcher for the official [Plane MCP server](https://github.com/makeplane/plane-mcp-server)**, for people connecting AI clients to self-hosted Plane. It keeps named connection profiles and access tokens outside your repositories and client configuration.

The launcher starts `plane-mcp-server==0.3.4` as a local **stdio subprocess**. The official server provides the MCP tools and calls your Plane REST API. This repository contains the launcher, documentation and tests; it does not implement Plane tools or bundle the official server. It is not affiliated with or endorsed by Plane. See [attribution](NOTICE.md) and [MIT license](LICENSE).

```text
Codex / Claude → local launcher → official Plane MCP server → your Plane API
                 profile + token       stdio                   HTTPS
```

The client starts a process for each connection. You do not need a shared daemon, public MCP port, VPS or container. Deploying a remote MCP service is outside this project's scope.

## Prerequisites and compatibility

- **macOS or Linux**, or **WSL for CLI clients**. Native Windows is not supported: the launcher relies on POSIX file ownership, permissions and process replacement. A native Windows Claude Desktop process cannot directly use these WSL paths.
- **Python 3.10+** for the launcher and official server. Check `python3 --version`; on macOS `/usr/bin/python3` may be too old. Use the Python you installed, including its absolute path in GUI client configuration.
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**, which provides `uvx`. The launcher uses `--no-config` and `--no-env-file`; use a current uv release supporting these options.
- An existing Plane instance reachable from the computer running the client, its **root API URL**, a **workspace slug**, and your own **Plane personal access/API token** with access to that workspace.
- A client that can launch local stdio MCP servers: Codex, Claude Code, or Claude Desktop on macOS as documented below.
- Internet access for the first package installation. Later launches reuse uv's cache but are not guaranteed to work offline if dependencies or the selected Python environment are missing. Calls to Plane always need access to your instance.

On macOS with Homebrew:

```sh
brew install python uv
python3 --version
uvx --version
command -v python3
command -v uvx
```

On Linux or WSL, install Python 3.10+ using your distribution and uv using its official installation guide. The launcher itself uses only Python's standard library.

The official server declares Python `>=3.10`; the launcher pins **server version 0.3.4**, not a specific Plane application release or every dependency. Tools and actions depend on your Plane release, edition and account permissions. There is no universal compatibility guarantee for older installations. Validate read operations against your own instance before using write actions. This repository's CI checks the launcher on Python 3.10, 3.12 and 3.14 on macOS and Linux; it does not test every Plane release.

## Install

For guided setup by a local coding agent, give it [INSTALL.md](INSTALL.md) and ask:

> Follow INSTALL.md to install Plane MCP Launcher, guide me through creating my
> token, configure my MCP client, and verify the connection. Never ask me to paste
> the token into chat.

The guide works before cloning and covers prerequisites, private profiles, token
entry in your own terminal, and client registration. For manual setup, continue
below.

Download or clone this repository, then run these commands from its directory:

```sh
mkdir -p "$HOME/.local/bin"
install -m 700 plane-mcp.py "$HOME/.local/bin/plane-mcp"
python3 "$HOME/.local/bin/plane-mcp" --help
```

Prefetch the pinned official package with the same Python interpreter used for the launcher:

```sh
uvx --no-config --no-env-file --python "$(command -v python3)" \
  --from plane-mcp-server==0.3.4 \
  python -c 'from importlib.metadata import version; print(version("plane-mcp-server"))'
```

Expected version: `0.3.4`. This installs dependencies in uv's tool cache and checks package availability; it does **not** authenticate to Plane. A Python virtual environment for the launcher is unnecessary. Keep the chosen Python installation available: the launcher passes its own interpreter path to uvx.

## Profiles: multiple instances and workspaces

Each connection targets **one Plane instance and one workspace**. Projects are selected in tool calls, so a connection covers the projects your account can access in that workspace. Add a profile and client entry for each additional workspace, even on the same instance.

| Local profile | Instance root URL | Workspace slug | Client server name |
| --- | --- | --- | --- |
| `work-a` | `https://plane.example.com` | `team-a` | `plane-work-a` |
| `work-b` | `https://plane.example.com` | `team-b` | `plane-work-b` |
| `lab` | `https://tasks.example.net` | `lab` | `plane-lab` |

All names and addresses here are fictional examples. Profile names contain letters, digits, underscores and hyphens, beginning with a letter or digit. They are local labels, not Plane identifiers.

Create private directories and copy the example profiles:

```sh
mkdir -p "$HOME/.config/plane-mcp/profiles" "$HOME/.config/plane-mcp/tokens"
chmod 700 "$HOME/.config/plane-mcp" "$HOME/.config/plane-mcp/profiles" "$HOME/.config/plane-mcp/tokens"
cp examples/work-a.profile.example.json "$HOME/.config/plane-mcp/profiles/work-a.json"
cp examples/work-b.profile.example.json "$HOME/.config/plane-mcp/profiles/work-b.json"
cp examples/lab.profile.example.json "$HOME/.config/plane-mcp/profiles/lab.json"
chmod 600 "$HOME/.config/plane-mcp/profiles/"*.json
```

Edit the copied files outside this repository. For example, `~/.config/plane-mcp/profiles/work-a.json`:

```json
{
  "base_url": "https://plane.example.com",
  "workspace_slug": "team-a",
  "token_file": "~/.config/plane-mcp/tokens/work.token"
}
```

The profile must contain exactly these three fields, with nonempty string values:

- `base_url`: the Plane **instance root URL**. Do not append `/api/v1`, a workspace or a project path. Credentials, query strings and fragments are rejected. Installations that expose the API only under a custom URL prefix are not supported by this launcher. Use HTTPS over a network; plain HTTP sends the token unencrypted and is intended only for trusted local development.
- `workspace_slug`: the workspace's URL slug, which can differ from its display name or UUID. In `https://plane.example.com/team-a/`, it is `team-a`.
- `token_file`: an absolute path or a path starting with `~/`. Shell variables such as `$HOME` are not expanded in JSON. The file must be a regular file owned by the current user, with no group/other permissions. Symlinks are rejected.

Profiles on the same instance may share a token file when the token grants access to both workspaces. Use a separate token file for another instance or account. A workspace-scoped token may need a different file for each workspace.

The configuration location is fixed at `~/.config/plane-mcp`, including on macOS; `XDG_CONFIG_HOME` is not used.

## Store your token

Create a token in your Plane account settings. Menu names vary by release; current Plane documentation describes **Profile Settings → Personal Access Tokens**, and workspace access tokens where available. See [Plane's authentication guide](https://developers.plane.so/api-reference/v2/authentication).

Run this in your own terminal:

```sh
python3 "$HOME/.local/bin/plane-mcp" work-a --set-token
python3 "$HOME/.local/bin/plane-mcp" work-a --check-profile
```

Paste only the token at the hidden prompt. The launcher writes it atomically with mode `600`, outside the repository. It never takes tokens as command-line arguments or stores them in profiles. `--set-token` requires an interactive terminal. Configure `lab` separately; `work-b` can use the shared `work.token` from the example.

`--check-profile` validates the JSON and token file locally. It makes no network request and does not check Plane authentication or whether uvx is installed.

Use each person's own token. Access follows Plane's token scope, memberships and roles. Store profiles and token files only in directories you control. The token is a plain-text local secret, not an encrypted vault; it is passed to the official subprocess through its environment. Processes with the same user privileges or administrative access may read it. Payload and user-display-name logging are disabled, but upstream errors and client logs may still contain sensitive details. Redact logs before sharing them.

## Configure your client

The examples explicitly select a Python interpreter so GUI apps do not accidentally use an older system Python via the script's shebang. Run `command -v python3` in a terminal and use that absolute path. Replace `/ABSOLUTE/HOME` with your actual home directory in configuration files; clients do not necessarily expand `~` or shell variables there.

Repeat registration with a **unique server name and profile argument** for each workspace.

### Codex: CLI, desktop and IDE extension

```sh
codex mcp add plane-work-a -- "$(command -v python3)" "$HOME/.local/bin/plane-mcp" work-a
codex mcp add plane-work-b -- "$(command -v python3)" "$HOME/.local/bin/plane-mcp" work-b
codex mcp get plane-work-a
codex mcp list
```

Alternatively, merge these entries into the user-level `~/.codex/config.toml`:

```toml
[mcp_servers.plane-work-a]
command = "/absolute/path/to/python3"
args = ["/ABSOLUTE/HOME/.local/bin/plane-mcp", "work-a"]
startup_timeout_sec = 30

[mcp_servers.plane-work-b]
command = "/absolute/path/to/python3"
args = ["/ABSOLUTE/HOME/.local/bin/plane-mcp", "work-b"]
startup_timeout_sec = 30
```

These entries use stdio; no URL or OAuth login is needed. Restart the connection, open a fresh CLI session, or fully quit and reopen the desktop app after changing settings. Use `/mcp` in the Codex CLI to inspect active servers. User-level configuration is shared by supported local Codex clients; project configuration and administrator policies can affect availability. A cloud agent needs its own credentials and connectivity. See the [official Codex MCP guide](https://developers.openai.com/codex/mcp).

### Claude Code

```sh
claude mcp add --transport stdio --scope user plane-work-a -- "$(command -v python3)" "$HOME/.local/bin/plane-mcp" work-a
claude mcp add --transport stdio --scope user plane-work-b -- "$(command -v python3)" "$HOME/.local/bin/plane-mcp" work-b
claude mcp get plane-work-a
```

User scope stores the entries in `~/.claude.json`. Start a fresh session and inspect `/mcp`. Local or project entries with the same name take precedence. See the [official Claude Code MCP guide](https://code.claude.com/docs/en/mcp).

### Claude Desktop on macOS

Open **Settings → Developer → Edit Config**. Merge this JSON into `~/Library/Application Support/Claude/claude_desktop_config.json`, preserving existing server entries:

```json
{
  "mcpServers": {
    "plane-work-a": {
      "command": "/absolute/path/to/python3",
      "args": ["/ABSOLUTE/HOME/.local/bin/plane-mcp", "work-a"]
    },
    "plane-work-b": {
      "command": "/absolute/path/to/python3",
      "args": ["/ABSOLUTE/HOME/.local/bin/plane-mcp", "work-b"]
    }
  }
}
```

Fully quit and reopen Claude Desktop. Its configuration is separate from Claude Code and claude.ai web connectors. A web connector cannot directly launch this local script. See the [MCP local-server setup guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

## Verify the connection

1. **Local files:** run `python3 "$HOME/.local/bin/plane-mcp" work-a --check-profile`.
2. **Plane API:** run the read-only connectivity check:

   ```sh
   python3 "$HOME/.local/bin/plane-mcp" work-a --check-connection
   ```

   It sends one authenticated GET to `/api/v1/workspaces/<slug>/projects/`, with a 15-second timeout and normal TLS verification. It expects HTTP `200` and a JSON content type, prints no response body, and does not follow redirects. This checks API reachability and access to the projects endpoint, not the MCP protocol or every tool.
3. **MCP and workspace access:** in your connected client, ask:

   > Using plane-work-a, list the projects I can access. Report their names and identifiers. Do not change anything.

   Then request the details of an existing project or work item. Repeat for each connection. Successful tool discovery alone does not prove that Plane API requests work. No test tickets or other data changes are required.

Before requesting edits, identify the intended connection, workspace and project. The launcher does not enforce read-only access; tool permissions and approvals belong to the client and Plane.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Missing or invalid profile | File `~/.config/plane-mcp/profiles/<name>.json`, exact keys, valid UTF-8 JSON, root URL and workspace slug. |
| Wrong token permissions or ownership | Run `--set-token` as your normal user. Use mode `600`, a regular file and no symlink. Do not run the client with `sudo`. |
| `Python 3.10 or newer is required` | Select your installed Python. On macOS, avoid an outdated `/usr/bin/python3`; update the client's absolute `command` path. |
| `uvx was not found` | Install uv, verify `uvx --version` and restart the client. The launcher searches PATH, `~/.local/bin`, `/opt/homebrew/bin` and `/usr/local/bin`. |
| uv rejects an option or package installation fails | Update uv; run the prefetch command with the same interpreter; check package-index access, proxy settings, disk space and dependency errors. |
| Startup times out | Prefetch dependencies before starting the client. For Codex, set `startup_timeout_sec = 30`, or increase it if needed. |
| Script appears to wait when run without a flag | Normal stdio behavior: it is waiting for MCP input from a client. Use `--check-profile` or `--check-connection` for terminal checks; Ctrl-C stops it. |
| HTTP 301/302/307/308 | Set the final canonical root URL, including HTTPS. The connection check rejects redirects to avoid forwarding credentials. Check reverse proxy routing. |
| HTTP 401 | Token is wrong, expired, revoked, or belongs to another instance. Rotate it with `--set-token`. |
| HTTP 403 | Token scope, workspace/project membership or role permissions. |
| HTTP 404 | Incorrect root URL, workspace slug, IDs, or an API endpoint unavailable in your Plane release. |
| HTTP 429 or 5xx | Plane rate limits, service health or reverse proxy errors. Retry after resolving the cause. |
| HTTP 200 with HTML | A login page, frontend or proxy intercepted the API route. Check the root URL and `/api/v1/` routing. |
| DNS, TLS or timeout error | VPN/private network access, DNS, certificate trust, proxy and instance availability. Keep TLS verification enabled; configure trusted certificates instead of disabling verification. |
| Tools appear but calls fail | Check the API with `--check-connection`; compare Plane and MCP API compatibility. Inspect local client logs, redacting sensitive details. |
| New profile/token has no effect | Reconnect or restart every connection using the file: configuration loads when the subprocess starts. |
| Wrong instance despite environment settings | The profile is authoritative: the launcher overrides `PLANE_API_KEY`, `PLANE_BASE_URL` and `PLANE_WORKSPACE_SLUG`, and removes inherited `PLANE_INTERNAL_BASE_URL`. |

For Claude Desktop on macOS, logs are in `~/Library/Logs/Claude/` (`mcp.log` and `mcp-server-<name>.log`). Keep stdout reserved for MCP protocol messages; launcher errors go to stderr.

## Maintenance and removal

To rotate credentials: create a replacement token, run `--set-token` for a profile using that token file, reconnect all affected entries, verify reads, then revoke the old token in Plane. Changing a shared token file affects all profiles referencing it.

To update: review upstream release notes, change the `PACKAGE` pin in `plane-mcp.py`, update the prefetch commands in this README and `INSTALL.md` and attribution/version references, run the tests, reinstall the launcher and recheck connectivity. uv resolves transitive dependencies independently; this is a server-version pin, not a complete dependency lock.

The old npm package `@makeplane/plane-mcp-server` is deprecated. This launcher uses the official Python server and `PLANE_BASE_URL`; it does not use the old `PLANE_API_HOST_URL` setting. See [Plane's migration guidance](https://developers.plane.so/dev-tools/mcp-server).

To remove a client entry:

```sh
codex mcp remove plane-work-a
claude mcp remove --scope user plane-work-a
```

For Claude Desktop, remove the corresponding JSON entry and restart. Remove your installed launcher and local profiles/tokens when no longer needed. Removing an entry or deleting a token file does not revoke the token in Plane; revoke it in Plane separately.

## Development and public-repository hygiene

Run the standard-library test suite without Plane credentials or external dependencies:

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile plane-mcp.py
```

Tests use temporary profiles, dummy tokens, mocked process replacement and a loopback HTTP server. They check configuration validation, private token handling, connection errors, and the exact upstream command/environment. No real Plane instance is contacted.

To check the actual official package through the launcher, run the optional smoke test. It downloads dependencies if needed, initializes stdio, discovers tools and lists projects against a fake loopback API:

```sh
uvx --no-config --no-env-file --python "$(command -v python3)" \
  --from plane-mcp-server==0.3.4 python tests/smoke_upstream.py
```

This also uses only a dummy token and temporary profiles. It requires permission to bind a loopback socket and does not prove compatibility with a real Plane release.

Only generic `.example.json` profiles belong in this repository. Real profiles, token files, client configuration, environment files and logs are ignored by `.gitignore`; keep them outside the checkout anyway. Ignore rules do not sanitize files or protect files already tracked. Before publishing, inspect staged contents with `git diff --cached` and `git ls-files`. Never include credentials, personal profiles, private hostnames or client logs in commits or issues.

## References

- [Official Plane MCP server source and license](https://github.com/makeplane/plane-mcp-server)
- [Plane MCP documentation](https://developers.plane.so/dev-tools/mcp-server)
- [Pinned PyPI package](https://pypi.org/project/plane-mcp-server/0.3.4/)
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)
- [Codex MCP configuration](https://developers.openai.com/codex/mcp)
- [Claude Code MCP configuration](https://code.claude.com/docs/en/mcp)
- [Claude Desktop local MCP configuration](https://modelcontextprotocol.io/docs/develop/connect-local-servers)
