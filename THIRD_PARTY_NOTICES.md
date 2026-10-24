# Third-party notices and data provenance

The application is MIT-licensed. It depends on separately licensed Python and npm packages, pinned in `requirements.lock` and `apps/web/package-lock.json`. Their installed distributions retain their license files. Principal libraries include FastAPI, Starlette, Pydantic, HTTPX, Uvicorn, python-dotenv, React, react-markdown, remark-gfm, Vite, TypeScript, Lucide, pytest and Playwright. Dependency licenses should be rechecked when updating the lockfiles or redistributing vendor bundles.

Mathematical presentation additionally uses remark-math, rehype-katex and KaTeX, with KaTeX fonts served from the local application bundle. Their upstream license notices remain in the installed npm distributions.

Lucide icons are ISC-licensed. DM Sans and IBM Plex Mono are loaded optionally from Google Fonts; they use the SIL Open Font License. System fonts work if network font loading is unavailable. No generated imagery, proprietary design kit or externally sourced photograph is required.

The synthetic benchmark source facts and numerical answer keys are authored for ZeroWall and dedicated to the public domain under CC0 1.0. They describe hypothetical scenarios, not attributed physical measurements. The supplied private brainstorming and Arabic vision documents remain in the user's workspace and are excluded from the distributable source package.

Nebius Token Factory is an external service under its own terms. Model weights are neither downloaded nor redistributed. NVIDIA Nemotron, GLM and any optional models retain their respective provider/model terms. Their runtime identities are recorded when actually called; model access and advertised price references do not establish runtime execution.

The package contains no provider key or account credential. A user must supply their own locally stored project key for live mode. Fixture mode and registered local calculations need no external account or payment.

The source library uses pinned Beautiful Soup, Soup Sieve, pypdf, python-docx, lxml and psutil. Exact versions, copied licence files and hashes are in [the 1.05 dependency inventory](docs/third-party/1.05/README.md). The [agent repository survey](docs/research/1.05/REPOSITORY_SURVEY.md) records design references; no upstream agent runtime code was copied.

Token Factory context counting uses the pinned Hugging Face Tokenizers library. Setup downloads public tokenizer data from the model authors, under their respective repository terms, to ignored local storage; tokenizer revisions, source URLs and SHA-256 hashes are in `config/token_factory_tokenizers.json`. No model weights or model-author Python code are downloaded or executed.
