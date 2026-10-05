"""Run: python test_explain.py"""
import json
import tempfile
from pathlib import Path

import explain


def line(type_, content, **extra):
    return json.dumps({"type": type_, "message": {"content": content}, **extra})


def test_exchanges():
    log = [
        line("user", "<command-name>/clear</command-name>"),
        line("user", "first question"),
        line("assistant", [{"type": "text", "text": "first answer"}]),
        line("user", "fix the bug"),
        line("assistant", [{"type": "thinking", "thinking": "hmm"}]),
        line("assistant", [{"type": "text", "text": "Let me check..."}]),
        line("assistant", [{"type": "tool_use", "name": "Read"}]),
        line("user", [{"type": "tool_result", "content": "file text"}]),
        line("assistant", [{"type": "text", "text": "sub-agent noise"}], isSidechain=True),
        line("assistant", [{"type": "text", "text": "Fixed it. sk-abcdefghijklmnopqrstuvwxyz123"}]),
        line("user", "<bash-input>echo hi</bash-input>"),
        line("user", "gpt eli5"),
        "not json",
    ]
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "s.jsonl"
        p.write_text("\n".join(log), encoding="utf-8")
        pairs = explain.exchanges(p)
    assert pairs == [("first question", "first answer"),
                     ("fix the bug", "Fixed it. sk-abcdefghijklmnopqrstuvwxyz123")], pairs
    prompt = explain.build_prompt(*pairs[-1], "eli5")
    assert "[hidden secret]" in prompt and "sk-abc" not in prompt


def test_keyword():
    for p in ("gpt", " GPT ", "gpt eli5", "gpt 2", "gpt tldr 3"):
        assert explain.KEYWORD.match(p), p
    for p in ("gpt is better than you?", "gpt5", "use gpt"):
        assert not explain.KEYWORD.match(p), p
    assert explain.KEYWORD.match("gpt tldr 3").group(1).split() == ["tldr", "3"]


def test_install_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "settings.json"
        path.write_text(json.dumps({"theme": "dark"}))
        explain.settings_path = lambda: path
        explain.install()
        explain.install()  # twice -> still one hook
        hooks = json.loads(path.read_text())["hooks"]["UserPromptSubmit"]
        assert len(hooks) == 1 and "--hook" in hooks[0]["hooks"][0]["command"]
        explain.install(remove=True)
        assert json.loads(path.read_text()) == {"theme": "dark"}


if __name__ == "__main__":
    test_exchanges()
    test_keyword()
    test_install_roundtrip()
    print("all tests passed")
