"""Reviewed live pairs must survive unrelated discovery-ranking growth."""
import pathlib
import runpy
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILDER = runpy.run_path(str(ROOT / 'scripts/build-corroboration-review-queue.py'))


class CorroborationQueueRetentionTests(unittest.TestCase):
    def setUp(self):
        self.profiles = [{
            'id': 'leaf-spot', 'reviewStatus': 'reviewed',
            'sources': [
                {'doi': '10.1234/a', 'supportedClaims': ['Older lower leaves develop yellow flecks followed by brown necrotic lesions.']},
                {'doi': '10.1234/b', 'supportedClaims': ['Older leaves develop yellow flecks and then necrotic spots.']},
                {'doi': '10.1234/c', 'supportedClaims': ['Lower foliage shows pale specks before brown leaf spots appear.']},
            ],
        }]
        self.all_rows = BUILDER['discovery_pairs'](self.profiles, 1.1, 1.1, 0, 0, 10)
        self.assertEqual(len(self.all_rows), 3)
        last = self.all_rows[-1]
        self.decision = {
            'profile_id': last['profile_id'],
            'source_a_id': last['source_a']['canonical_source_id'],
            'source_b_id': last['source_b']['canonical_source_id'],
            'claim_a': last['claim_a'], 'claim_b': last['claim_b'],
        }

    def select(self, decisions, limit=1):
        return BUILDER['discovery_pairs'](self.profiles, 1.1, 1.1, 0, 0, limit, reviewed_decisions=decisions)

    def test_retains_reviewed_pair_below_cutoff_without_promoting_it(self):
        rows = self.select([self.decision])
        self.assertEqual(rows, [self.all_rows[-1]])
        for field in ('auto_merge', 'eligible_for_training', 'eligible_for_corroboration'):
            self.assertIs(rows[0][field], False)

    def test_swapped_pair_orientation_has_same_identity(self):
        swapped = dict(self.decision, source_a_id=self.decision['source_b_id'],
                       source_b_id=self.decision['source_a_id'],
                       claim_a=self.decision['claim_b'], claim_b=self.decision['claim_a'])
        self.assertEqual(self.select([swapped]), [self.all_rows[-1]])

    def test_changed_claim_or_source_cannot_resurrect_a_review(self):
        for altered in (dict(self.decision, claim_a='A different claim'),
                        dict(self.decision, source_a_id='doi:10.9999/foreign')):
            self.assertEqual(self.select([altered]), [self.all_rows[0]])

    def test_review_overflow_fails_instead_of_dropping_history(self):
        other = self.all_rows[0]
        decision = dict(profile_id=other['profile_id'], claim_a=other['claim_a'], claim_b=other['claim_b'],
                        source_a_id=other['source_a']['canonical_source_id'],
                        source_b_id=other['source_b']['canonical_source_id'])
        with self.assertRaisesRegex(ValueError, 'reviewed.*budget'):
            self.select([self.decision, decision])

    def test_unreviewed_ranking_and_capacity_are_preserved(self):
        self.assertEqual(self.select([], 2), self.all_rows[:2])


if __name__ == '__main__':
    unittest.main()
