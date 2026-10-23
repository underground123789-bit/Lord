"""
Optional "Ask AI" support using Claude (Anthropic API).

Only used when the user saves an API key in Settings (or sets ANTHROPIC_API_KEY).
Everything else in CMD Helper works offline without it.
"""

import os
import platform

DEFAULT_MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are a Windows troubleshooting expert inside "CMD Helper", a desktop tool \
that helps people fix Windows problems: installation errors, update errors, blue screens, \
drivers, network, disk, boot, activation, CMD and PowerShell usage.

The user pastes an error message or describes a problem. They may write in English, Arabic, \
or Lebanese Arabizi (Arabic written with Latin letters and numbers, e.g. "ma 3am yemshi" = \
"it's not working"). Reply in the same language and style the user wrote in; for Arabizi, \
reply in Arabizi.

How to answer:
- Start with one or two sentences on what the error means and its most likely cause.
- Then give numbered steps, easiest and safest first. Put every command in its own \
```cmd code block (or ```powershell when it is PowerShell) so it can be copied directly.
- Say when a command needs CMD as Administrator.
- Before anything that can delete data (format, diskpart clean, deleting partitions, \
registry deletes) give a clear warning and suggest a backup.
- Never suggest downloading single DLL files from DLL websites, cracked software, or \
disabling security permanently.
- If the message is too vague to diagnose, give the most common fixes and ask for the \
exact error text or code.
Keep it practical and concise."""


def system_context():
    """A short description of this PC, sent along so answers fit the user's Windows."""
    try:
        return f"User's system: {platform.platform()} ({platform.machine()})"
    except Exception:
        return ""


class AIError(Exception):
    pass


def ask(api_key, messages, on_text, model=DEFAULT_MODEL):
    """Stream Claude's answer for the conversation `messages`.

    Calls on_text(chunk) for each piece of text as it arrives and returns the
    final assistant content blocks, to be appended to `messages` unchanged.
    Raises AIError with a readable message on failure.
    """
    try:
        import anthropic
    except ImportError:
        raise AIError("The 'anthropic' package is not installed (pip install anthropic).")

    client = anthropic.Anthropic(api_key=api_key or None)
    system = SYSTEM_PROMPT
    ctx = system_context()
    if ctx:
        system += "\n\n" + ctx
    try:
        with client.beta.messages.stream(
            model=model,
            max_tokens=16000,
            system=system,
            messages=messages,
            output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        ) as stream:
            for text in stream.text_stream:
                on_text(text)
            final = stream.get_final_message()
    except anthropic.AuthenticationError:
        raise AIError("Your API key is not valid. Check it in Settings.")
    except anthropic.PermissionDeniedError:
        raise AIError("This API key is not allowed to use this model.")
    except anthropic.NotFoundError:
        raise AIError(f"Model '{model}' was not found. Check the model name in Settings.")
    except anthropic.RateLimitError:
        raise AIError("Too many requests or no credit left on the account. Try again in a minute.")
    except anthropic.BadRequestError as e:
        raise AIError(f"Request rejected: {e.message}")
    except anthropic.APIStatusError as e:
        raise AIError(f"Claude API error ({e.status_code}). Try again later.")
    except anthropic.APIConnectionError:
        raise AIError("No internet connection (or the API can't be reached).")
    if final.stop_reason == "refusal":
        raise AIError("The AI declined to answer this request.")
    if final.stop_reason == "max_tokens":
        on_text("\n\n[answer was cut off - ask a follow-up to continue]")
    return final.content


def key_from_env():
    return os.environ.get("ANTHROPIC_API_KEY", "")
