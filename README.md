# study-finder
LLM koulutuksen testirepo...

Prompt: create a readme file for a new project where my goal is extract and analyze study program description and learning goals from opintopolku.fi. I might want to focus on cs related programs but I don't really know how to do that yet

From Claude:
The most useful discovery is that opintopolku.fi runs on an open, documented API (**konfo-backend**), so the README is built around hitting that instead of scraping HTML — it's more stable and gives you structured JSON. I pointed you to the Swagger docs as the source of truth rather than hardcoding endpoint paths I hadn't verified.

The key data-model insight: programmes (`koulutus`) and their institution-specific implementations (`toteutus`) are separate entities, and **learning goals/osaamistavoitteet most likely live on `toteutus`** — that's the first thing to confirm before you build anything.

On the CS-focus uncertainty you mentioned, I left it as a genuine open question with three concrete approaches (field-of-study filter, keyword search, or classify-from-text) rather than pretending it's decided. The suggested first move is to pull everything in the ICT field, look at ~20 entries, and let that show you where the real boundary is.

I assumed Python and left the license/scope as TBD. Two things I'd want your steer on if you keep iterating: whether you care about all three languages (fi/sv/en) or just one, since Finnish text needs Finnish-aware NLP tooling, and what the actual analytical *question* is — "compare learning goals" is a direction but not yet something you can test an answer against.
