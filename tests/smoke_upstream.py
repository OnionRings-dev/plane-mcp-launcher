"""Optional real-upstream stdio check against a fake local Plane API.

Run with the pinned official package, as documented in README.md.
No real Plane credentials, client settings or profiles are used.
"""

import asyncio
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from urllib.parse import urlsplit

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


ROOT = Path(__file__).resolve().parents[1]
DUMMY_TOKEN = "dummy-upstream-smoke-value"


async def verify(config, log):
    # Override the module constant in this temporary subprocess only. This
    # deliberately avoids reading or modifying the user's real profiles.
    bootstrap = """
import importlib.util
from pathlib import Path
import sys
spec = importlib.util.spec_from_file_location('launcher', sys.argv[1])
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
launcher.CONFIG_DIR = Path(sys.argv[2])
sys.argv = [sys.argv[1], 'smoke']
launcher.main()
"""
    environment = os.environ.copy()
    # Prove that an inherited internal URL cannot override the profile.
    environment["PLANE_INTERNAL_BASE_URL"] = "http://127.0.0.1:1"
    environment["NO_PROXY"] = "127.0.0.1,localhost"
    parameters = StdioServerParameters(
        command=sys._base_executable,
        args=["-c", bootstrap, str(ROOT / "plane-mcp.py"), str(config)],
        env=environment,
    )
    async with stdio_client(parameters, errlog=log) as (reader, writer):
        async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=45)) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            assert {"project", "workspace"} <= names, "Expected official resource tools"
            workspace = await session.call_tool("workspace", {"action": "retrieve"})
            assert not workspace.isError, "Workspace tool failed"
            assert '"team-a"' in workspace.model_dump_json(), "Wrong workspace binding"
            projects = await session.call_tool("project", {"action": "list"})
            assert not projects.isError, "Official project list call failed"
            assert '"results"' in projects.model_dump_json(), "Missing project results"
            return len(names)


def main():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            requests.append((path, self.headers.get("x-api-key")))
            if path != "/api/v1/workspaces/team-a/projects-lite/" or self.headers.get("x-api-key") != DUMMY_TOKEN:
                self.send_error(404)
                return
            payload = json.dumps({
                "results": [], "total_count": 0, "next_cursor": "", "prev_cursor": "",
                "next_page_results": False, "prev_page_results": False,
                "count": 0, "total_pages": 0, "total_results": 0,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryFile(mode="w+") as log:
            config = Path(directory)
            (config / "profiles").mkdir()
            token = config / "smoke.token"
            token.write_text(DUMMY_TOKEN + "\n", encoding="utf-8")
            token.chmod(0o600)
            (config / "profiles" / "smoke.json").write_text(json.dumps({
                "base_url": "http://127.0.0.1:" + str(server.server_port),
                "workspace_slug": "team-a", "token_file": str(token),
            }), encoding="utf-8")
            count = asyncio.run(asyncio.wait_for(verify(config, log), timeout=60))
            assert requests == [("/api/v1/workspaces/team-a/projects-lite/", DUMMY_TOKEN)], "Unexpected API traffic"
            print(f"PASS: official server initialized, {count} tools discovered, workspace binding and project GET verified.")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


if __name__ == "__main__":
    main()
