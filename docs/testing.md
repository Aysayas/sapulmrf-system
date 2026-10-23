# Testing

There are two kinds of tests:
- **API tests** (pytest) check the backend rules directly.
- **Browser tests** ([Playwright](https://playwright.dev)) open the app in a real Chrome, click and type like a user, and check what appears.

## API tests

Run them from the repo root, with the stack running:

| Command | What it does |
|---|---|
| `docker compose exec api pytest` | Run every API test |
| `docker compose exec api pytest tests/test_users.py -v` | Run one file and show each test |
| `docker compose exec api ruff check .` | Lint |

They use their own database, `<DB_NAME>_test`, created on the first run. Each test runs inside a transaction that's rolled back, so they never touch your dev data.

## Browser tests

Run them from `web/`:

| Command | What it does |
|---|---|
| `npm run test:e2e` | Run every browser test in the terminal |
| `npm run test:e2e:ui` | Open the visual runner to watch tests step by step |
| `npm run test:e2e:report` | Open the report from the last run, with screenshots of failures |

They test the real stack on http://localhost:5174, and run `docker compose up -d` first if it isn't up.

### First time on a new computer

1. In `web/`, install the packages on the host (the container has its own copy) and download the test browser:
   ```bash
   npm install
   npx playwright install chromium
   ```
2. Create the test admin in your dev database. Put `E2E_ADMIN_USERNAME=e2e.admin` and a long random `E2E_ADMIN_PASSWORD` in `.env`, then:
   ```bash
   docker compose exec -e E2E_ADMIN_PASSWORD api python -c "import os; from app.core.db import SessionLocal; from app.cli import create_admin; create_admin(SessionLocal(), 'Test Admin', 'e2e.admin', os.environ['E2E_ADMIN_PASSWORD'])"
   ```
   (Run it from a shell where `E2E_ADMIN_PASSWORD` is set, or pass the value with `-e E2E_ADMIN_PASSWORD=...`.)

### Test accounts

| Account | Where it comes from |
|---|---|
| `e2e.admin` (Barangay Administrator) | `.env`, created once as above. Only for tests, never a real person |
| `e2e.<role>.<id>` | Created by the tests that need them, unique on every run |
| `e2e Purok …`, `e2e Area …`, `E2E-…` devices | Created by `admin-02-setup.spec.ts` through `admin-05-alerts.spec.ts` |
| `E2E-…` problem reports | Created by `admin-05-alerts.spec.ts` |

Clean up what the tests created: `e2e.<role>.<id>` users, `e2e …` source areas and their deliveries, `e2e …` storage areas with their stock, requests and alerts, `E2E-…` devices, and problem reports about `E2E-…` records. It keeps `e2e.admin` and all real data:
```bash
docker compose exec api python -m app.cli remove-test-data
```

### Operations data

`admin-03-operations.spec.ts` needs operations records in the dev database. Fill it with the simulator once (see `sim/README.md`). The backfill needs the test admin, because it approves older requests as that account:
```bash
docker compose --profile sim run --rm sim python -m app.simulator setup
docker compose exec api python -m app.simulator backfill --days 40
```
Remove everything simulated with `docker compose exec api python -m app.simulator remove`. Real records are never touched.

`admin-05-alerts.spec.ts` needs the `worker` service running (`docker compose up -d` starts it). It waits up to 45 seconds for the worker's next check.

## Where tests live

```
api/tests/            test_<module>.py, with fixtures in conftest.py
web/e2e/
├── fixtures/         logIn / logOut helpers, the adminPage fixture, test accounts
├── smoke.spec.ts     login page, redirect when logged out, wrong password
├── admin-NN-name.spec.ts     admin screens (desktop size)
└── operator-NN-name.spec.ts  operator screens (phone size, 390 × 844; none yet)
```

Files whose name starts with `operator` run at phone size. All others run at desktop size (1440 × 900).

## Writing a browser test

```ts
import { expect, test } from './fixtures/test'

test('admin sees the users list', async ({ adminPage: page }) => {
  await page.goto('/admin/settings/users')
  await expect(page.getByRole('button', { name: '+ Add user' })).toBeVisible()
})
```

Find elements the way a user would: `getByRole`, `getByLabel`, `getByText`. Never use CSS classes. Import `test` and `expect` from `./fixtures/test`.
