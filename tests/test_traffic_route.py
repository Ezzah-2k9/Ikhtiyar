"""Exercise the actual Flask view body without a server or application DB."""

import ast
import unittest
from pathlib import Path
from unittest.mock import Mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class JsonReply:
    def __init__(self, payload):
        self.payload = payload


def load_traffic_view():
    """Compile the real route function with Flask globals replaced by fakes."""
    source_path = PROJECT_ROOT / "app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "traffic_tile"
    )
    function.decorator_list = []
    namespace = {
        "session": {},
        "jsonify": JsonReply,
        "TrafficService": Mock(),
        "Response": Mock(),
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace["traffic_tile"], namespace


class TrafficRouteTests(unittest.TestCase):
    def test_expired_session_returns_application_json_without_provider_call(self):
        view, namespace = load_traffic_view()

        reply, status = view(12, 2200, 1450)

        self.assertEqual(status, 401)
        self.assertEqual(reply.payload["source"], "application")
        self.assertEqual(reply.payload["code"], "AUTH_REQUIRED")
        self.assertIn("sign-in has expired", reply.payload["error"])
        namespace["TrafficService"].get_tile.assert_not_called()


if __name__ == "__main__":
    unittest.main()

