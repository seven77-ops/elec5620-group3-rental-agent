# Product language

The rental assistant is an English product. Write all new or modified product
copy in English: visible UI, accessibility labels, errors, status descriptions,
agent questions/replies, retrieval summaries, generated emails and public help.
Use English/Australian date and currency conventions. Generated output defaults
to English; do not add a Chinese output option without a new user request.

Preserve original user messages, names, addresses, uploaded documents, citations,
quoted source text and saved business records. Multilingual input recognition
and legacy aliases remain valid; they must produce English authored responses.
Never translate schema identifiers, environment variable names or source facts.

Keep consent, explicit save/confirmation steps, evidence citations and Jev
routing behavior intact. Use synthetic records for development verification.

See `docs/frontend/2026-10-30-english-product.md` for the release and verification
record. Update English selectors and meaningful output expectations when changing
copy; retain tests for original source data and multilingual inputs.
