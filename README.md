# Microbiome Paper Bot

A Telegram and Discord bot that sends each person a daily digest of new microbiome and early-life papers from bioRxiv, medRxiv and the journals they choose, matched to their interests with Gemini. People can also search recent papers, save them, follow authors and ask for plain-language summaries. It runs on a computer that stays on, such as a lab server.

It's the same bot as [neuropaperbot](https://github.com/alirzar/neuropaperbot), which does this for neuroscience, with its own sources, topic areas and Gemini prompts. Both are based on [oecs-bot](https://github.com/mcfrank/oecs-bot) by Michael Frank (MIT license).

## What it does

[`scripts/bot.py`](scripts/bot.py) keeps running and talks to everyone who uses it, on Telegram or, once you [add it to Discord](#add-it-to-discord), on Discord:

- **Joining:** someone sends `/start`, and you get **✅ Approve / ❌ Deny**. Once approved, they pick from 10 areas, describe their interests in their own words, choose their sources, and pick a time zone, an hour, the days of the week, and how many papers they want each time (1 to 10, three to start with). Then they see a summary of their choices, can change any part, and tap **✅ Start my digest**: nothing is sent before that. `/settings` shows the same summary anytime.
- **A digest** at their hour, on the days they pick (every day to start with): the papers that suit them best and that they haven't seen yet, from the past week, or from as far back as they choose with `/range`: 2 weeks, a month, 2 months, and 6 months or a year once the bot has [filled in that far](#going-back-a-year). Each comes as a card with **👍 / 👎** (which tune later picks), **💾 Save**, **📃 Abstract** (the whole abstract as text: the card only has room for its start), **📄 Summary**, **📋 Copy** and **🔗 Similar** (the 5 closest recent papers). A 💡 line on each card says why it was picked: the interest it matched, and whether it came from their sources. A **➡️ 3 more** button under the digest brings the next papers on their list, up to 5 times a day.
- **Sources:** `/sources` lists where papers come from: bioRxiv and medRxiv sections, microbiology and microbiome journals, and general journals such as Nature Communications, PNAS and Frontiers in Microbiology, from which only the microbiome and early-life papers come. Nothing is ticked to start with: each person ticks the ones they want, or none. **➕ Add a journal** takes any journal PubMed indexes, by name, abbreviation or ISSN. The bot checks that it published in the past year, and then offers it to everyone.
- **On request:** `/find <topic>` searches the last 60 days of papers. Pasting a DOI or a bioRxiv or medRxiv link gets a plain-language summary. `/popular` shows this week's papers that at least two people gave 👍 or saved, as counts without names. `/export` sends someone's saved papers as a citation file for Zotero, EndNote or Mendeley (`/export bibtex` for LaTeX), with full details from Crossref.
- **Alerts:** `/follow <name>` sends a message when that author publishes, in any PubMed journal or on bioRxiv. `/watch <topic>` sends one the day a new paper mentions that topic or is among the week's closest matches to it, up to 3 a day.
- **Commands:** `/digest`, `/find`, `/popular`, `/saved`, `/export`, `/follow`, `/following`, `/unfollow`, `/watch`, `/watching`, `/unwatch`, `/topics`, `/keywords`, `/sources`, `/time`, `/days`, `/range`, `/settings`, `/privacy` and `/stop`; and for you, `/users` and `/stats` (people, papers, reactions and Gemini use over the past week).

**How it picks papers.** Every morning at 07:00 UTC it fetches new papers from the base sources (`sources` in `config.json`) and from every source someone has ticked. A source nobody had is fetched right away, the moment someone ticks it. Gemini turns each paper, and each person's topics and keywords, into a "fingerprint" (an embedding), so that similar subjects get similar fingerprints. A person's digest starts with the papers from the sources they ticked, over the past week or the range they chose, closest to their interests first, nudged toward papers like the ones they gave 👍, away from the 👎 ones, and slightly by Gemini's quality score. When those run out, the best matches from every other source follow, and someone who ticks nothing gets the best matches from everything. From general journals, PubMed sends only papers whose title or abstract uses the field's words (microbes and microbiomes, metabolic models, infants, pregnancy and so on: `field.filter_words` in `config.json`), and Gemini then sets aside any that aren't really in the field, such as a materials paper on antibacterial coatings. Gemini works per paper, not per person, so costs grow with the number of papers rather than people. Summaries are the exception, which is why each person gets 10 a day (you have no limit).

<a id="going-back-a-year"></a>**Going back a year.** Besides each day's new papers, the bot fills in the past year in the background: a week of older papers at a time, from every source it fetches, at most 500 fingerprints a day (`bot.backfill_per_day`), so the daily update and people's searches keep their share of Gemini's free tier. That's about two weeks of history a day, so `/range` offers **6 months** after about two weeks and **a year** after about a month. Older papers count from their own dates, so they only show for ranges that reach that far; they get quality scores but no teasers until someone is sent one, and they never trigger author or topic alerts. `/stats` shows how far back the bot has got.

**Privacy.** People's data stays in `data/db/bot.db` on the computer running the bot and is never committed to git: their Telegram or Discord name and ID, their interests and sources, what they were sent, and their 👍/👎, saves, follows and watched topics. Journals people add are kept without their names, and `/popular` shows counts, never who. `/privacy` tells people this, and `/stop` deletes everything about them.

## Set it up

You need a Telegram bot and a Gemini API key.

1. In Telegram, ask **@BotFather** for a new bot (`/newbot`). It gives you a token.
2. Create a Gemini API key at [Google AI Studio](https://aistudio.google.com/apikey). Gemini's free-tier limits count per Google Cloud project, so give this bot a key from a project of its own, not one another bot already uses.
3. Copy `.env.example` to `.env` and fill it in:
   - `TELEGRAM_BOT_TOKEN`: the token from step 1.
   - `GEMINI_API_KEY`: the key from step 2.
   - `TELEGRAM_CHAT_ID`: your own Telegram ID, which makes you the admin who approves people. It's the same number for every bot, so if you run neuropaperbot, copy it from there. Otherwise, send the new bot any message, then run `python scripts/telegram_api.py` to see it.
   - Optional: `DISCORD_BOT_TOKEN` ([Discord](#add-it-to-discord)) and `NCBI_API_KEY` (lets PubMed answer faster).
4. Install it and start it:

   ```
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt       # on Windows: .venv\Scripts\pip
   .venv/bin/python scripts/bot.py
   ```

   Send your new bot `/start` to set up your own digest. Its first paper update starts right away and takes a minute or two. Stop the bot with **Ctrl+C**.
5. Optional, with @BotFather: `/setuserpic` (use `assets/logo.png`), `/setdescription`, `/setjoingroups` → **Disable**, and `/setcommands` with the list below, so the commands show up in Telegram's menu.

```
digest - Today's papers, now
find - Search recent papers
saved - Papers you saved
follow - Get a message when an author publishes
following - Authors you follow
unfollow - Stop following an author
watch - Get a message when a new paper is on a topic
watching - Topics you watch
unwatch - Stop watching a topic
popular - This week's most liked and saved papers
export - Your saved papers as a file for Zotero
topics - The areas you follow
keywords - Your interests in your own words
sources - The journals and preprints you get
time - When your digest arrives
days - Which days your digest comes
range - How far back your papers go
settings - Your choices, and changing them
privacy - What the bot keeps
stop - Delete your data
help - What the bot can do
```

### Add it to Discord

The same program also runs the bot on Discord, for people without Telegram. Everyone shares one database and one daily paper update, so Discord adds no Gemini cost beyond each person's own summaries and searches.

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications), click **New Application**, and name it (for example *Microbiome Paper Digest*). Make a new one rather than reusing another bot's: one Discord bot can't be run by two programs. You can upload `assets/logo.png` as its icon.
2. On the **Bot** page, click **Reset Token**, copy the token, and paste it into `.env` as `DISCORD_BOT_TOKEN=...`. On the same page, turn off **Public Bot**, so only you can add it to servers. It needs none of the "privileged intents".
3. Discord only lets a bot message people who share a server with it, so the bot needs a server. Make one (in Discord: **+** → **Create My Own**), or use one you run.
4. Restart the bot. Its log shows a link starting with `https://discord.com/oauth2/authorize`: open it and add the bot to your server. The bot sets up its slash commands by itself.
5. Share the server's invite link. People join, find the bot in the member list, and send it a message or `/start`. You approve them in Telegram, as for everyone else.

On Discord, everything happens in a direct message with the bot, with the same setup, digest, buttons and commands. Lists with many choices (areas, sources, time zones) are dropdown menus, since Discord allows at most 25 buttons on a message. If someone leaves the server, the bot can no longer message them: their digest is skipped, and the log says so.

### Run it on a server

Any Linux machine that stays on and can reach the internet will do. It doesn't need open ports or a web address, because the bot fetches its messages from Telegram and Discord. If the server is a shared cluster with a job scheduler (such as SLURM), ask first: those often stop long-running programs.

**1. Install it**, here with conda. If neuropaperbot already runs on the server, skip the two `conda` lines and use its environment: they need the same packages.

```
git clone https://github.com/alirzar/micropaperbot.git
cd micropaperbot
conda create -n micropaperbot python=3.12 -y
conda activate micropaperbot
pip install -r requirements.txt
which python      # note this path: step 3 needs it
```

**2. Add your settings.** Create `.env` on the server as in [Set it up](#set-it-up), then `chmod 600 .env` so only you can read it. Don't send `.env` by email: it holds your keys. If the bot already ran on your computer, stop it there first (two copies can't run at once), and copy its database to keep everyone's setup:

```
ssh YOUR_USERNAME@SERVER "mkdir -p micropaperbot/data/db"
scp data/db/bot.db YOUR_USERNAME@SERVER:micropaperbot/data/db/bot.db
```

On the server, check that the bot starts with `python scripts/bot.py`, then stop it with Ctrl+C.

**3. Keep it running.** Without admin rights, use [`scripts/run_bot.sh`](scripts/run_bot.sh). It restarts the bot whenever it stops, and cron starts the script again after the server restarts. Run `crontab -e` and add this line, with your Python path from step 1:

```
*/10 * * * * PYTHON=/path/to/envs/micropaperbot/bin/python flock -n $HOME/.micropaperbot.lock $HOME/micropaperbot/scripts/run_bot.sh
```

Within 10 minutes the bot is running. Its log is `logs/bot.log`, which you can follow with `tail -f logs/bot.log`. To stop the bot for good, delete that line with `crontab -e`, then run `pkill -f micropaperbot/scripts/run_bot.sh; pkill -f micropaperbot/scripts/bot.py`.

**Updating it:** `git pull`, then `pkill -f micropaperbot/scripts/bot.py`; it starts again within 30 seconds. That restarts only this bot. neuropaperbot's own restart, `pkill -f scripts/bot.py`, matches both bots, which does no harm: each starts again on its own.

With admin rights, a systemd service does the same job. Save this as `/etc/systemd/system/micropaperbot.service`, with your own username, folder and Python path:

```
[Unit]
Description=Microbiome Paper Bot
After=network-online.target

[Service]
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/micropaperbot
ExecStart=/path/to/envs/micropaperbot/bin/python scripts/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Start it with `sudo systemctl enable --now micropaperbot`, and follow its log with `journalctl -u micropaperbot -f`.

Back up `data/db/bot.db` now and then: it's the only copy of everyone's settings.

## Settings

In `config.json`:

| Key | What it does |
|---|---|
| `name` | The bot's name, shown on each paper's card |
| `field.name`, `field.papers` | How the bot names its field: "a daily digest of new **microbiome** papers", and "you only get the **microbiome and early-life papers**" from a general journal |
| `field.general_examples`, `field.journal_example` | Examples in `/sources`: two general journals, and a journal abbreviation for **➕ Add a journal** |
| `field.filter_words` | Words that pick the field's papers out of general journals, searched in titles and abstracts on PubMed. They also decide whether a journal someone adds counts as general: it does when fewer than 60% of its papers use them. |
| `field.check`, `field.not_like` | What Gemini checks a paper from a general journal is about, and examples of what isn't |
| `bot.approval` | `true`: you approve each new person. `false`: anyone can join. |
| `bot.update_hour_utc` | When (UTC) the daily paper update runs. It's 07:00, an hour after neuropaperbot's, so the two don't query PubMed at the same time if they share a server. |
| `bot.papers_per_digest` | Papers per digest, until someone picks their own with `/settings` |
| `bot.recent_days` | How far back each daily update looks, and how far back digests reach unless someone picks a longer `/range` |
| `bot.search_days`, `bot.keep_days` | How far back `/find` looks, and when old papers are forgotten (saved ones are kept). `/range` never offers more than `keep_days`. |
| `bot.backfill_days`, `bot.backfill_per_day` | How far back to fill in older papers (0 turns it off), and how many fingerprints a day it may use |
| `bot.summaries_per_day`, `bot.searches_per_day` | Daily limits per person (searches include journal searches); you have none |
| `bot.more_per_day` | How many times a day each person can tap **➡️ more**; you have no limit |
| `bot.follows_per_person`, `bot.watches_per_person` | The most authors one person can follow, and topics they can watch |
| `sources` | The base sources: fetched every day whether or not anyone ticks them, so there are always papers to choose from. `sources.pubmed.journals` uses PubMed's abbreviation for each journal (the "NLM Title Abbreviation" in the [NLM Catalog](https://www.ncbi.nlm.nih.gov/nlmcatalog/journals)). |
| `sources.pubmed.exclude_types` | PubMed publication types to skip, such as errata and editorials |
| `sources.pubmed.email` | An email address NCBI may contact about heavy use. Optional, and sent with every PubMed request, so leave it empty in a public repository. |
| `more_sources` | The other sources `/sources` offers: `preprints` as `"server:category"` (bioRxiv or medRxiv), `journals` by PubMed abbreviation, and `general_journals`, from which only the field's papers come |
| `topics` | The areas offered at setup: each has a label, and the description its fingerprint is made from |
| `posting.hook_max_chars` | The longest teaser Gemini may write for a card |
| `posting.hashtag` | The hashtag at the end of the **📋 Copy** text, or `null` for none |
| `gemini.model`, `gemini.fallback_model` | The Gemini models for scores, teasers and summaries; the fallback is used when the main one is overloaded |
| `gemini.embedding_model` | The Gemini model that makes the fingerprints |

To see how the bot would treat a journal, `python scripts/catalog.py "gut microbes"` lists the journals PubMed finds for that name, with how many papers each publishes a month, and whether it counts as general.

The wording Gemini works from is in `scripts/`:

| File | What it writes |
|---|---|
| `ranking_prompt.txt` | Each paper's quality score, which nudges the ranking |
| `summary_prompt.txt` | The teaser at the top of each card |
| `explain_prompt.txt` | **📄 Summary**: the question, what they did, what they found, and why it matters |

The card's colors are at the top of `scripts/card.py`; `python scripts/card.py --title "A title"` saves a sample in `previews/`.

## Tests

```
python tests/run_all.py
```

Each test works in a throwaway copy of the project with its own database, so your data is never touched. Telegram, Discord, Gemini, PubMed and the preprint servers are replaced by stand-ins, so no keys are needed. Run them after changing the code, and before moving the bot to a server.

| Test | What it covers |
|---|---|
| `test_field.py` | This bot's field: its config, prompts, wording and sources, and a first digest with them |
| `test_bot.py` | The bot on Telegram: joining, setup and its summary, digests and **➡️ more**, sources and adding journals, summaries, search, author alerts and the daily schedule |
| `test_discord.py` | The same bot on Discord: its format, dropdowns, slash commands, and one person from joining to leaving |
| `test_quota.py` | Gemini's free-tier limits, and the daily update carrying on where it stopped |
| `test_backfill.py` | Filling in older papers: a week at a time, within the daily budget, with their own dates |

The code is the same for any field. All tests but `test_field.py` were written with neuroscience papers and topics, so they run on a neuroscience config, [`tests/neuro_config.json`](tests/neuro_config.json).

## Notes

- **Images:** each card is drawn by the bot. Papers' own figures aren't used, because many preprints don't allow reuse and journal figures are copyrighted.
- **neuropaperbot:** the two bots share no code at run time, so a fix made in one doesn't reach the other until it's copied across.
