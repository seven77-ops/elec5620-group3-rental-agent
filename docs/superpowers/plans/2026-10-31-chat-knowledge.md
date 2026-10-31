# Unified rental knowledge in chat

The user approved retiring the public Ask rental knowledge modal. General rental/documentation questions use the existing main-chat knowledge route and cited answer view. Uploaded contract questions keep the existing review/search/cloud consent and private scope.

- [x] Verify the existing chat RAG pipeline, housing-context preservation, missing-fact handling and private-contract boundaries with isolated tests; reproduce the redundant public-button entry.
- [x] Remove public KnowledgePanel mounts from chat, contract and aftercare headers and retire the unused public modal. Keep ContractKnowledgePanel and knowledge APIs. Migrate tests from modal interaction to the conversation while retaining local-only public retrieval coverage through the API.
- [x] Verify ordinary chat questions, English answers, citations, source expansion, product guidance, privacy/consent and conversation reloads. Run the build and focused UI/backend checks.
- [x] Update public help and presentation examples, refresh only the public help index after backup and check the local frontend without modifying existing cases.
