# Verification — 5 November 2026

- Generated 12,000 unique synthetic transactions plus 100 raw duplicate rows.
- Trained Logistic Regression, Random Forest, Gradient Boosting and XGBoost with three-fold CV and validation PR-AUC model selection.
- Selected Logistic Regression. Holdout PR-AUC: 0.433434; ROC-AUC: 0.692774. Synthetic evaluation only.
- Backend: 33 integration tests passed, including authenticated routes, validation, persistence, SHAP additivity, capacity exhaustion, refunds, all nine agents, inspection gating and audited approval.
- Next.js production build and TypeScript validation passed.
- Alembic initial migration applied successfully to the demo SQLite database. PostgreSQL was not available for runtime verification.
- Live browser: overview loaded database aggregates; ORD-00001 prediction returned 52.4% medium risk with SHAP factors; nine-agent workflow completed and required approval with the inspection gate enforced.
- Backend HTTP health and frontend HTTP response both returned success.
- Optional external LLM integration and cloud deployment were not exercised. Mobile layout is implemented in CSS but not browser-verified.
- Demo runs create persistent recommendations, not financial transactions or warehouse reservations.
