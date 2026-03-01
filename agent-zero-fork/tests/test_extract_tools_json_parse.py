import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from python.helpers.extract_tools import json_parse_dirty


def test_json_parse_dirty_parses_plain_tool_request():
    msg = '{"tool_name":"response","tool_args":{"text":"ok"}}'
    parsed = json_parse_dirty(msg)
    assert parsed is not None
    assert parsed.get("tool_name") == "response"
    assert parsed.get("tool_args", {}).get("text") == "ok"


def test_json_parse_dirty_finds_tool_request_in_mixed_text():
    msg = (
        'Thinking step {"note":"not a tool"}\n'
        '```json\n'
        '{"tool_name":"memory_save","tool_args":{"text":"abc_123"}}\n'
        '```\n'
        'Trailing text {"meta":"ignored"}'
    )
    parsed = json_parse_dirty(msg)
    assert parsed is not None
    assert parsed.get("tool_name") == "memory_save"
    assert parsed.get("tool_args", {}).get("text") == "abc_123"


def test_json_parse_dirty_finds_nested_tool_request():
    msg = '{"analysis":{"ok":true},"result":{"tool_name":"response","tool_args":{"text":"done"}}}'
    parsed = json_parse_dirty(msg)
    assert parsed is not None
    assert parsed.get("tool_name") == "response"
    assert parsed.get("tool_args", {}).get("text") == "done"


def test_json_parse_dirty_returns_none_without_tool_request():
    msg = '{"message":"hello","meta":{"a":1}}'
    parsed = json_parse_dirty(msg)
    assert parsed is None
