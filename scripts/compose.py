"""The text around a paper: who and where it's from, its card's caption, and posts ready to copy."""
import html

from common import shorten

X_LIMIT = 280  # characters in a post on X; Bluesky allows 300


def byline(authors):
    if not authors:
        return None
    if len(authors) == 1:
        return authors[0]
    if len(authors) == 2:
        return f"{authors[0]} and {authors[1]}"
    return f"{authors[0]} et al."


def attribution(d):
    """'Smith et al. · Microbiome'"""
    return " · ".join(x for x in (byline(d.get("authors")), d.get("venue")) if x)


def copy_versions(d, hashtag):
    """Posts to paste by hand, link included: one short enough for X and Bluesky, a longer one for anywhere else."""
    hook = (d.get("hook") or "").strip() or d["title"]
    short_tail = f"\n\n{attribution(d)}\n{d['link']}" + (f"\n{hashtag}" if hashtag else "")
    short = shorten(hook, X_LIMIT - len(short_tail)) + short_tail
    long = f"{hook}\n\n📄 {d['title']}\n{attribution(d)}\n{d['link']}" + (f"\n\n{hashtag}" if hashtag else "")
    return short, long


def copy_message(d, hashtag):
    """Telegram message (HTML) with both versions in code blocks, which Telegram copies with a tap."""

    def e(text):
        return html.escape(text, quote=False)

    short, long = copy_versions(d, hashtag)
    return (
        "📋 <b>Ready to copy</b>\n\n"
        f"<b>X and Bluesky</b>\n<pre>{e(short)}</pre>\n\n"
        f"<b>LinkedIn and others</b>\n<pre>{e(long)}</pre>"
    )


def channel_post(d, hashtag):
    """A paper card's caption (HTML): the hook, then the paper."""

    def e(text):
        return html.escape(text, quote=False)

    hook = shorten((d.get("hook") or "").strip(), 400)
    parts = [e(hook)] if hook else []
    parts.append(f"<b>{e(d['title'])}</b>\n{e(attribution(d))}\n{e(d['link'])}")
    if hashtag:
        parts.append(e(hashtag))
    return "\n\n".join(parts)
