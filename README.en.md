# SOIA Knowledge Vault Skills

Reusable AI skills for initializing, organizing, reading, distilling, translating, and transforming Markdown vault content.

## Skills

| Skill | Summary |
|---|---|
| `soia-pkm-alipan-curator` | Inventory and organize Aliyun Drive resources, then produce catalogs, family navigation, and learning plans. |
| `soia-pkm-alipan-drive-ops` | Provide atomic Aliyun Drive operations for authentication, browsing, transfers, organization, capacity checks, and full scans. |
| `soia-pkm-baidu-netdisk-ops` | Provide Baidu Netdisk authentication, browsing, and read-only JSONL scanning. |
| `soia-pkm-bootstrap-vault-base` | Initialize a platform-neutral Markdown vault structure, multi-agent entry points, and a knowledge-management loop. |
| `soia-pkm-bootstrap-vault-ima` | Connect a local Markdown vault to Tencent ima with folder monitoring, synchronization, and retrieval verification. |
| `soia-pkm-bootstrap-vault-obsidian` | Configure Obsidian as the client for a local Markdown knowledge base. |
| `soia-pkm-clip-douyin` | Archive a Douyin video to an Obsidian vault with a local media index. |
| `soia-pkm-clip-drive` | Import existing cloud-drive or local PDF and Word documents into an Obsidian vault in bulk. |
| `soia-pkm-clip-github-repo` | Archive an open-source GitHub repository as an Obsidian project card and research note. |
| `soia-pkm-clip-rednote` | Archive a Rednote post, including image and video posts, to an Obsidian vault. |
| `soia-pkm-clip-web` | Archive a web page or blog post to an Obsidian vault using a consistent format. |
| `soia-pkm-clip-wechat-account` | Archive published articles from a WeChat Official Account managed by the user, with URL deduplication. |
| `soia-pkm-clip-wechat-article` | Capture and archive one WeChat article with its content, metadata, and images. |
| `soia-pkm-clip-x` | Archive X/Twitter posts, threads, or Articles to an Obsidian vault. |
| `soia-pkm-distill-article-opinion` | Use Socratic questions to distill the user's own opinion about a vault article. |
| `soia-pkm-interpret-article-analysis` | Produce an independent AI analysis of a long article or paper without changing the source or impersonating the user. |
| `soia-pkm-library-book-catalog` | Maintain Obsidian book catalogs, reading records, and category indexes locally and idempotently. |
| `soia-pkm-library-weread-sync` | Synchronize WeRead books, highlights, and book details to an Obsidian library. |
| `soia-pkm-maintain` | Maintain Obsidian vault health, a vault-wide map, and AI session logs. |
| `soia-pkm-organize-article-moc` | Organize an Obsidian article library using metadata, topic links, months, and two-level MOCs. |
| `soia-pkm-reading-plan` | Turn reading lists, topics, or ideas into an actionable reading schedule based on word count. |
| `soia-pkm-transform-article-notebooklm` | Use NotebookLM to turn articles into quizzes, flashcards, mind maps, podcasts, and study notes. |
| `soia-pkm-transform-article-ppt` | Turn an article, outline, or topic into a presentation media bundle centered on an editable PPTX. |
| `soia-pkm-transform-article-visual` | Turn an article into long-form graphics, infographics, posters, covers, or illustrations. |
| `soia-pkm-transform-obsidian-pdf` | Export Markdown notes in a vault to PDF using Obsidian's native exporter. |
| `soia-pkm-translate-article-zh` | Translate a foreign-language article into a terminology-consistent Chinese document without overwriting the source. |

## Installation

Replace `<skill>` with a skill name from the table above:

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s <skill> -y
```

For example, install the vault maintenance skill:

```bash
npx skills add soia-team/soia-open-pkm-vault-skills -g -a '*' -s soia-pkm-maintain -y
```

## Ecosystem

See [soia-team/soia-open-skills](https://github.com/soia-team/soia-open-skills) for the canonical specifications and complete ecosystem catalog.

## License

MIT License. See [LICENSE](./LICENSE).
