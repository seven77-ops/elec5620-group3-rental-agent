"""Evaluation reports are explicit about labels, errors and partial cost observations."""
from pathlib import Path
import tempfile
import unittest

from scripts.evaluate_jev_routing import load_cases, metrics
from scripts.local_ai_env import load_ai_env


class EvaluationTests(unittest.TestCase):
    def test_synthetic_fixture_has_balanced_supported_labels_without_claiming_human_validation(self):
        root=Path(__file__).resolve().parents[2]
        fixture,cases=load_cases(root/'data/evaluation/jev-routing.json')
        self.assertEqual(len(cases),36)
        self.assertEqual(fixture['label_status'],'proposed_baseline_for_human_review')
        self.assertEqual(len({c['expected_route'] for c in cases}),6)

    def test_failures_count_against_accuracy_and_unknown_cost_is_not_assumed_zero(self):
        report=metrics([{'expected':'knowledge','predicted':'knowledge','accepted':True,'duration_ms':10,'cost':.01},
                        {'expected':'aftercare','predicted':None,'accepted':False}])
        self.assertEqual(report['accuracy_including_failures'],.5)
        self.assertEqual(report['accepted_fraction'],.5)
        self.assertEqual(report['cost_observed_calls'],1)
        self.assertEqual(report['known_cost_usd'],.01)

    def test_env_loader_supports_separate_jev_settings_without_overriding_existing_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'.env'
            path.write_text('OPENROUTER_API_KEY=local-key\nRENTAL_JEV_MODE=shadow\nRENTAL_JEV_TIMEOUT_SECONDS=3\n')
            result=load_ai_env(path,{'OPENROUTER_API_KEY':'existing-key'})
            self.assertEqual(result['OPENROUTER_API_KEY'],'existing-key')
            self.assertEqual(result['RENTAL_JEV_MODE'],'shadow')
            self.assertEqual(result['RENTAL_JEV_TIMEOUT_SECONDS'],'3')


if __name__=='__main__':unittest.main()
