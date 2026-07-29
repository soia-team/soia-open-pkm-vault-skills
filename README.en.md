# SOIA Knowledge Vault Skills

[中文](README.md) · English

Collect scattered articles, books, and cloud-drive files into one local Markdown vault, then turn them into something usable — opinions, notes, decks, long images, PDFs.

## What this is

`soia-open-pkm-vault-skills` covers the full lifecycle of a personal knowledge base. Every skill works against the same local Markdown vault, forming one loop:

```text
Capture (web / WeChat articles / X / Rednote / Douyin / GitHub / cloud drive / WeRead)
    ↓
Organize (metadata normalization, topic backlinks, two-level MOC, book catalog)
    ↓
Distill (AI interpretation, Socratic opinion extraction, translation)
    ↓
Transform (PPT / long image / infographic / PDF / quiz, flashcards, podcast)
    ↓
Maintain (health checks, vault map, reading plans)
```

The vault is plain local Markdown with no platform lock-in; Obsidian and Tencent ima are optional consumers.

### When to use it

- "Archive this web page / WeChat article / tweet into my vault."
- "I have hundreds of PDFs on my cloud drive — import and organize them."
- "Is this long article worth reading closely? Give me an interpretation first."
- "I finished it but cannot articulate my take — help me get it out."
- "Turn this article into a deck / long image / quiz."
- "Sync my WeRead highlights into the book library."
- "The vault is getting messy — run a health check and clean it up."

### What it does not do

- Does not host your vault. Everything stays in your own local directory; this repo only provides the skills that operate on it.
- Does not write your opinions for you. Interpretation skills produce material for you to judge; opinion extraction asks you questions until you say it yourself.
- Does not store credentials. WeRead, X, Alipan and similar logins stay in their own official flows — never in the repo, the vault body, or logs.
- Does not install environments. Obsidian, Playwright and similar prerequisites belong to [soia-open-env-skills](https://github.com/soia-team/soia-open-env-skills).
- Does not touch internal company material or governance workflows — those live in private repos.

## Where to start

First time through, follow this order:

| Goal | Start with | Done when |
|---|---|---|
| Build a vault from scratch | `soia-pkm-bootstrap-vault-base` | Directory skeleton, multi-agent entries, and the PKM loop are in place |
| Consume it in Obsidian | `soia-pkm-bootstrap-vault-obsidian` | Bases enabled; config and styles verified |
| Archive your first item | `soia-pkm-clip-web` | A normalized Markdown note with metadata appears in the vault |
| Organize once it grows | `soia-pkm-organize-article-moc` | Topic backlinks and a two-level MOC exist |
| Periodic health check | `soia-pkm-maintain` | Dead links, tag drift, and orphan notes are reported |

Skills marked 🟡 need a platform login or an API key first; each one tells you exactly what is missing before it runs.

## Skill catalog

> **Ready to use**: ✅ works right after install · 🟡 needs an API key or a third-party login first

| Skill | Responsibility | Ready to use |
|---|---|---|
| `soia-pkm-alipan-curator` | Inventory and organize Alipan cloud-drive resources into an Obsidian collection index, Excel catalog, and study plan. | 🟡 |
| `soia-pkm-alipan-drive-ops` | Alipan atomic operations: login, dual-drive browsing, move/rename/delete, upload/download, and full-drive scans. | 🟡 |
| `soia-pkm-baidu-netdisk-ops` | Baidu Netdisk atomic operations and read-only JSONL scanning. | 🟡 |
| `soia-pkm-bootstrap-vault-base` | Initialize a platform-neutral Markdown vault structure, multi-agent entry points, and a knowledge-management loop. | ✅ |
| `soia-pkm-bootstrap-vault-ima` | Connect a local Markdown vault to Tencent ima with folder monitoring, synchronization, and retrieval verification. | 🟡 |
| `soia-pkm-bootstrap-vault-obsidian` | Configure Obsidian as the client for a local Markdown knowledge base. | ✅ |
| `soia-pkm-clip-douyin` | Archive a single Douyin video into the Obsidian vault, keeping media local and the note lightweight. | ✅ |
| `soia-pkm-clip-drive` | Bulk-import existing cloud-drive or local documents (PDF/Word) into the vault as searchable notes. | ✅ |
| `soia-pkm-clip-github-repo` | Archive a GitHub repository as a project card and research note in the vault. | ✅ |
| `soia-pkm-clip-rednote` | Archive a single Rednote post (text or video) into the vault; media stays local, the vault keeps lightweight Markdown. | ✅ |
| `soia-pkm-clip-web` | Archive a web page or blog post into the vault following the shared clip conventions. | ✅ |
| `soia-pkm-clip-wechat-account` | Bulk-archive articles published from your own WeChat official account, deduplicated by URL. | 🟡 |
| `soia-pkm-clip-wechat-article` | Archive a single WeChat article: title, author, body, publish time, and images, per the clip conventions. | ✅ |
| `soia-pkm-clip-x` | Archive X/Twitter posts, threads, and Articles into the vault, with optional Telegram favorites sync. | 🟡 |
| `soia-pkm-distill-article-opinion` | Use Socratic questions to distill the user's own opinion about a vault article. | ✅ |
| `soia-pkm-interpret-article-analysis` | Produce an independent AI analysis of a long article or paper without changing the source or impersonating the user. | ✅ |
| `soia-pkm-library-book-catalog` | Maintain Obsidian book catalogs, reading records, and category indexes locally and idempotently. | ✅ |
| `soia-pkm-library-weread-sync` | Synchronize WeRead books, highlights, and book details to an Obsidian library. | 🟡 |
| `soia-pkm-maintain` | Maintain Obsidian vault health, a vault-wide map, and AI session logs. | ✅ |
| `soia-pkm-organize-article-moc` | Organize an Obsidian article library using metadata, topic links, months, and two-level MOCs. | ✅ |
| `soia-pkm-reading-plan` | Turn reading lists, topics, or ideas into an actionable reading schedule based on word count. | ✅ |
| `soia-pkm-transform-article-notebooklm` | Use NotebookLM to turn articles into quizzes, flashcards, mind maps, podcasts, and study notes. | 🟡 |
| `soia-pkm-transform-article-ppt` | Turn an article, outline, or topic into a presentation media bundle centered on an editable PPTX. | ✅ |
| `soia-pkm-transform-article-visual` | Turn an article into long-form graphics, infographics, posters, covers, or illustrations. | ✅ |
| `soia-pkm-transform-obsidian-pdf` | Export Markdown notes in a vault to PDF using Obsidian's native exporter. | ✅ |
| `soia-pkm-translate-article-zh` | Translate a foreign-language article into a terminology-consistent Chinese document without overwriting the source. | ✅ |

## Install

Installing the whole domain plugin is recommended — it brings every skill in this repo:

```bash
claude plugin marketplace add soia-team/soia-open-skills
```

```bash
claude plugin install soia-pkm-vault@soia
```

For Codex:

```bash
codex plugin marketplace add soia-team/soia-open-skills
codex plugin add soia-pkm-vault@soia
```

For a single skill you can use the npx route. Note the skill lands in the shared
source `~/.agents/skills`; if the plugin is installed too, the same skill shows up
twice and the two copies drift apart — pick one:

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s <skill-name> -y
```

## Ecosystem

Specifications, the full ecosystem catalog, and install guides live in [soia-team/soia-open-skills](https://github.com/soia-team/soia-open-skills).
The full maintenance workflow is in [CONTRIBUTING.md](https://github.com/soia-team/soia-open-skills/blob/main/CONTRIBUTING.md).

## License

MIT License — see [LICENSE](./LICENSE).
