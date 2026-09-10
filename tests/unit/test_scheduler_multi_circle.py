# Updated by Claude AI on 2026-09-09
"""
Tests for routes/scheduler.py's _run_for_every_circle() - the helper every
Task-Scheduler-triggered digest route uses to sweep every circle. Uses a
fake generator function (not the real digest generators) so this stays fast
and doesn't touch real circles' data - CircleModel.get_all() returns EVERY
circle in the local dev DB (test/test2 plus whatever real circles exist
locally), so assertions here check that both test circles were included,
not that they were the ONLY circles processed. See PROMPT.md's "Plan:
Multi-Circle Test Coverage" item 5.
"""

# Import order safety - see tests/unit/test_multi_circle_isolation.py's comment.
import app  # noqa: F401

from routes.scheduler import _run_for_every_circle
from tests.test_config import TEST_CIRCLE_SLUG, TEST_CIRCLE_SLUG_2


class TestRunForEveryCircle:
    def test_generator_called_once_per_circle_with_distinct_slugs(self, second_test_circle):
        calls = []

        def fake_generator(app_arg, slug):
            calls.append(slug)
            return {'emails_sent': 1, 'areas_processed': 1, 'unassigned_count': 0, 'errors': []}

        _run_for_every_circle(fake_generator, 'test label')

        assert TEST_CIRCLE_SLUG in calls
        assert TEST_CIRCLE_SLUG_2 in calls
        assert calls.count(TEST_CIRCLE_SLUG) == 1
        assert calls.count(TEST_CIRCLE_SLUG_2) == 1

    def test_one_circles_exception_does_not_block_the_others(self, second_test_circle):
        """One circle's generator raising must be caught and logged into
        that circle's own errors entry, without preventing the OTHER
        circle's generator from running - aggregated results/errors stay
        per-circle-attributable, not lost or conflated."""
        calls = []

        def flaky_generator(app_arg, slug):
            calls.append(slug)
            if slug == TEST_CIRCLE_SLUG_2:
                raise RuntimeError('simulated failure for test2')
            return {'emails_sent': 5, 'areas_processed': 2, 'unassigned_count': 0, 'errors': []}

        aggregated = _run_for_every_circle(flaky_generator, 'test label')

        # Both circles were actually attempted - the exception didn't
        # short-circuit the loop for circles processed afterward.
        assert TEST_CIRCLE_SLUG in calls
        assert TEST_CIRCLE_SLUG_2 in calls

        # The failure is attributable to the specific circle that raised.
        assert any(TEST_CIRCLE_SLUG_2 in err for err in aggregated['errors'])
        assert not any(err.startswith(f'{TEST_CIRCLE_SLUG}:') for err in aggregated['errors'])

        # The OTHER circle's real results still made it into the aggregate -
        # a failure in one circle doesn't wipe out or block another's data.
        assert aggregated['emails_sent'] >= 5
        assert aggregated['areas_processed'] >= 2
