"""Score papers with Gemini: how good each one is, from 1 to 10, with a short reason.

The prompt is scripts/ranking_prompt.txt. The score is a small part of each person's ranking;
how well a paper matches their interests counts far more (see digest.py).
"""
import json

from pydantic import BaseModel

from common import gemini_generate, prompt_file

PROMPT = "ranking_prompt.txt"  # in scripts/
BATCH_SIZE = 20  # papers per Gemini request
ABSTRACT_CHARS = 1500  # enough to judge a paper, and keeps requests small


class Score(BaseModel):
    id: str
    score: int
    reason: str


class TopicScore(Score):
    relevant: bool  # is it in the bot's field at all? The public bot asks, for papers from general journals


def load_prompt():
    return prompt_file(PROMPT).read_text(encoding="utf-8").strip()


def score_papers(client, models, prompt, papers, schema=Score):
    """Returns {doi (lowercase): {"score": int, "reason": str}}, plus "relevant" with schema=TopicScore.
    Papers Gemini leaves out are missing."""
    scores = {}
    for i in range(0, len(papers), BATCH_SIZE):
        # Short IDs rather than DOIs, which a model can garble.
        batch = {f"p{n}": p for n, p in enumerate(papers[i : i + BATCH_SIZE], 1)}
        listing = "\n\n".join(
            f"ID: {pid}\nSOURCE: {p['venue']}\nTITLE: {p['title']}\nABSTRACT: {p['abstract'][:ABSTRACT_CHARS]}"
            for pid, p in batch.items()
        )
        for item in generate_scores(client, models, f"{prompt}\n\nPAPERS\n\n{listing}", schema):
            paper = batch.get(str(item.get("id")))
            if paper and isinstance(item.get("score"), int):
                scores[paper["doi"].lower()] = {
                    "score": max(1, min(10, item["score"])),
                    "reason": str(item.get("reason", "")).strip(),
                    **({"relevant": item["relevant"]} if isinstance(item.get("relevant"), bool) else {}),
                }
        missed = sum(1 for p in batch.values() if p["doi"].lower() not in scores)
        if missed:
            print(f"  Gemini left out {missed} of {len(batch)} papers in one request; they'll be retried next batch")
    return scores


def generate_scores(client, models, contents, schema=Score):
    config = {"response_mime_type": "application/json", "response_schema": list[schema], "temperature": 0.2}
    for _ in range(2):  # with a schema a garbled reply is rare, but worth one more try
        try:
            items = json.loads(gemini_generate(client, models, contents, config))
            if isinstance(items, list):
                return [x for x in items if isinstance(x, dict)]
        except ValueError:  # includes json.JSONDecodeError
            pass
    raise ValueError("Gemini's scores weren't a JSON list")
