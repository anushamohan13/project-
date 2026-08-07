# Phase 2 validation report

## Passed

- Python source compilation: passed
- FastAPI application import and OpenAPI generation: passed
- OpenAPI paths generated: 60
- Backend automated tests: **11 passed**
- Fresh SQLite Alembic upgrade to `20260807_0002`: passed
- Fresh SQLite Alembic downgrade to base: passed
- Simulated Phase 1 SQLite schema upgraded to Phase 2: passed
- Original Phase 1 end-to-end flow: passed
- Cross-user data isolation: passed
- Decimal-safe budgeting and exact allocation totals: passed
- Refresh-token rotation and rejection of reused refresh token: passed
- Custom-category and transaction CRUD: passed
- Transaction category/online-spending summary: passed
- AI proposal creation and explicit confirmation: passed
- Immutable plan-version creation: passed
- AI change reversal: passed
- Plan-history comparison: passed
- Mock email notification job processing: passed
- Widget snapshot API update after plan confirmation: passed

## Environment limitation

`npm install` could not be completed in the execution environment because its configured internal npm registry returned HTTP 404 for `@babel/core`. Therefore the React Native dependency graph and native iOS build could not be executed here. The mobile source, package manifest, native Expo module, WidgetKit files, and configuration are included, but they must be installed and built on a machine with access to the public npm registry or a complete corporate mirror.

## Credentials not exercised

The following integrations are implemented but were not live-tested because credentials and provider accounts were not supplied:

- Google OAuth
- SendGrid
- Expo Push Service
- OpenAI
- Anthropic
- Azure OpenAI

All have development-safe mock or disabled behavior where appropriate.
