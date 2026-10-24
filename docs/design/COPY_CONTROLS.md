# Copy controls

Visual thesis: small, always-visible outline icons in the existing calm council layout, with no extra cards or panels on the normal path.

Content plan: put a response copy icon beside its author, and a copy-all icon beside transcript download. Copy the original public Markdown, preserving equations; the combined text includes the question, notes, model names and all responses in chronological order.

Interaction thesis: show a temporary checkmark on successful copy and retain keyboard focus and the current draft. Use a local browser fallback when the clipboard API is unavailable; if both clipboard mechanisms fail, present selected plain text in a keyboard-accessible dialog. Copy actions never dispatch inference or research. Both Simple and Explain expose the same controls.

The hidden copy announcement is positioned relative to its button so it stays inside the conversation's scroll container. Long replies must not create an outer page scrollbar or expose a light canvas. The document canvas follows the council's dark theme while the research workspace retains its own theme.
