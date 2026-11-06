# ReturnWise AI

An agentic return prediction and reverse logistics platform using Next.js, FastAPI, SQLAlchemy, scikit-learn/XGBoost, SHAP, LangGraph and SciPy MILP.

**All included transactions are synthetic**, generated with seed 42. Model results are synthetic holdout measurements, not evidence of real-world performance. The supplied request was truncated in its Refund Management section; this implementation follows all available sections.

## Run locally

From this repository, using Python 3.12 and Node 20+:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
.\.venv\Scripts\python -m scripts.bootstrap
.\.venv\Scripts\python -m alembic upgrade head
.\.venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open [the dashboard](http://localhost:3000) and [interactive API documentation](http://localhost:8000/api/docs). `ORD-00001` is a ready-to-use order. The dashboard proxies `/api` to FastAPI, including API key headers. The browser uses a login session; `API_KEY` is reserved for service API clients. For a production system, replace this shared-key boundary with user identity and role-based authorization.

The workspace already contains the generated CSV files, SQLite demo database, EDA figures and fitted model bundle. Artifacts and databases are ignored by Git; a fresh checkout requires bootstrap. Startup never generates data or trains models. Bootstrap is an explicit demo operation: do not run it against a production database. Re-running bootstrap regenerates CSV/model artifacts but does not replace existing database orders.

## Use the platform

1. Explore orders and customers in Data Explorer and Customer Intelligence. Search uses IDs and lists are paginated. Select an order to inspect its fields or create a new order using validated JSON.
2. Score an order on Return Prediction. SHAP contributions are computed on encoded model features, in probability units. The baseline plus all contributions equals the prediction. Class probability is not a calibrated guarantee.
3. Run all nine agents in the Agent Center. Provide a verified inspection to obtain disposition recommendations. Enter the actual return request date for policy evaluation.
4. Review the final report, enter reviewer identity and rationale, then approve or reject. Approval only records the review; it does not move goods, reserve capacity, or initiate payments. A report without completed inspection cannot be approved.
5. Use Reverse Logistics, Product Disposition and Refund Management independently. Every analysis is saved. Logistics costs, savings and recovery values are estimates. Warehouse recommendations are individually optimized and do not reserve capacity.
6. Inspect model comparisons, holdout curves, confusion matrix and permutation importance on Model Performance. Explicit retraining uses the cleaned synthetic training file, not new operational orders.
7. Download EDA reports from Data Explorer. Business Intelligence uses database aggregate facts; it supports aggregate summaries and category comparisons rather than unrestricted question answering.

## Data and machine learning

`data/synthetic/transactions.csv` contains 12,000 complete generated records. `data/raw/transactions.csv` adds 100 duplicates and controlled missing ratings/discounts. `data/processed/transactions.csv` removes duplicate order IDs and validates target/history. Missing predictors remain missing until fold-local imputation. See [data dictionary](docs/data-dictionary.md) and `data/provenance.json`.

Training uses 60/20/20 stratified train/validation/test partitions. Each model has a small two-value hyperparameter grid and three-fold cross-validation scored by average precision. Validation PR-AUC selects the model. The selected configuration is refit on train plus validation and evaluated on the untouched test split. Comparison includes Logistic Regression, Random Forest, Gradient Boosting and XGBoost. Metrics and curve points are in `reports/model_performance.json`. The entire preprocessing/model/Isolation Forest/background bundle is atomically persisted using Joblib.

Historical features are generated before the target. Order value, smoothed historical return ratio, purchase-frequency proxy, price bucket and delivery performance are derived without using return outcomes. Category encoding is fitted only in training. Return reason, condition, refund, resale value, return date and processing time are excluded. Predictions are made after delivery; a pre-shipment use case must remove delivery-delay features and retrain. History is a synthetic snapshot, not reconstructed customer event-time history. The dataset contains repeated customers/products across random splits, so evaluation does not measure generalization to entirely unseen customers or future time periods.

## Architecture and API

See [architecture and operational boundaries](docs/architecture.md). Sixteen SQLAlchemy tables cover operational entities, recommendations, model versions and audit logs. Alembic supplies the initial migration. OpenAPI lists every implemented route at `/api/docs`. Read APIs have pagination where applicable; order/customer ID search and return filtering are supported.

Core functionality needs no LLM API. The Business Intelligence agent optionally uses an OpenAI-compatible endpoint via LangChain when `LLM_API_KEY` is set. Only aggregate facts are supplied. The LLM produces a structured qualitative recommendation; authoritative numbers remain in the deterministic fact report. Provider errors fall back to deterministic output. Other explanation types are deterministic and expose their source values.

## Verification

```powershell
.\.venv\Scripts\python -m pytest backend/tests -q
cd frontend
npm run build
```

Tests use a separate workspace test database. They cover authenticated routes, pagination, schema constraints, duplicate protection, persistence, SHAP additivity, warehouse exhaustion, refund policy dates, inspection gates, workflow logs and approval review. Build checks TypeScript and production rendering. No paid provider or real financial service is needed.

## Deployment

The root Dockerfile builds data/model artifacts and runs the backend. `render.yaml` describes a Render Docker service. Configure `DATABASE_URL` as `postgresql+psycopg://...`, `API_KEY`, and an explicit `CORS_ORIGINS` list. On a fresh managed database run Alembic, then import approved data; demo seeding is a separate operation. The Docker build's SQLite database is demo-only and is not copied into PostgreSQL. Database migrations run at container startup. Use one backend worker for the current synchronous retraining lock. Persist model artifacts on durable storage if retrained models must survive deployments.

Deploy `frontend/` to Vercel as a Next.js project. Set `API_URL` to the backend HTTPS origin and `NEXT_PUBLIC_REPORTS_URL` to the same origin. The browser calls the Next.js proxy, so private backend addresses must be reachable from the frontend host. Configure HTTPS and managed secrets. The current direct Vercel deployment is live at https://returnwise-ai-zeta.vercel.app. It runs both services on Vercel with Neon PostgreSQL; see docs/vercel-direct-deployment.md.

Before real operational use: integrate identity/roles, replace synthetic data, validate fairness and probability calibration, evaluate out-of-time performance, add durable background jobs/distributed locks, set rate limits and monitoring, and implement transactional warehouse reservation. The current graph executes synchronously; activity logs become visible after each committed node and the caller receives the final report. Its human review is persisted through an API gate rather than a LangGraph interrupt/checkpointer.

## Verified workspace preview

The preview for this build uses frontend `http://127.0.0.1:3276` and backend `http://127.0.0.1:8275` because default ports were occupied. Start the frontend with `API_URL=http://127.0.0.1:8275` when using these alternate ports. The documented defaults remain 3000 and 8000.

## Workspace login

Open `/login`. Local demo credentials: `demo@returnwise.ai` / `ReturnWise@123`. The **Use demo account** button fills them in. Sign in redirects to the dashboard; Sign out revokes the database session. Sessions expire after eight hours. Passwords and session tokens are never stored in browser storage; the database stores only SHA-256 hashes of random session tokens. Browser mutations require a custom request header and SameSite cookies provide additional cross-site protection.

For deployment, set `APP_ENV=production`, `LOGIN_EMAIL`, and `LOGIN_PASSWORD_HASH`. Production refuses login without a configured hash and sends cookies only over HTTPS. Generate a PBKDF2 hash without putting the password in your shell history:

```powershell
.\.venv\Scripts\python -c "from getpass import getpass; from backend.app.auth import hash_password; print(hash_password(getpass('New password: ')))"
```

Copy the resulting hash into your hosting secret settings. Run `alembic upgrade head` to add the session table. API clients can still authenticate with the configured `X-API-Key`; browser users authenticate with cookies. The local demo password must not be used for a deployed production workspace. Login attempts are limited to five per client address in fifteen minutes in the current single-process service; multi-worker deployments should use a shared rate-limit store.

## Live deployment

Production: https://returnwise-ai-zeta.vercel.app

Login credentials are saved in the ignored local file `.deployment-tools/deployment-login.json`. The deployed app uses its generated production credentials, not the development demo password. The frontend, Python backend, database persistence, prediction explanations, nine-agent workflow, report download and logout were verified on the hosted build on 6 November 2026.

## Create an account

Choose **Create account** on the login page or open `/create-account`. Enter your name, email, a password of at least twelve characters, and a matching confirmation. Registration creates a database-backed member account and starts a session. The same credentials work after signing out. Emails are normalized and duplicates are rejected; only password hashes are stored.

Self-service accounts access the shared synthetic-data demo workspace. They can explore data and generate recommendations. Approval of sensitive recommendations and model retraining require the configured administrator or service credential. Registration does not send email-verification messages or provide password recovery. Deployments apply Alembic migration `0003` automatically before serving the backend.
