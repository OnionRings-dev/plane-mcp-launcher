# Agent-assisted local setup

Give this file to a local coding agent with terminal and file access, and ask:

> Follow INSTALL.md to install Plane MCP Launcher on my computer. Clone the
> repository if needed, ask me for the connection details, guide me through
> creating and storing my Plane token, configure my chosen MCP client, and verify
> the connection. Never ask me to paste the token into chat.

This file can be used on its own before cloning. The repository is
**https://github.com/OnionRings-dev/plane-mcp-launcher.git**. It installs a local
launcher for the official Plane MCP server; the user must already have a Plane
instance and an account with workspace access.

## Instructions for the agent

Carry out the setup, rather than only returning commands. Use the user's language
for questions and explanations. Continue through the steps you can perform;
pause when user input, token entry, or a client restart is needed. Resume from
the last completed step when the user returns.

- Keep credentials outside the checkout and client configuration. Never request,
  print, read back, or place a token in chat, command arguments, shell history,
  environment files, or logs. Use the launcher's hidden token prompt.
- Reuse a working installation. Preserve existing profiles, tokens and unrelated
  client settings. Before editing an existing client configuration, make a private
  backup alongside it. If a profile or server name already points elsewhere, ask
  whether to use a new name or replace that specific connection.
- Run the launcher and client as the normal user, without `sudo`. Follow the
  environment's permission controls for package installation and writes outside
  the checkout. If an action is blocked, explain the exact blocker and give the
  user the corresponding command to run locally.
- Verify using reads only. Do not create test projects, tickets or comments.

## 1. Gather the connection details

Inspect the OS and available tools first. Ask for missing details together in
one short message; use information already provided:

| Detail | Guidance / default |
| --- | --- |
| MCP client | Codex (CLI, desktop or IDE), Claude Code, OpenCode, or Claude Desktop on macOS. Configure only the selected client(s). |
| Plane instance | Root URL, such as `https://plane.example.com`; no `/api/v1`, workspace path, credentials, query or fragment. |
| Workspace | URL slug, not display name or UUID. For `https://plane.example.com/team-a/`, use `team-a`. |
| Local profile | Suggest `work`; allow letters, digits, `_` and `-`, starting with a letter or digit. |
| Client server name | Suggest `plane-work`, adapting it to the profile. |
| Checkout | Reuse this repository if already present; otherwise suggest `~/repositories/plane-mcp-launcher`. |

Ask whether the user already has a token stored for this connection, **not for
the token itself**. Collect one instance/workspace first, then repeat for any
additional connections. A profile covers all projects the account can access
in that workspace.

Supported platforms are Linux, macOS, and WSL for CLI clients. Native Windows is
unsupported. A native Windows GUI client cannot directly launch these WSL paths.
On Linux use a CLI client such as Codex CLI, Claude Code or OpenCode; the Claude
Desktop instructions here apply only to macOS. In WSL, install and run the
launcher, Python, uv and CLI client inside the same Linux distribution, with
profiles and tokens in its Linux home directory.
A cloud-only agent or web connector cannot install this local stdio connection;
the agent must run on the computer where the MCP client launches processes.

## 2. Check prerequisites and clone

Use `sh`, Bash or Zsh for the shell snippets. If the user's shell is Fish,
run them through `sh` rather than pasting incompatible assignments into Fish.
Check the OS with `uname -s`; on Linux also inspect `/etc/os-release` before
selecting a package manager. Check Git, Python 3.10+, `uvx` and the selected
client. Install only missing prerequisites; do not assume Homebrew on Linux.

- Ubuntu/Debian: `sudo apt-get update`, then
  `sudo apt-get install -y python3 git curl ca-certificates coreutils`.
- Fedora: `sudo dnf install -y python3 git curl ca-certificates coreutils`.
- macOS with Homebrew already installed: `brew install python uv git`.

