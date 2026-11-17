"""What a bot is about: its field's name and wording, the words that pick its papers out of general
journals, and Gemini's check that a paper belongs to the field.

The "field" section of config.json sets them; these are the fallbacks. The bot's prompts are
scripts/ranking_prompt.txt, summary_prompt.txt and explain_prompt.txt.
"""
from fetch_papers import FIELD_WORDS

DEFAULTS = {
    "name": "microbiome",  # "a daily digest of new microbiome papers"
    "papers": "microbiome and early-life papers",  # what general journals contribute
    "general_examples": "Nature Communications or Frontiers in Microbiology",
    "journal_example": "ISME J",  # how PubMed abbreviates a journal in this field
    "check": "it studies microbes or microbial communities (such as the gut microbiome), their genomes or metabolism, "
    "how they interact with their hosts, or maternal and child health and early-life development",
    "not_like": 'such as plant science, environmental chemistry or materials science, even when it uses words like "culture" or "colony"',
    "filter_words": FIELD_WORDS,  # PubMed title/abstract words; generous on purpose: Gemini makes the final call
}


def field(cfg):
    return {**DEFAULTS, **cfg.get("field", {})}


def pubmed_filter(cfg):
    """The PubMed search that picks this field's papers out of a general journal."""
    return " OR ".join(f"{word}[tiab]" for word in field(cfg)["filter_words"])


def relevance_check(cfg):
    """What the scoring prompt adds, so Gemini also says whether each paper belongs to this field."""
    f = field(cfg)
    return (
        f'\n\nALSO: give each object a fourth field, "relevant": true if the paper is {f["name"]} research, '
        f'meaning {f["check"]}; false if it belongs to another field ({f["not_like"]}).'
    )
