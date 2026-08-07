# Phase 2 changelog

## Backend

- Added Google OAuth verification endpoint.
- Added persistent rotating refresh tokens and logout revocation.
- Added Phase 2 Alembic revision with Phase 1 upgrade support.
- Added CRUD routers for business entities.
- Added transaction tracking and summaries.
- Added custom categories and recurring expenses.
- Added immutable budget plan history and comparison.
- Added notification preference, device-token, job, and delivery services.
- Added provider-independent AI providers and allowlisted tool orchestration.
- Added proposal confirmation, rejection, recalculation, and reversal.
- Added append-only audit, tool-call, delivery, and AI-usage records.
- Expanded widget snapshots with plan ID and version.

## Mobile

- Added Google OAuth sign-in flow.
- Added automatic refresh-token rotation.
- Added allocation sliders and locks.
- Added transaction entry and summary screen.
- Added custom-category screen.
- Added plan-history comparison screen.
- Added AI confirmation and undo cards.
- Added notification preferences and push-token registration.
- Expanded native widget bridge.

## Native iOS

- Added App Group config plugin support.
- Expanded snapshot schema with plan ID/version.
- Added bridge methods to write, clear, and inspect snapshot write time.
- Reloads WidgetKit timelines after confirmed changes and reversals.
