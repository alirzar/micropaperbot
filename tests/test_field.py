"""This bot's own field: its config, prompts, wording and sources, and a first digest with them.

The other tests run on a neuroscience config (tests/neuro_config.json), as their papers and topics
are neuroscience ones; this one runs on config.json itself. It works in a throwaway copy of the
project; Telegram, Gemini and PubMed are stand-ins.
"""
import atexit
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
WORK = Path(tempfile.mkdtemp(prefix="micropaperbot-field-"))  # a throwaway copy of the project
atexit.register(shutil.rmtree, WORK, ignore_errors=True)
for name in ("scripts", "assets"):
    shutil.copytree(PROJECT / name, WORK / name, ignore=shutil.ignore_patterns("__pycache__"))
shutil.copy(PROJECT / "config.json", WORK / "config.json")
(WORK / ".env").write_text("TELEGRAM_BOT_TOKEN=from-env\nTELEGRAM_CHAT_ID=111\nGEMINI_API_KEY=fake\n", encoding="utf-8")
for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "GEMINI_API_KEY", "DISCORD_BOT_TOKEN"):
    os.environ.pop(key, None)
sys.path.insert(0, str(WORK / "scripts"))

import bot as botmod  # noqa: E402
import catalog  # noqa: E402
import common  # noqa: E402
import digest  # noqa: E402
import explain  # noqa: E402
import fetch_papers  # noqa: E402
import field  # noqa: E402
import telegram_api  # noqa: E402
from generate_summaries import load_prompt as hook_prompt  # noqa: E402
from rank_papers import load_prompt as ranking_prompt  # noqa: E402
from store import DB_PATH, Store  # noqa: E402

failures = []
ADMIN, ANA = 111, 777


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        failures.append(what)


print("1. its config and prompts")
cfg = common.load_config()
check(DB_PATH == WORK.resolve() / "data" / "db" / "bot.db", "its database is in data/db/")
check(os.environ.get("TELEGRAM_BOT_TOKEN") == "from-env", "its keys come from .env")
check(cfg["name"] == "Microbiome Paper Bot", "its name")
check(common.prompt_file("ranking_prompt.txt") == WORK.resolve() / "scripts" / "ranking_prompt.txt", "its prompts are in scripts/")
check("microbiome and systems biology researchers" in ranking_prompt() and "neuroscien" not in ranking_prompt(), "scores for its field")
check("microbiome science" in hook_prompt(200) and "200 characters" in hook_prompt(200), "teasers for its field")
check("microbiome science" in common.prompt_file(explain.PROMPT).read_text(encoding="utf-8"), "summaries for its field")

print("2. its field")
f = field.field(cfg)
term = field.pubmed_filter(cfg)
check(f["name"] == "microbiome" and "bifidobacter*[tiab]" in term and "hippocamp*" not in term, "its own words for general journals")
check('"relevant": true if the paper is microbiome research' in field.relevance_check(cfg), "Gemini checks papers belong to its field")
check(field.field({}) == field.field(cfg) and field.pubmed_filter({}) == term, "without a field section, it's the same field")
neuro = json.loads((PROJECT / "tests" / "neuro_config.json").read_text(encoding="utf-8"))
check(field.field(neuro)["name"] == "neuroscience" and "hippocamp*[tiab]" in field.pubmed_filter(neuro), "and a config can set another")
keys = [s["key"] for s in catalog.sources(cfg) if s["base"]]
check(keys == ["biorxiv:microbiology", "pubmed:microbiome", "pubmed:gut microbes"], f"its own base sources: {keys}")
general = [s for s in catalog.sources(cfg) if s["broad"]]
check("Nature Communications" in [s["name"] for s in general], "and general journals filtered for its field")
check(len(cfg["topics"]) == 10 and all(len(t) == 2 and all(t) for t in cfg["topics"].values()), "10 topic areas, each with a description")
searched = []
fetch_papers.eutils = lambda path, api_key=None, **data: (searched.append(data.get("term", "")) or SimpleNamespace(
    json=lambda: {"esearchresult": {"idlist": [], "count": "0"}}, content=b"<x/>"))
fetch_papers.fetch_sources([s for s in general if s["name"] == "Nature Communications"], date(2026, 11, 1), date(2026, 11, 1),
                           cfg["sources"]["pubmed"], term)
check(searched and "milk oligosaccharide*" in searched[0] and "brain*" not in searched[0], "fetching a general journal uses those words")
check(catalog.journal_details.__defaults__[-1] == fetch_papers.FIELD_FILTER and "microbio*[tiab]" in fetch_papers.FIELD_FILTER,
      "checking an added journal uses them too")


