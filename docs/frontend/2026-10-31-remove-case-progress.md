# Remove the user-facing case progress page

Removed the Case progress navigation item on desktop and mobile, its lazy page registration, component and unused styles. Old /cases/:caseId/progress URLs replace-navigate to the same case's assistant. No saved case records or backend progress endpoints were removed.

Updated the reviewed product guide and canonical document snapshot so help no longer points users to the retired screen. Only backed-up product-help RAG chunks were refreshed; all other chunks and vectors were preserved.

Verification: production build passed; two browser checks passed for shell navigation, desktop/mobile removal, old URL redirect and immutable case/progress records. Three backend progress tests passed, and eight product-help checks passed. The pre-existing historical Agent4 UI test remains skipped; its old page-navigation assertion now checks the retained API instead.
