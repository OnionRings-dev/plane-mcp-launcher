"""Offline regression tests; all tokens and profiles here are fictional."""

import contextlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import URLError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("launcher", ROOT / "plane-mcp.py")
launcher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(launcher)
DUMMY_TOKEN = "dummy-local-test-value"


class LauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "config"
        (self.config / "profiles").mkdir(parents=True)
        self.token = self.root / "test.token"
        self.token.write_text(DUMMY_TOKEN + "\n", encoding="utf-8")
        self.token.chmod(0o600)
        self.profile = {
            "base_url": "https://plane.example.com/",
            "workspace_slug": "team-a",
            "token_file": str(self.token),
        }
        self.config_patch = patch.object(launcher, "CONFIG_DIR", self.config)
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.save_profile()

    def save_profile(self, value=None):
        (self.config / "profiles" / "work-a.json").write_text(
            json.dumps(self.profile if value is None else value), encoding="utf-8"
        )

    def assert_failure(self, callback, *args):
        with contextlib.redirect_stderr(io.StringIO()) as output:
            with self.assertRaises(SystemExit) as error:
                callback(*args)
        self.assertEqual(error.exception.code, 1)
        self.assertNotIn(DUMMY_TOKEN, output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
        return output.getvalue()

    def run_main(self, *arguments):
        with patch.object(sys, "argv", ["plane-mcp", "work-a", *arguments]):
            launcher.main()

    def test_profile_normalizes_root_and_expands_home(self):
        self.profile["token_file"] = "~/private/test.token"
        self.save_profile()
        base, workspace, token = launcher.load_profile("work-a")
        self.assertEqual(base, "https://plane.example.com")
        self.assertEqual(workspace, "team-a")
        self.assertEqual(token, Path.home() / "private/test.token")

    def test_profile_names_cannot_escape_directory(self):
        for name in ("../work-a", "/tmp/work-a", ".", "a/b", "-a", "a b"):
            with self.subTest(name=name):
                self.assert_failure(launcher.load_profile, name)

    def test_profile_schema_rejects_secrets_and_wrong_types(self):
        for value in ([], {**self.profile, "api_key": "should-not-be-here"},
                      {"base_url": "https://plane.example.com"},
                      {**self.profile, "workspace_slug": 123},
                      {**self.profile, "workspace_slug": " team-a"},
                      {**self.profile, "token_file": "bad\x00path"}):
            with self.subTest(value=value):
                self.save_profile(value)
                self.assert_failure(launcher.load_profile, "work-a")

    def test_malformed_profile_files_fail_without_traceback(self):
        path = self.config / "profiles" / "work-a.json"
        for content in (b"{", b"\xff"):
            path.write_bytes(content)
            self.assert_failure(launcher.load_profile, "work-a")
        path.unlink()
        self.assert_failure(launcher.load_profile, "work-a")

    def test_rejects_non_root_or_malformed_urls(self):
        for url in ("https://u:p@plane.example.com", "https://plane.example.com/team-a/",
                    "https://plane.example.com/api/v1", "https://plane.example.com?q=1",
                    "https://plane.example.com/#x", "ftp://plane.example.com", "https://",
                    "https://[broken", "https://plane.example.com:70000", "https://bad host"):
            with self.subTest(url=url):
                self.profile["base_url"] = url
                self.save_profile()
                self.assert_failure(launcher.load_profile, "work-a")

    def test_accepts_local_port_and_ipv6(self):
        for url in ("http://localhost:8000", "http://[::1]:8000/"):
            with self.subTest(url=url):
                self.profile["base_url"] = url
                self.save_profile()
                self.assertEqual(launcher.load_profile("work-a")[0], url.rstrip("/"))

    def test_rejects_bad_slugs_and_relative_token_paths(self):
        for slug in ("team/a", "Team A", "https://plane.example.com/a", ""):
            self.profile["workspace_slug"] = slug
            self.save_profile()
            self.assert_failure(launcher.load_profile, "work-a")
        self.profile["workspace_slug"] = "team-a"
        self.profile["token_file"] = "relative.token"
        self.save_profile()
        self.assert_failure(launcher.load_profile, "work-a")

    def test_reads_private_token_with_trailing_newline(self):
        self.assertEqual(launcher.read_token(self.token), DUMMY_TOKEN)
        self.token.chmod(0o400)
        self.assertEqual(launcher.read_token(self.token), DUMMY_TOKEN)

    def test_rejects_exposed_token_permissions(self):
        for mode in (0o644, 0o640, 0o601):
            self.token.chmod(mode)
            self.assert_failure(launcher.read_token, self.token)

    def test_rejects_token_owned_by_another_user(self):
        with patch.object(launcher.os, "getuid", return_value=os.getuid() + 1):
            self.assert_failure(launcher.read_token, self.token)

    def test_rejects_symlinks_directories_missing_files_and_fifos(self):
        link = self.root / "link"
        link.symlink_to(self.token)
        fifo = self.root / "fifo"
        os.mkfifo(fifo, 0o600)
        for path in (link, self.root, self.root / "missing", fifo):
            with self.subTest(path=path):
                self.assert_failure(launcher.read_token, path)

    def test_rejects_invalid_or_oversized_tokens(self):
        for content in (b"", b"has space", b"a\nb", b"a\x00b", b"a\x7fb", b"\xff", b"a" * 17000):
            with self.subTest(content_length=len(content)):
                self.token.write_bytes(content)
                self.assert_failure(launcher.read_token, self.token)

    def test_store_token_is_private_and_does_not_echo_secret(self):
        with patch.object(launcher.sys.stdin, "isatty", return_value=True), \
                patch.object(launcher.getpass, "getpass", return_value=DUMMY_TOKEN), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            launcher.store_token(self.token)
        self.assertEqual(stat.S_IMODE(self.token.stat().st_mode), 0o600)
        self.assertEqual(launcher.read_token(self.token), DUMMY_TOKEN)
        self.assertNotIn(DUMMY_TOKEN, output.getvalue())
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_invalid_or_cancelled_entry_preserves_existing_token(self):
        original = self.token.read_bytes()
        with patch.object(launcher.sys.stdin, "isatty", return_value=True):
            with patch.object(launcher.getpass, "getpass", return_value="bad token"):
                self.assert_failure(launcher.store_token, self.token)
            with patch.object(launcher.getpass, "getpass", side_effect=EOFError):
                with self.assertRaises(EOFError):
                    launcher.store_token(self.token)
        self.assertEqual(self.token.read_bytes(), original)

    def test_non_interactive_entry_is_rejected(self):
        with patch.object(launcher.sys.stdin, "isatty", return_value=False), \
                patch.object(launcher.getpass, "getpass") as prompt:
            self.assert_failure(launcher.store_token, self.token)
        prompt.assert_not_called()

    def test_failed_atomic_write_preserves_old_token_and_cleans_temp(self):
        original = self.token.read_bytes()
        with patch.object(launcher.sys.stdin, "isatty", return_value=True), \
                patch.object(launcher.getpass, "getpass", return_value="replacement-dummy"), \
                patch.object(launcher.os, "replace", side_effect=PermissionError):
            self.assert_failure(launcher.store_token, self.token)
        self.assertEqual(self.token.read_bytes(), original)
        self.assertEqual(len(list(self.root.iterdir())), 2)

    def test_check_profile_never_starts_server_or_network(self):
        with patch.object(launcher.os, "execve") as execute, \
                patch.object(launcher, "build_opener") as network, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.run_main("--check-profile")
        execute.assert_not_called()
        network.assert_not_called()
        self.assertIn("has not been checked", output.getvalue())

    def test_launch_uses_pinned_official_server_and_profile_environment(self):
        inherited = {"PLANE_API_KEY": "old-dummy", "PLANE_BASE_URL": "https://old.example.org",
                     "PLANE_WORKSPACE_SLUG": "old", "PLANE_INTERNAL_BASE_URL": "https://wrong.example.org",
                     "LOG_PAYLOADS": "true", "LOG_USER_INFO": "true"}
        with patch.dict(os.environ, inherited), \
                patch.object(launcher.shutil, "which", return_value="/fake/uvx"), \
                patch.object(launcher.os.path, "isfile", return_value=True), \
                patch.object(launcher.os, "access", return_value=True), \
                patch.object(launcher.os, "execve") as execute, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.run_main()
        executable, command, environment = execute.call_args.args
        self.assertEqual(executable, "/fake/uvx")
        self.assertEqual(command, ["/fake/uvx", "--no-config", "--no-env-file", "--python", sys.executable,
                                   "--from", "plane-mcp-server==0.3.4", "plane-mcp-server", "stdio"])
        self.assertEqual(environment["PLANE_API_KEY"], DUMMY_TOKEN)
        self.assertEqual(environment["PLANE_BASE_URL"], "https://plane.example.com")
        self.assertEqual(environment["PLANE_WORKSPACE_SLUG"], "team-a")
        self.assertNotIn("PLANE_INTERNAL_BASE_URL", environment)
        self.assertEqual(environment["LOG_PAYLOADS"], "false")
        self.assertEqual(environment["LOG_USER_INFO"], "false")
        self.assertEqual(output.getvalue(), "")

    def test_missing_uvx_or_failed_exec_is_a_clean_error(self):
        with patch.object(launcher.shutil, "which", return_value=None), \
                patch.object(launcher.os.path, "isfile", return_value=False):
            self.assertIn("uvx was not found", self.assert_failure(self.run_main))
        with patch.object(launcher.shutil, "which", return_value="/fake/uvx"), \
                patch.object(launcher.os.path, "isfile", return_value=True), \
                patch.object(launcher.os, "access", return_value=True), \
                patch.object(launcher.os, "execve", side_effect=OSError):
            self.assertIn("Cannot execute", self.assert_failure(self.run_main))

    def test_check_connection_flag_does_not_start_mcp(self):
        with patch.object(launcher, "check_connection") as check, \
                patch.object(launcher.os, "execve") as execute:
            self.run_main("--check-connection")
        check.assert_called_once_with("https://plane.example.com", "team-a", DUMMY_TOKEN)
        execute.assert_not_called()

    def test_unsupported_platform_or_python_is_clear(self):
        with patch.object(launcher.os, "name", "nt"):
            self.assertIn("native Windows", self.assert_failure(launcher.main))
        with patch.object(launcher.sys, "version_info", (3, 9)):
            self.assertIn("Python 3.10", self.assert_failure(launcher.main))

    def test_connection_network_error_does_not_leak_details(self):
        with patch.object(launcher, "build_opener") as opener:
            opener.return_value.open.side_effect = URLError(DUMMY_TOKEN)
            self.assert_failure(launcher.check_connection, "https://plane.example.com", "team-a", DUMMY_TOKEN)


class ConnectionTests(unittest.TestCase):
    """Real HTTP transport on loopback; verifies redirects cannot leak a token."""

    def setUp(self):
        self.status = 200
        self.content_type = "application/json"
        self.requests = []
        self.user_agents = []
        case = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                case.requests.append((self.path, self.headers.get("x-api-key")))
                case.user_agents.append(self.headers.get("User-Agent"))
                self.send_response(case.status)
                self.send_header("Content-Type", case.content_type)
                if case.status in (301, 302, 307, 308):
                    self.send_header("Location", "/must-not-follow")
                self.end_headers()
                self.wfile.write(b'[]')

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        self.url = "http://127.0.0.1:" + str(server.server_port)

    def test_projects_get_uses_rest_auth_and_prints_no_payload(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            launcher.check_connection(self.url, "team-a", DUMMY_TOKEN)
        self.assertEqual(self.requests, [("/api/v1/workspaces/team-a/projects/", DUMMY_TOKEN)])
        self.assertEqual(self.user_agents, [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"
        ])
        self.assertIn("HTTP 200 JSON", output.getvalue())
        self.assertNotIn(DUMMY_TOKEN, output.getvalue())
        self.assertNotIn("[]", output.getvalue())

    def test_http_failures_and_redirects_do_not_follow_or_echo_secret(self):
        for status in (301, 302, 307, 308, 401, 403, 404, 429, 500):
            with self.subTest(status=status):
                self.status = status
                self.requests.clear()
                with contextlib.redirect_stderr(io.StringIO()) as output:
                    with self.assertRaises(SystemExit):
                        launcher.check_connection(self.url, "team-a", DUMMY_TOKEN)
                self.assertIn("HTTP " + str(status), output.getvalue())
                self.assertNotIn(DUMMY_TOKEN, output.getvalue())
                self.assertEqual(len(self.requests), 1)
                self.assertNotEqual(self.requests[0][0], "/must-not-follow")

    def test_html_login_page_is_not_success(self):
        self.content_type = "text/html"
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                launcher.check_connection(self.url, "team-a", DUMMY_TOKEN)


if __name__ == "__main__":
    unittest.main()
