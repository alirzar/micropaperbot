"""Fetch new papers from bioRxiv, medRxiv and PubMed.

All free public APIs:
  bioRxiv, medRxiv  api.biorxiv.org: one subject category each, first versions only (no revisions)
  PubMed            NCBI E-utilities: chosen journals, by the date added to PubMed

Every paper comes back in one shape:
  {doi, source, venue, src (which source, like "pubmed:microbiome"), title, authors (last names),
   author_keys ('smith j', for author alerts), date, link, abstract, license}
"""
import os
import threading
import time
import xml.etree.ElementTree as ET

import requests

from common import author_key, clean_text, name_key

BIORXIV = "https://api.biorxiv.org/details/{server}/{start}/{end}/{cursor}"
PREPRINTS = {"biorxiv": "bioRxiv", "medrxiv": "medRxiv"}  # the servers api.biorxiv.org covers
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TIMEOUT = 60
TRIES = 3  # tries per page from bioRxiv's API, which now and then drops a connection or times out
RETRY_WAIT = 5  # seconds before the second try, twice that before the third

# Words in a title or abstract that mark a paper as being in the field (the "field" section of
# config.json has the same list; these are only the fallback). Used for journals that publish far
# beyond it; generous on purpose, as Gemini makes the final call.
FIELD_WORDS = [
    "microbio*", "microbiom*", "microbiota*", "bacteri*", "metagenom*", "metabolom*", '"metabolic model*"',
    '"flux balance"', '"constraint-based"', '"genome-scale"', "bifidobacter*", "lactobacill*",
    '"short-chain fatty"', "butyrate", '"milk oligosaccharide*"', "probiotic*", "prebiotic*", "dysbiosis",
    "commensal*", '"cross-feeding"', '"gut-brain"', "breastfe*", '"human milk"', "infant*", "maternal",
    "pregnan*", "neurodevelopment*",
]
FIELD_FILTER = " OR ".join(f"{word}[tiab]" for word in FIELD_WORDS)

session = requests.Session()
session.headers["User-Agent"] = "micropaperbot/0.1"
_ncbi_lock = threading.Lock()
_ncbi_last = [0.0]


def eutils(path, api_key=None, **data):
    """POST to an NCBI E-utility, at most 3 requests a second (10 with a key), even across threads."""
    gap = 0.11 if api_key else 0.34
    data = {"tool": "micropaperbot", **data, **({"api_key": api_key} if api_key else {})}
    for attempt in range(3):
        with _ncbi_lock:
            time.sleep(max(0.0, _ncbi_last[0] + gap - time.monotonic()))
            _ncbi_last[0] = time.monotonic()
        resp = session.post(f"{EUTILS}/{path}", data=data, timeout=TIMEOUT)
        if resp.status_code != 429:  # too many requests: wait a moment and try again
            break
        time.sleep(1 + attempt)
    resp.raise_for_status()
    return resp


def pubmed_count(term, api_key=None):
    """How many PubMed records match a search."""
    found = eutils("esearch.fcgi", api_key, db="pubmed", term=term, retmode="json", retmax=0).json()
    return int(found["esearchresult"]["count"])


def biorxiv_page(url, params):
    """One page from bioRxiv's API. It now and then drops a connection, times out or has a server error,
    and one failed page costs the whole source for that update, so each page gets a few tries."""
    for attempt in range(TRIES):
        try:
            resp = session.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError, requests.HTTPError) as exc:
            on_their_side = not isinstance(exc, requests.HTTPError) or exc.response is None or exc.response.status_code >= 500
            if not on_their_side or attempt == TRIES - 1:
                raise
            time.sleep(RETRY_WAIT * (attempt + 1))


def fetch_biorxiv(start, end, category, server="biorxiv"):
    """First versions posted in one category of bioRxiv or (with server="medrxiv") medRxiv."""
    papers, cursor, total = [], 0, 1
    while cursor < total:
        data = biorxiv_page(BIORXIV.format(server=server, start=start, end=end, cursor=cursor), {"category": category})
        msg = (data.get("messages") or [{}])[0]
        page = data.get("collection") or []
        if msg.get("status") != "ok" or not page:
            break  # "no posts found" for an empty window
        total = int(msg.get("total") or 0)
        cursor += len(page)  # the API returns 30 records per page
        for p in page:
            if str(p.get("version")) == "1":  # later versions are revisions of older preprints
                papers.append(biorxiv_record(p, server))
    return papers


def biorxiv_record(p, server="biorxiv"):
    """One record from the bioRxiv (or medRxiv) API, in the shape every paper has."""
    return {
        "doi": p["doi"],
        "source": server,
        "venue": f"{PREPRINTS.get(server, server)} preprint",
        "src": f"{server}:{(p.get('category') or '').strip().lower()}",
        "title": clean_text(p.get("title")),
        "authors": biorxiv_authors(p.get("authors")),
        "author_keys": [name_key(part) for part in (p.get("authors") or "").split(";") if part.strip()],
        "date": p.get("date"),
        "link": f"https://doi.org/{p['doi']}",
        "abstract": clean_text(p.get("abstract")),
        "license": p.get("license"),
    }


def biorxiv_authors(field):
    """'Smith, J. A.; Doe, B.' -> ['Smith', 'Doe']"""
    names = [part.split(",")[0].strip() for part in (field or "").split(";")]
    return [n for n in names if n]


