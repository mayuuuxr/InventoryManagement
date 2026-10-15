# E2E (Playwright) — nibba

Journeys covered: J1 login/lockout, J2 inward→balance, J3 outward→balance+reports (happy + bad-input/expired-session/empty-data states).

## Run
```
cd e2e
npm i
npx playwright install chromium
set BASE_URL=http://127.0.0.1:8000 && set E2E_USER=owner && set E2E_PASS=owner1234
npm run test:e2e        :: headless
npm run test:e2e:ui     :: headed debug
```
Seed first: owner superuser + 1 site + 1 material (use Django admin or `seed_catalog.json`).
Cleanup: delete rows named `E2E-*` via admin after runs (tests use timestamped names).

## CI
Workflow `.github/workflows/e2e.yml` runs `npm run test:e2e:ci` on every PR (traces + screenshots on failure).
Resilient selectors: role-based first; add `data-testid` to login inputs, Save buttons, balance cells (see journeys.spec.js NOTE).
Auth fixture (`tests/auth.fixture.js`) logs in once per worker.
Push notifications and phone/tunnel access were removed from nibba (nothing to test). E2E runs against local `http://127.0.0.1:8000` only.