# ---------- the bot, with stand-ins ----------
def fake_vector(text):
    v = np.zeros(768, dtype=np.float32)
    for word in re.findall(r"[a-z]+", text.lower()):
        if len(word) >= 4:
            v[int(hashlib.md5(word[:6].encode()).hexdigest(), 16) % 768] += 1.0
    return (v / (np.linalg.norm(v) or 1)).tolist()


class FakeGemini:
    def __init__(self):
        self.models, self.prompts = self, []

    def embed_content(self, *, model, contents, config=None):
        return SimpleNamespace(embeddings=[SimpleNamespace(values=fake_vector(c.parts[0].text)) for c in contents])

    def generate_content(self, *, model, contents, config=None):
        self.prompts.append(contents)
        items = re.findall(r"^ID: (p\d+)\nSOURCE: .*\nTITLE: (.*)$", contents, re.M)
        if config and "Hook" in str(config.get("response_schema")):
            return SimpleNamespace(text=json.dumps([{"id": i, "hook": f"Hook: {t[:40]}"} for i, t in items]))
        if config:
            return SimpleNamespace(text=json.dumps([{"id": i, "score": 7, "reason": "fake", "relevant": True} for i, _ in items]))
        return SimpleNamespace(text="Hook")


calls = []
telegram_api.call = lambda method, files=None, **params: (calls.append((method, params)) or {"message_id": len(calls)})
telegram_api.answer = lambda *a, **k: None
texts = lambda chat: [p.get("text") or p.get("caption") or "" for m, p in calls if p.get("chat_id") == chat]  # noqa: E731
gemini = FakeGemini()
store = Store()
bot = botmod.Bot(cfg, store, gemini)
bot.settings["backfill_days"] = 0


def message(uid, text, first="Ana"):
    bot.handle({"update_id": 1, "message": {"chat": {"type": "private"}, "from": {"id": uid, "first_name": first}, "text": text}})


def tap(uid, data):
    bot.handle({"update_id": 1, "callback_query": {"id": "cq", "from": {"id": uid}, "data": data, "message": {"message_id": 5}}})


print("3. talking about its field")
message(ANA, "/start")
check("new microbiome papers" in texts(ANA)[-1], f"a newcomer hears what it's about: {texts(ANA)[-1][:60]!r}")
tap(ADMIN, f"ok:{ANA}")
picker = [p for m, p in calls if p.get("chat_id") == ANA][-1]
labels = [b["text"] for row in picker["reply_markup"]["inline_keyboard"] for b in row]
check("Metabolic modeling" in labels and "Gut–brain axis" in labels and len(labels) == 11, "its own 10 areas, then Done")
tap(ANA, "topic:infant")
tap(ANA, "topics_done")
message(ANA, "Bifidobacterium, short-chain fatty acids")
check("Nature Communications or Frontiers in Microbiology" in texts(ANA)[-1] and "microbiome and early-life papers" in texts(ANA)[-1],
      "its sources text")
tap(ANA, "src_add")
check("<i>ISME J</i>" in texts(ANA)[-1], "its journal example")

print("4. papers from its sources")
PAPERS = [
    {"doi": f"10.1101/m{i}", "source": "biorxiv", "venue": "bioRxiv preprint", "src": "biorxiv:microbiology", "title": title,
     "authors": ["Lee"], "author_keys": ["lee k"], "date": "2026-11-10", "link": f"https://doi.org/10.1101/m{i}", "abstract": title, "license": None}
    for i, title in enumerate([
        "Bifidobacterium consumes human milk oligosaccharides in the infant gut",
        "Short-chain fatty acids from microbial cross-feeding",
        "Soil bacteria fix nitrogen in drought",
        "Gut microbiome maturation over the first year of life",
    ])
]
fetched = []
digest.fetch_sources = lambda sources, start, end, pubmed=None, topic_filter=None: (fetched.append(topic_filter) or ([dict(p) for p in PAPERS], []))
result = digest.daily_update(store, cfg, gemini)
check(result["new"] == 4 and fetched[-1] == term, "the daily update fetches with its field's words")
check(any("microbiome and systems biology researchers" in p and '"relevant": true if the paper is microbiome research' in p
          for p in gemini.prompts), "and scores with its field's prompt and check")
tap(ANA, "src_cancel")
tap(ANA, "src_done")
tap(ANA, "tz:12")
tap(ANA, "hour:9")
tap(ANA, "days_done")
tap(ANA, "count:3")
tap(ANA, "go")
cards = [p for m, p in calls if m == "sendPhoto" and p["chat_id"] == ANA]
check(len(cards) == 3 and "Bifidobacterium" in cards[0]["caption"], f"the first digest: {cards[0]['caption'][:60]!r}")
message(ANA, "/help")
check(texts(ANA)[-1].startswith("I send you a daily digest of new microbiome papers"), "its help, once set up")

print("\nALL OK" if not failures else f"\n{len(failures)} FAILED: {failures}")
raise SystemExit(1 if failures else 0)