On Linux, or macOS without Homebrew, use the
[official uv installer](https://docs.astral.sh/uv/getting-started/installation/)
as the normal user: `curl -LsSf https://astral.sh/uv/install.sh | sh`.
For its default installation, `export PATH="$HOME/.local/bin:$PATH"` makes uv
available in the current shell. Respect a custom install location and ensure
the client inherits that location in PATH. Administrative privileges are only
for system package installation; never run the launcher or client with `sudo`.

Check the actual Python version: older Linux distributions and macOS's
`/usr/bin/python3` may be too old. If the supported interpreter is named
`python3.12`, use `command -v python3.12` in the selection below. Do not replace
the OS's system Python. The remaining `mkdir -p`, `install -m`, `cp`, `chmod`
and `command -v` options work on both GNU/Linux and macOS; GNU-only options or
macOS-only tools are unnecessary. Install the chosen MCP client separately
using its official instructions if it is missing.

For a new checkout, create the chosen parent directory and run the equivalent of:

```sh
git clone https://github.com/OnionRings-dev/plane-mcp-launcher.git "$HOME/repositories/plane-mcp-launcher"
```

Never clone over a nonempty directory or reset an existing checkout. If access
fails, help the user resolve repository access without requesting GitHub secrets
in chat. In an existing checkout, inspect its remote and local changes before
reusing it; do not automatically pull over local work.

Read the checkout's `README.md` and `plane-mcp.py` before installation. Their
actual options and `PACKAGE` pin take precedence if this guide has drifted.
Do not upgrade the official server as part of setup.

Select a working Python interpreter and record its **absolute path**. The
examples below use these shell variables; replace the names with the user's
chosen values and restore the variables if shell calls do not share state:

```sh
plane_mcp_python="$(command -v python3)"
plane_mcp_profile=work
plane_mcp_server=plane-work
"$plane_mcp_python" -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"; print(sys.executable)'
uvx --version
```

Use the selected interpreter throughout, including client configuration. Keep
that Python installation available after setup. Use paths on the machine
running the client process: home directories are typically `/home/<user>` on
Linux and `/Users/<user>` on macOS. Do not copy a macOS path to a Linux client.

## 3. Install the launcher and prepare the package

From the checkout, install the launcher. If the destination exists, compare it
first; preserve a private backup before replacing a different version.

```sh
mkdir -p "$HOME/.local/bin"
install -m 700 plane-mcp.py "$HOME/.local/bin/plane-mcp"
"$plane_mcp_python" "$HOME/.local/bin/plane-mcp" --help
uvx --no-config --no-env-file --python "$plane_mcp_python" \
  --from plane-mcp-server==0.3.4 \
  python -c 'from importlib.metadata import version; print(version("plane-mcp-server"))'
```

The expected package version is `0.3.4`; use the checkout's pin if it changes.
Prefetching requires internet access and does not authenticate to Plane. No
launcher virtual environment, daemon, Docker container or public port is needed.

## 4. Create one private profile

```sh
mkdir -p "$HOME/.config/plane-mcp/profiles" "$HOME/.config/plane-mcp/tokens"
chmod 700 "$HOME/.config/plane-mcp" "$HOME/.config/plane-mcp/profiles" "$HOME/.config/plane-mcp/tokens"
```

Create `~/.config/plane-mcp/profiles/<profile>.json` with mode `600`, substituting
the agreed values. Use a JSON serializer to encode user-provided strings safely.
For the example profile `work`:

```json
{
  "base_url": "https://plane.example.com",
  "workspace_slug": "team-a",
  "token_file": "~/.config/plane-mcp/tokens/work.token"
}
```

Use exactly these three fields. `token_file` must be absolute or start with `~/`;
`$HOME` is not expanded inside JSON. Keep the real profile outside the checkout.
Prefer HTTPS; HTTP is intended only for trusted local development. Custom API
URL prefixes are unsupported.

On a repeated setup, reuse a matching profile and validate its existing token
with `--check-profile`; do not overwrite or rotate it automatically. For another
instance or account use a separate token file. Share an existing token file
between workspaces only when the user intends it and the token grants access.

## 5. Guide the user through token creation and entry

If a suitable token is already stored, skip creation and proceed to validation.
Otherwise guide the user, one step at a time:

1. Open **their Plane instance** in a browser and sign in with their own account.
2. Open **Profile Settings → Personal Access Tokens** and choose **Add personal
   access token**. Labels can differ by Plane release; if the option is missing,
   check the instance's version and settings rather than guessing another URL.
3. Give it a recognizable name, such as `Local Plane MCP`. If scope or expiry
   choices are offered, choose access appropriate to the intended workspace and
   tasks. A read-only setup check does not make the connection read-only.
4. Copy the generated token privately and paste it **only into the hidden prompt
   in the user's own terminal**, using the command below.

See [Plane's authentication documentation](https://developers.plane.so/api-reference/v2/authentication).

Give the user a concrete command with the actual absolute Python and launcher
paths and profile name, correctly shell-quoted. The template is:

```sh
"$plane_mcp_python" "$HOME/.local/bin/plane-mcp" "$plane_mcp_profile" --set-token
```

Do not ask the user to recreate these shell variables in a separate terminal;
resolve them in the command you provide. Wait for them to confirm the command
completed. Do not run the hidden prompt in an agent-controlled terminal or feed
the secret through a tool. The launcher requires an interactive terminal and
saves the token atomically with mode `600`.

## 6. Validate and register the selected client

Run both checks without reading or displaying the token file:

```sh
"$plane_mcp_python" "$HOME/.local/bin/plane-mcp" "$plane_mcp_profile" --check-profile
"$plane_mcp_python" "$HOME/.local/bin/plane-mcp" "$plane_mcp_profile" --check-connection
```

The first validates local files; the second sends a read-only GET to the Plane
projects endpoint and expects HTTP `200` JSON. If it fails, use the README's
troubleshooting table. Keep TLS verification enabled and resolve redirects by
using the canonical instance root URL. Do not retry with broader credentials
without understanding the failure.

Inspect only the relevant client entry before adding it. Back up an existing
configuration privately without printing unrelated settings or secrets. Reuse an
identical entry; resolve a name collision as described above.

### Codex

```sh
codex mcp add "$plane_mcp_server" -- "$plane_mcp_python" "$HOME/.local/bin/plane-mcp" "$plane_mcp_profile"
codex mcp get "$plane_mcp_server"
```

If the CLI is unavailable, merge one `[mcp_servers.<server-name>]` entry into the
active user configuration, normally `~/.codex/config.toml`, with the absolute
Python path as `command`, launcher path and profile as `args`, and
`startup_timeout_sec = 30`. Respect a custom Codex configuration location.
Use a TOML-aware edit and preserve other settings; do not append duplicate tables.
See the [official Codex MCP guide](https://developers.openai.com/codex/mcp).

### Claude Code

```sh
claude mcp add --transport stdio --scope user "$plane_mcp_server" -- "$plane_mcp_python" "$HOME/.local/bin/plane-mcp" "$plane_mcp_profile"
claude mcp get "$plane_mcp_server"
```

User scope keeps the connection outside project configuration. See the
[official Claude Code MCP guide](https://code.claude.com/docs/en/mcp).

### OpenCode

Merge one entry under `mcp` in the global `~/.config/opencode/opencode.json`
(or the user's existing `opencode.jsonc`). Respect custom configuration and
preserve unrelated settings. Use a JSONC-aware edit for files with comments;
validate the result without printing unrelated settings. Do not create a
project configuration for this personal connection.

For the example profile `work` and server `plane-work`, substitute the selected
absolute Python and launcher paths:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "plane-work": {
      "type": "local",
      "command": ["/absolute/path/to/python3", "/ABSOLUTE/HOME/.local/bin/plane-mcp", "work"],
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

Use the agreed server name and profile. `command` includes the executable and
arguments in one array; `timeout` is in milliseconds. No token belongs in this
configuration. Restart OpenCode, then run `opencode mcp list` from the intended
project to check status. Project or managed settings may override global
entries. With a remote backend, install on the backend computer.

See the official [OpenCode MCP guide](https://opencode.ai/docs/mcp-servers/),
[configuration guide](https://opencode.ai/docs/config/) and
[MCP CLI commands](https://opencode.ai/docs/cli/#mcp). Continue with step 7;
connection status alone does not verify access to Plane projects.

### Claude Desktop on macOS

Merge one entry under `mcpServers` in
`~/Library/Application Support/Claude/claude_desktop_config.json`, using the
absolute Python path as `command` and `[absolute_launcher_path, profile_name]`
as `args`. Preserve existing entries and validate the resulting JSON. The
README contains a complete example. Claude Code's configuration is separate.

In every client, configure a **local stdio command**. Keep the token in its
private file; this setup does not require an MCP URL or OAuth login.

## 7. Reconnect, verify MCP, and hand over

Ask the user to reconnect the server or start a fresh CLI session; desktop apps
may need to be fully quit and reopened. Do not close the user's app yourself.

Once tools are available, use the newly configured connection to list accessible
projects. If this agent cannot access newly added tools until a new session,
provide this prompt with the actual server name:

> Using plane-work, list the projects I can access. Report their names and
> identifiers. Do not change anything.

Report the outcome precisely:

- Checkout, installed launcher and interpreter paths.
- Profile and client server names, and the client configuration location.
- Local validation, API connectivity, and MCP project-list result separately.
  Mark any check awaiting a restart or another session as **pending**.
- Any remaining user action, with the exact command or prompt needed.

Do not claim MCP verification from a successful API check or tool discovery
alone. An empty project list can be valid; confirm that it matches the user's
expected access. To add another workspace, repeat the profile, token validation
and client registration steps with unique names. Explain that future token
rotation uses the same `--set-token` command followed by reconnection; removing
a local token file does not revoke it in Plane.