def fetch_journals(start, end, journals, general, names, exclude_types, email=None, api_key=None, topic_filter=FIELD_FILTER):
    """Papers from PubMed journals, given as abbreviations (its [ta] field): everything from `journals`,
    and from `general` ones only the papers `topic_filter` finds (the field's own),
    which come back marked "broad". names maps abbreviations to the names shown on cards."""
    groups = []
    if journals:
        groups.append(" OR ".join(f'"{abbr}"[ta]' for abbr in journals))
    if general:
        groups.append("(" + " OR ".join(f'"{abbr}"[ta]' for abbr in general) + f") AND ({topic_filter})")
    if not groups:
        return []
    term = " OR ".join(f"({g})" for g in groups)
    window = f"{start:%Y/%m/%d}:{end:%Y/%m/%d}[edat]"
    papers = search_pubmed(f"({term}) AND hasabstract AND {window}", names, exclude_types, email, api_key)
    wide = {f"pubmed:{abbr.lower()}" for abbr in general}
    for p in papers:
        p["broad"] = p["src"] in wide
    return papers


def search_pubmed(term, journals, exclude_types, email=None, api_key=None):
    """Papers matching any PubMed search, such as an author's name; journals names the venues it knows."""
    params = {"db": "pubmed", **({"email": email} if email else {})}
    found = eutils("esearch.fcgi", api_key, **params, term=term, retmode="json", retmax=5000).json()
    ids = found["esearchresult"]["idlist"]

    names = {abbr.lower(): name for abbr, name in journals.items()}
    papers = []
    for i in range(0, len(ids), 200):
        resp = eutils("efetch.fcgi", api_key, **params, id=",".join(ids[i : i + 200]), retmode="xml")
        for article in ET.fromstring(resp.content).iter("PubmedArticle"):
            paper = pubmed_paper(article, names, exclude_types)
            if paper:
                papers.append(paper)
    return papers


def pubmed_paper(article, names, exclude_types):
    citation = article.find("MedlineCitation")
    art = citation.find("Article")
    types = {t.text for t in art.iterfind("PublicationTypeList/PublicationType")}
    if types & exclude_types:
        return None
    abstract = clean_text(" ".join(text_of(p) for p in art.iterfind("Abstract/AbstractText")))
    doi = pubmed_doi(article)
    if not abstract or not doi:
        return None  # nothing to rank or hook without an abstract, nothing to link without a DOI
    abbr = citation.findtext("MedlineJournalInfo/MedlineTA") or art.findtext("Journal/ISOAbbreviation") or ""
    people = list(art.iterfind("AuthorList/Author"))
    authors = [clean_text(a.findtext("LastName") or a.findtext("CollectiveName")) for a in people]
    keys = [author_key(a.findtext("LastName"), a.findtext("ForeName") or a.findtext("Initials") or "") for a in people if a.findtext("LastName")]
    return {
        "doi": doi,
        "source": "pubmed",
        "venue": names.get(abbr.lower(), abbr),
        "src": f"pubmed:{abbr.lower()}",
        "title": clean_text(text_of(art.find("ArticleTitle"))).rstrip("."),
        "authors": [a for a in authors if a],
        "author_keys": keys,
        "date": entrez_date(article),
        "link": f"https://doi.org/{doi}",
        "abstract": abstract,
        "license": None,
        "pmid": citation.findtext("PMID"),
    }


def text_of(el):
    return "".join(el.itertext()) if el is not None else ""


def pubmed_doi(article):
    for el in article.iterfind("PubmedData/ArticleIdList/ArticleId"):
        if el.get("IdType") == "doi" and el.text:
            return el.text.strip()
    for el in article.iterfind("MedlineCitation/Article/ELocationID"):
        if el.get("EIdType") == "doi" and el.text:
            return el.text.strip()
    return None


def entrez_date(article):
    d = article.find("PubmedData/History/PubMedPubDate[@PubStatus='entrez']")
    if d is None:
        return None
    return f"{d.findtext('Year')}-{int(d.findtext('Month')):02d}-{int(d.findtext('Day')):02d}"


def fetch_sources(sources, start, end, pubmed=None, topic_filter=FIELD_FILTER):
    """Papers from a list of sources (see catalog.py) for the window, one entry per DOI.

    pubmed is config.json's sources.pubmed, for exclude_types and email; topic_filter picks the
    field's papers out of general journals. Returns (papers, errors).
    """
    pubmed = pubmed or {}
    papers, errors = [], []
    for s in sources:
        if s["kind"] in PREPRINTS:
            try:
                papers += fetch_biorxiv(start, end, s["query"], server=s["kind"])
            except Exception as exc:
                errors.append(f"{s['name']}: {exc}")
    journals = [s for s in sources if s["kind"] == "pubmed"]
    if journals:
        try:
            papers += fetch_journals(
                start,
                end,
                [s["query"] for s in journals if not s["broad"]],
                [s["query"] for s in journals if s["broad"]],
                {s["query"]: s["name"] for s in journals},
                set(pubmed.get("exclude_types", [])),
                pubmed.get("email") or None,
                os.getenv("NCBI_API_KEY"),
                topic_filter,
            )
        except Exception as exc:
            errors.append(f"PubMed: {exc}")
    return one_per_doi(papers), errors


def one_per_doi(papers):
    unique = {}
    for p in papers:
        unique.setdefault(p["doi"].lower(), p)
    return list(unique.values())
