# Vendored packs (main)

| Pack | Upstream | Role |
|---|---|---|
| `vendor/tavily/` | [tavily-ai/skills](https://github.com/tavily-ai/skills) | Search / extract / crawl / research |
| `vendor/firecrawl/` | [firecrawl/skills](https://github.com/firecrawl/skills) | Build + research Firecrawl skills |
| `vendor/mattpocock/` | [mattpocock/skills](https://github.com/mattpocock/skills) | Implement, TDD, code review, architecture |
| `vendor/ui-ux-pro-max/` | ui-ux-pro-max bundle | UI/UX design system |
| `vendor/anthropic/skill-creator/` | [anthropics/skills](https://github.com/anthropics/skills) | Skill authoring (operators) |
| `vendor/superpowers/` | [obra/superpowers](https://github.com/obra/superpowers) | Debugging, verification, TDD, git workflows |
| `vendor/trailofbits/` | [trailofbits/skills](https://github.com/trailofbits/skills) | Audit context, diff review, insecure defaults |

**Not vendored:** Anthropic `canvas-design` (art-first; bad for exact text posters). Kodus/VoltAgent awesome lists are catalogs only — see `docs/hermes_skill_sources.txt` (plan) for curation targets.

Prefer dispatcher `http://dispatcher:8090/v1/search|extract|image` over inventing tool flows.

Live-matched media packs live under `hermes/temp/skills/vendor/` (gitignored).
