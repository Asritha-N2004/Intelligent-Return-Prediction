# Vercel deployment

Deployment is prepared but requires an authenticated Vercel account and a hosted Python backend. A local URL such as `http://127.0.0.1:8275` cannot serve a cloud deployment.

## Frontend project

- Project directory / Root Directory: `frontend`
- Framework: Next.js (configured in `frontend/vercel.json`)
- Build command: `pnpm run build`
- Install command: automatic, using the included `pnpm-lock.yaml`
- Output directory: framework default
- Required production and preview environment variable: `API_URL`, the public HTTPS origin of the FastAPI backend, without an `/api` suffix
- Leave `NEXT_DIST_DIR` unset on Vercel. It is only used for isolated local build verification.
- Leave `NEXT_PUBLIC_REPORTS_URL` unset to serve report downloads through the same-origin backend proxy.

The build fails explicitly on Vercel if the backend address is absent, insecure, or points at localhost. API requests and reports are proxied through Next.js; authentication cookies are returned on the frontend origin.

## Backend prerequisite

The current backend is a Python service with fitted model artifacts and a persistent relational database. Use the supplied Dockerfile/Render configuration with PostgreSQL and configure:

- `DATABASE_URL`: PostgreSQL connection URL using the psycopg dialect
- `APP_ENV=production`
- `LOGIN_EMAIL`: workspace login email
- `LOGIN_PASSWORD_HASH`: PBKDF2 hash generated using the README command
- `API_KEY`: independent service-client credential
- `CORS_ORIGINS`: the deployed frontend origin

Apply migrations. Import the synthetic dataset explicitly if this is a demo deployment; the Docker build's local SQLite demo database does not populate a separately configured PostgreSQL database. Preserve trained models between releases if retraining is enabled.

After deployment verify `/login`, successful sign-in, a loaded dashboard, a return prediction, report downloads, and sign-out. Do not claim a working deployment based only on a frontend build or a hosted login page.

Official references: [Vercel CLI deployment](https://vercel.com/docs/cli/deploying-from-cli), [monorepo root directories](https://vercel.com/docs/monorepos), [package manager detection](https://vercel.com/docs/package-managers).
