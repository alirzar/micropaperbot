"""Write the hook, the teaser text on each paper's card, with Gemini.

The prompt is scripts/summary_prompt.txt. Hooks are at most posting.hook_max_chars
long; when Gemini writes more, it's asked again rather than the text being cut off.
"""
import json

from pydantic import BaseModel

from common import gemini_generate, prompt_file, shorten

PROMPT = "summary_prompt.txt"  # in scripts/
ABSTRACT_CHARS = 4000
BATCH_SIZE = 20  # papers per request when writing many hooks at once
BATCH_ABSTRACT_CHARS = 2500
ONE_ONLY = "Return only the teaser text, nothing else."
FOR_EACH = (
    "Write one teaser for each paper below, following the rules above for each. Return a JSON list with "
    'exactly one {"id", "hook"} object per paper, using the IDs given.'
)


class Hook(BaseModel):
    id: str
    hook: str


def load_prompt(max_chars):
    return prompt_file(PROMPT).read_text(encoding="utf-8").strip().replace("{max_chars}", str(max_chars))


def make_hook(client, models, prompt, paper, max_chars):
    contents = f"{prompt}\n\nSOURCE: {paper['venue']}\nTITLE: {paper['title']}\nABSTRACT: {paper['abstract'][:ABSTRACT_CHARS]}"
    hook = ""
    for _ in range(3):
        hook = " ".join(gemini_generate(client, models, contents).split()).strip('"“”')
        if len(hook) <= max_chars:
            return hook
        contents += f'\n\nYour answer was {len(hook)} characters long: "{hook}"\nRewrite it in at most {max_chars} characters.'
    return shorten(hook, max_chars)  # still too long after three tries


def make_hooks(client, models, prompt, papers, max_chars):
    """Hooks for many papers, BATCH_SIZE per Gemini request: {pid: hook}. A paper Gemini leaves out,
    or whose hook is too long, is missing from the result, and gets its own make_hook later."""
    batch_prompt = prompt.replace(ONE_ONLY, "").strip() + "\n\n" + FOR_EACH
    config = {"response_mime_type": "application/json", "response_schema": list[Hook]}
    hooks = {}
    for i in range(0, len(papers), BATCH_SIZE):
        batch = {f"p{n}": p for n, p in enumerate(papers[i : i + BATCH_SIZE], 1)}
        listing = "\n\n".join(
            f"ID: {key}\nSOURCE: {p['venue']}\nTITLE: {p['title']}\nABSTRACT: {p['abstract'][:BATCH_ABSTRACT_CHARS]}"
            for key, p in batch.items()
        )
        try:
            items = json.loads(gemini_generate(client, models, f"{batch_prompt}\n\nPAPERS\n\n{listing}", config))
        except ValueError:  # a garbled reply: these papers get their hooks one by one later
            continue
        for item in items if isinstance(items, list) else []:
            p = batch.get(str(item.get("id"))) if isinstance(item, dict) else None
            hook = " ".join(str(item.get("hook", "")).split()).strip('"“”') if p else ""
            if hook and len(hook) <= max_chars:
                hooks[p["pid"]] = hook
    return hooks
