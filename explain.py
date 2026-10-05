"""Send Claude Code's last answer to ChatGPT with an "explain this simply" prompt.

Usage inside Claude Code (after `python explain.py --install`):
    gpt            explain the last answer
    gpt eli5       explain like I'm 12
    gpt tldr       2-3 bullet points
    gpt steps      numbered to-do list
    gpt 2          explain the 2nd-latest answer (works with modes: gpt eli5 2)

Or from any terminal in a project folder:  python explain.py [mode] [N]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from urllib.parse import quote

CLAUDE_DIR = Path.home() / ".claude"
# Max link length before falling back to the clipboard. Measure on your setup and tune via env var.
MAX_URL = int(os.environ.get("GPT_MAX_URL", "8000"))
MAX_QUESTION = 1500
KEYWORD = re.compile(r"^\s*gpt((?:\s+(?:eli5|tldr|steps|\d+))*)\s*$", re.I)

MODES = {
    "": """Please explain its answer to me in simple, plain language:
1. The short version (1-2 sentences).
2. What it did or found.
3. What it means for me / my project.
4. What I should do next, if anything.
Explain any technical words briefly. Keep it easy to skim.""",
    "eli5": "Explain its answer like I'm 12 years old, using an everyday comparison. No jargon.",
    "tldr": "Give me the gist of its answer in 2-3 short bullet points. Nothing else.",
    "steps": "Turn its answer into a short numbered checklist of what I should do next, in plain words.",
}

NOISE_PREFIXES = ("<bash-input>", "<bash-stdout>", "<bash-stderr>", "<command-name>",
                  "<command-message>", "<local-command", "<system-reminder>", "<task-notification>")

SECRETS = re.compile(
    r"sk-[A-Za-z0-9_\-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_\-]{35}|xox[abprs]-[A-Za-z0-9\-]{10,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
)


def user_text(content):
    """The typed text of a user log entry, or None if it's a tool result / noise / our own keyword."""
    if isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content):
            return None
        content = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
    text = (content or "").strip()
    if not text or text.startswith(NOISE_PREFIXES) or KEYWORD.match(text):
        return None
    return text


def exchanges(log_path):
    """List of (question, final_answer) pairs from a Claude Code session log, oldest first."""
    turns = []  # each: [question, texts_after_last_tool, all_texts]
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("isSidechain") or d.get("isMeta") or d.get("isCompactSummary"):
                continue
            content = (d.get("message") or {}).get("content")
            if d.get("type") == "user":
                q = user_text(content)
                if q:
                    turns.append([q, [], []])
            elif d.get("type") == "assistant" and turns and isinstance(content, list):
                for b in content:
                    if b.get("type") == "tool_use":
                        turns[-1][1] = []  # the real answer is what comes after the last tool call
                    elif b.get("type") == "text" and b.get("text", "").strip():
                        turns[-1][1].append(b["text"].strip())
                        turns[-1][2].append(b["text"].strip())
    return [(q, "\n\n".join(final or every)) for q, final, every in turns if every]


def find_log(cwd):
    folder = CLAUDE_DIR / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(cwd))
    logs = list(folder.glob("*.jsonl")) or list((CLAUDE_DIR / "projects").glob("*/*.jsonl"))
    if not logs:
        raise SystemExit("No Claude Code session log found.")
    return max(logs, key=lambda p: p.stat().st_mtime)


def build_prompt(question, answer, mode=""):
    if len(question) > MAX_QUESTION:
        question = question[:MAX_QUESTION] + " [...]"
    text = (f'I\'m using an AI coding assistant (Claude Code). I asked it:\n"""\n{question}\n"""\n\n'
            f'It answered:\n"""\n{answer}\n"""\n\n{MODES[mode]}')
    return SECRETS.sub("[hidden secret]", text)


def copy_to_clipboard(text):
    if sys.platform == "win32":
        cmd, data = ["clip"], text.encode("utf-16")  # UTF-16 keeps emoji / non-English intact
    elif sys.platform == "darwin":
        cmd, data = ["pbcopy"], text.encode()
    else:
        cmd = next((c for c in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-ib"])
                    if shutil.which(c[0])), None)
        data = text.encode()
    if not cmd:
        return False
    subprocess.run(cmd, input=data, check=True)
    return True


def send(prompt):
    """Open ChatGPT with the prompt. Returns a status message for the user."""
    url = "https://chatgpt.com/?q=" + quote(prompt)
    if len(url) <= MAX_URL:
        webbrowser.open(url)
        return "Sent to ChatGPT."
    if copy_to_clipboard(prompt):
        webbrowser.open("https://chatgpt.com/")
        return "Answer too long for a link: it's on your clipboard. Press Ctrl+V, then Enter in ChatGPT."
    return "Answer too long for a link and no clipboard tool found (install wl-copy or xclip)."


def run(args, log_path):
    mode = next((a.lower() for a in args if a.lower() in MODES), "")
    n = next((int(a) for a in args if a.isdigit()), 1)
    pairs = exchanges(log_path)
    if not pairs:
        return "No Claude answer found yet in this session."
    if n < 1 or n > len(pairs):
        return f"Only {len(pairs)} answer(s) in this session."
    return send(build_prompt(*pairs[-n], mode))


def hook():
    """UserPromptSubmit hook: act only on the `gpt` keyword, then block it so it never reaches Claude."""
    data = json.loads(sys.stdin.buffer.read().decode("utf-8") or "{}")
    m = KEYWORD.match(data.get("prompt", ""))
    if not m:
        return 0  # not ours: stay silent, the prompt goes to Claude as normal
    log = data.get("transcript_path") or find_log(data.get("cwd") or Path.cwd())
    try:
        msg = run(m.group(1).split(), log)
    except Exception as e:  # never leave the user without feedback
        msg = f"gpt failed: {e}"
    sys.stderr.buffer.write(msg.encode("utf-8"))
    return 2  # exit code 2 = block the prompt, show stderr to the user


def settings_path():
    return CLAUDE_DIR / "settings.json"


def install(remove=False):
    path = settings_path()
    settings = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    script = Path(__file__).resolve().as_posix()
    groups = settings.setdefault("hooks", {}).setdefault("UserPromptSubmit", [])
    # drop any previous install of this tool (also makes install idempotent)
    for g in groups:
        g["hooks"] = [h for h in g.get("hooks", []) if "explain.py" not in h.get("command", "")]
    groups[:] = [g for g in groups if g.get("hooks")]
    if not remove:
        python = Path(sys.executable).as_posix()
        groups.append({"hooks": [{"type": "command", "command": f'"{python}" "{script}" --hook'}]})
    if not groups:
        del settings["hooks"]["UserPromptSubmit"]
    if not settings["hooks"]:
        del settings["hooks"]
    if path.exists():
        shutil.copy(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return f"{'Removed' if remove else 'Installed'} the gpt hook in {path} (backup: settings.json.bak)." + (
        "" if remove else " Restart Claude Code, then type `gpt` after any answer.")


def main(argv):
    if argv[:1] == ["--hook"]:
        return hook()
    if argv[:1] in (["--install"], ["--uninstall"]):
        print(install(remove=argv[0] == "--uninstall"))
        return 0
    print(run(argv, find_log(Path.cwd())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
