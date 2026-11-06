# Render backend, then Vercel frontend

The repository is prepared for a demo deployment. Both services use a real PostgreSQL database and HTTP-only login sessions; the 12,000 order records are explicitly synthetic.

## Account access needed

Connect the Render and GitHub plugins to publish a private source repository and create its Render resources. Vercel is already connected. Do not send API tokens or passwords through chat. Account login or any required third-party authorization must be completed by the account owner.

## Render

1. Publish the repository, keeping `render.yaml` and `Dockerfile` at its root.
2. Create a Render Blueprint from that repository. The included blueprint creates `returnwise-api` and `returnwise-db` in Singapore on free plans and automatically wires the database's internal connection URI.
3. Set `LOGIN_EMAIL` and `LOGIN_PASSWORD_HASH` when prompted. Generate the hash locally using the password command in the README. Store it as a Render secret; never commit the plaintext password or a real credential file.
4. Deploy the blueprint. Docker installs the pinned dependencies and OpenMP library, then generates data, EDA and model artifacts using an isolated build-time SQLite database. It does not connect to the live PostgreSQL database while building.
5. At runtime, the entry point applies migrations, imports synthetic demo data only into an empty database, records the model version, then starts Uvicorn on Render's supplied port. Repeated deployment starts preserve existing orders and records. PostgreSQL advisory locking serializes overlapping initialization attempts.
6. Verify the service's `/api/health` endpoint returns `status: ok` and `model_ready: true`. Public health checks do not bypass authentication on dashboard or order APIs.

The blueprint sets `SEED_DEMO_DATA=true`. Disable it before connecting a real operational dataset. Capacity and logistics figures remain recommendations, not executed actions. No paid LLM key is necessary.

## Vercel

After the backend is healthy, create the frontend project with Root Directory `frontend`. Set `API_URL` to the exact Render HTTPS origin, without `/api`. Leave `NEXT_PUBLIC_REPORTS_URL` unset so downloads use the same proxy. Build and deploy, then verify login, dashboard data, prediction persistence, report downloads and logout through the deployed frontend.

Because the browser uses the Vercel origin for both the page and proxied API, it does not need cross-origin credentialed fetches to Render. `CORS_ORIGINS` starts empty; any future direct browser clients need explicit origin configuration.

## Free-tier limits and verification

Render documents that free web services can sleep and free PostgreSQL databases expire after 30 days. This configuration is intended for a demo. No paid plan should be activated without the account owner's agreement to its price. See [Render free instances](https://render.com/docs/free) and [Blueprint specification](https://render.com/docs/blueprint-spec).

Local verification: 41 backend tests passed, including Render URI normalization, missing-production-login validation and repeat-start idempotency. Live PostgreSQL, the Linux Docker build, and hosted end-to-end behavior must still be verified during the cloud deployment. Docker is not installed in this workspace.
