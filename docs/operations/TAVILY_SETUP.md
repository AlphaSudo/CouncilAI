# Tavily setup

Verified on 20 October 2026 using the official
[Tavily setup skill](https://tavily.com/agent-setup/SKILL.md).

## Installed and verified

- Tavily CLI 0.1.8 in an isolated user tool environment, outside Council's
  Python environment. Its dependency check passed.
- Native Windows launcher at `~/.local/bin/tvly.cmd`, with UTF-8 enabled.
  The user PATH includes this directory. Existing app and terminal processes
  may need restarting before the bare `tvly` command resolves.
- API-key authentication persisted in `~/.tavily/config.json`. The directory
  and inherited config-file access are restricted to the current Windows user.
- The same supplied key is saved in the existing gitignored `.env.local` as
  `TAVILY_API_KEY`. No key is included in this document or the example file.
- Eight official skills installed globally for Codex: `tavily-cli`,
  `tavily-search`, `tavily-extract`, `tavily-map`, `tavily-crawl`,
  `tavily-research`, `tavily-dynamic-search`, and `tavily-best-practices`.
  The current session's skill inventory predates installation; they become
  available after the next-turn inventory refresh or a restart/rescan.
- Authentication from saved CLI config and one successful Basic search with
  three official documentation results were verified. An initial CLI attempt
  failed before consuming credits; UTF-8 resolved the launcher issue.

## Cost boundary

The usage endpoint identifies the account as Researcher with a 1,000-credit
plan. The setup performs no model inference, advanced search, extraction,
mapping, crawling, or Tavily Research. Basic search has a published cost of
one credit; a usage counter read immediately after the smoke test can lag and
must not be interpreted as proof that a successful search consumed no credit.

The account reports no pay-as-you-go usage. Its `paygo_limit` is null, which
does not establish that automatic paid billing is disabled. No billing setting
or payment method was changed. The user's $0 additional-payment constraint
continues to apply; future work must stay within confirmed free allowance.
CLI installation itself is not a free-only spending guard.

## Council integration boundary

The original setup only configured coding-agent skills and credentials. Council now integrates Tavily through its server-side REST adapter, with free-plan admission, Basic-only requests, reserved credits and shared cached results. The shared source library, bounded model tool loop, accounting and Simple/Explain inspection are implemented in [release 1.05](../releases/1.05.md).

The CLI is not used as Council's runtime provider. New supported councils now default to web search on when a key is configured. The main composer switch controls upcoming model replies; each enabled reply gets a broker search and saved passages. See [Per-reply web search](PER_REPLY_WEB_SEARCH.md) for execution rules and live verification. Local source operations work without a search key. The original setup verification below remains a historical setup record.

## Local checks

After refreshing the environment, the following commands do not execute a
search or consume search credits:

```powershell
tvly --version
tvly auth --json
```

The verification record is [tavily-setup.json](../validation/tavily-setup.json).
Do not share credential files or paste their contents into the browser.
