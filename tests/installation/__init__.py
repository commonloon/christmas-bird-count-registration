"""
Installation validation test suite for Christmas Bird Count registration system.

This test suite validates that a new deployment is properly configured and ready
for use. It is designed to be portable across different bird count organizations
with different area configurations, GCP projects, and organizational settings.

Test Phases:
- Phase 1: Configuration validation (config files)
- Phase 2: GCP infrastructure validation (Firestore, Secret Manager, Cloud Run)
- Phase 3: Deployment validation (URLs, static assets, OAuth)
- Phase 4: Core functionality validation (registration, admin, CSV export)
- Phase 5: Multi-area operations validation (all areas working)
"""
