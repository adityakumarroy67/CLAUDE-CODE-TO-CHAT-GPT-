# gpt — explain Claude Code's answer in ChatGPT

Claude Code gave you a long, technical answer? Type `gpt`. ChatGPT opens in your browser with your
question and Claude's answer already sent, and explains it in plain words. Ask follow-ups there.

Free, no API key, nothing to install except Python 3.

## Install

1. On this GitHub page, click **Code → Download ZIP** and unzip it somewhere it can stay
   (the hook points to this folder — if you move it, run the install again).
2. Open a terminal in that folder and run:

```
python explain.py --install
```

3. Restart Claude Code. This adds one hook to `~/.claude/settings.json` (a backup is saved next to it).
Remove it any time with `python explain.py --uninstall`.

## Use (inside Claude Code)

| Type | Gets you |
|---|---|
| `gpt` | simple explanation of the last answer |
| `gpt eli5` | explain like I'm 12 |
| `gpt tldr` | 2–3 bullet points |
| `gpt steps` | a to-do checklist |
| `gpt 2` | the 2nd-latest answer (combine: `gpt eli5 2`) |

The `gpt` message never reaches Claude, so it costs no Claude usage.
Without the hook you can also run `python explain.py [mode] [N]` in a project folder.

## Good to know

- You must be logged in to chatgpt.com in your default browser.
- Very long answers don't fit in a link: they're copied to your clipboard instead and ChatGPT opens —
  press **Ctrl+V** (Cmd+V on Mac), then **Enter**.
- Link limit is 8000 characters; change it with the `GPT_MAX_URL` environment variable.
- Common API keys (OpenAI, GitHub, AWS, Google, Slack, private keys) are replaced with `[hidden secret]`
  before sending. Anything else in the answer — code, file paths — goes to OpenAI.
- Linux needs `wl-copy`, `xclip` or `xsel` for the clipboard fallback.

## Test

```
python test_explain.py
```

License: MIT
