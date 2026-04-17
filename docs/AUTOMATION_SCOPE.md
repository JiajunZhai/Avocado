# Automation Scope (Pytest + Playwright)

## Pytest (Backend Contract & Service Logic)

### Covered Now
- API routes and error branches: `backend/tests/test_api_routes.py`
- Scraper extraction stability + rule-based fallback: `backend/tests/test_scraper.py`
- Oracle/refinery behavior: `backend/tests/test_refinery.py`
- Business flow integration (API-level): `backend/tests/test_business_flow_e2e.py`

### Keep in Pytest
- Schema validation and HTTP status assertions
- Cloud failure paths (`CLOUD_UNAVAILABLE` / `CLOUD_SYNTHESIS_FAILED` / `DRAFT_UNAVAILABLE`)
- PDF export gatekeeping and error code assertions

## Playwright (Frontend User Journeys)

### P0 E2E Candidates
- Route redirection `/ -> /generator`
- URL extraction interaction and confirm-to-manual transition
- Step2 config + Step3 generate + Step4 render
- Script edit + markdown copy + PDF button behavior
- Script history persistence/load/delete/clear

### P1 E2E Candidates
- `/oracle` ingest flow then back to `/generator`
- Cloud failure UI messaging and recovery actions (502 surfacing)
- Middle East region behavior + RTL visual checks

## CI Recommendation
- PR gate:
  - `pytest tests -q`
  - `npm run build`
- Nightly:
  - Playwright P0 + P1 suite
  - Upload screenshots and traces for failures
