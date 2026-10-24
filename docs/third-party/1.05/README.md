# Dependencies adopted for Council research

The exact installed versions, upstream package pages, licence metadata and
copied licence-file hashes are recorded in [dependencies.json](dependencies.json).
These packages provide CPU document parsing and process resource monitoring.
Tavily uses the official REST API through the existing HTTP client; the product
does not execute the Tavily CLI.

The agent repositories in the research survey informed architecture decisions.
No upstream agent runtime source was copied into Council and no agent plugin
or package installer runs when a source is read.
