"""Synthetic local-log contracts; no host sessions or catalogs are read."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import analyze

FIXTURES = Path(__file__).parent / 'fixtures'
NOW = 1793059200  # 2026-10-27 UTC


class LocalSourcesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.claude = self.root / 'claude'
        self.codex = self.root / 'codex'
        project = self.claude / 'projects' / 'synthetic'
        project.mkdir(parents=True)
        shutil.copyfile(FIXTURES / 'claude.jsonl', project / 'main.jsonl')
        sub = project / 'main' / 'subagents'
        sub.mkdir(parents=True)
        row = json.loads((FIXTURES / 'claude.jsonl').read_text().splitlines()[0])
        row['message']['id'] = 'msg-sub'
        row['requestId'] = 'req-sub'
        (sub / 'agent-one.jsonl').write_text(json.dumps(row)+'\n')
        sessions = self.codex / 'sessions' / '2026'
        sessions.mkdir(parents=True)
        shutil.copyfile(FIXTURES / 'codex.jsonl', sessions / 'rollout-one.jsonl')
        self.rates = self.root / 'rates.json'
        shutil.copyfile(FIXTURES / 'rates.json', self.rates)

    def args(self, source, *extra):
        return analyze.parse_args(['--source', source, '--days', '7',
            '--claude-dir', str(self.claude), '--codex-dir', str(self.codex),
            '--rates', str(self.rates), *extra])

    def run_report(self, source, *extra):
        with patch.object(analyze.time, 'time', return_value=NOW):
            return analyze.run(self.args(source, *extra))

    def test_claude_deduplicates_requests_and_tracks_subagents(self):
        report = self.run_report('claude')
        base = report['baseline']
        self.assertEqual(base['request_count'], 2)
        self.assertEqual(base['total_tokens'], 750)
        self.assertAlmostEqual(base['nominal_cost_usd'], .00123)
        self.assertEqual(base['agent_type_spend']['subagent']['requests'], 1)
        self.assertEqual(base['source_spend']['claude']['requests'], 2)
        detectors = {d['id']: d for d in report['detectors']}
        self.assertIn('claude', detectors['low_effort_expensive']['details']['unsupported_sources'])
        self.assertEqual(detectors['compaction_churn']['details']['compaction_count'], 1)
        self.assertEqual(detectors['fat_tool_result']['findings'][0]['count'], 1)

    def test_codex_last_usage_cache_model_effort_and_compaction(self):
        report = self.run_report('codex')
        base = report['baseline']
        self.assertEqual(base['request_count'], 2)
        self.assertEqual(base['total_tokens'], 1320)
        self.assertAlmostEqual(base['cost_composition']['input']['nominal_cost_usd'], .0011)
        self.assertAlmostEqual(base['cost_composition']['cache_read']['nominal_cost_usd'], .00013)
        self.assertEqual(base['model_spend']['gpt-other']['requests'], 1)
        self.assertEqual(base['agent_type_spend']['subagent']['requests'], 2)
        rows, tools, compactions, warnings = analyze.load_local_source('codex', [self.codex], analyze.load_rates(self.rates), 0, int(NOW*1000), None, None)
        self.assertEqual([(r['model'], r['effort']) for r in rows], [('gpt-6.1-sol', 'low'), ('gpt-other', 'high')])
        self.assertEqual([r['input_tokens'] for r in rows], [400, 150])
        self.assertEqual(rows[1]['previous_timestamp'], rows[0]['timestamp'])
        self.assertNotEqual(rows[0]['entry_id'], rows[1]['entry_id'])
        self.assertEqual(tools[0]['tool_name'], 'exec_command')
        self.assertEqual(len(compactions), 1)

    def test_rates_plain_and_wrapped_exact_model(self):
        expected = self.run_report('codex', '--baseline')['baseline']['nominal_cost_usd']
        document = json.loads(self.rates.read_text())
        document['openai/gpt-6.1-sol'] = {'input_cost_per_token': 999}
        self.rates.write_text(json.dumps({'fetchedAtMs': 1, 'document': document}))
        self.assertEqual(self.run_report('codex', '--baseline')['baseline']['nominal_cost_usd'], expected)
        self.assertAlmostEqual(expected, .00243)

    def test_all_warns_for_absent_sources_and_defaults_to_all(self):
        shutil.rmtree(self.codex)
        report = self.run_report('all', '--baseline')
        self.assertEqual(analyze.parse_args([]).source, 'all')
        self.assertEqual(report['baseline']['request_count'], 2)
        self.assertTrue(any('codex' in w for w in report['parse_warnings']))
        self.assertEqual(set(report['baseline']['source_spend']), {'claude'})

    def test_filters_and_empty_local_period(self):
        self.assertEqual(self.run_report('claude', '--session', 'agent-one', '--baseline')['baseline']['request_count'], 1)
        self.assertEqual(self.run_report('codex', '--folder', 'absent', '--baseline')['baseline']['request_count'], 0)

    def test_previous_request_outside_period_and_unsupported_codex_signals(self):
        rows, _, _, _ = analyze.load_local_source(
            'codex', [self.codex], analyze.load_rates(self.rates),
            1792922460000, int(NOW*1000), None, None)  # after first request
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['previous_timestamp'], 1792922400000)
        report = self.run_report('codex')
        detectors = {d['id']: d for d in report['detectors']}
        self.assertIn('codex', detectors['cache_rebuild']['details']['unsupported_sources'])
        self.assertIn('codex', detectors['error_and_retry_spend']['details']['unsupported_sources'])

    def test_claude_standalone_summary_forms(self):
        main = self.claude / 'projects/synthetic/main.jsonl'
        rows = [json.loads(line) for line in main.read_text().splitlines()]
        for summary in (rows[-1], {'type': 'summary', 'timestamp': '2026-10-25T10:01:01Z'}):
            with self.subTest(summary_type=summary['type']):
                main.write_text(''.join(json.dumps(row)+'\n' for row in [*rows[:3], summary]))
                report = self.run_report('claude')
                compaction = next(d for d in report['detectors'] if d['id'] == 'compaction_churn')
                self.assertEqual(compaction['details']['compaction_count'], 1)

    def test_multiple_claude_roots_and_invalid_line_warning(self):
        other = self.root / 'claude-other'
        shutil.copytree(self.claude, other)
        with (other / 'projects/synthetic/main.jsonl').open('a') as handle:
            handle.write('{invalid synthetic line\n')
        report = self.run_report('claude', '--claude-dir', str(other), '--baseline')
        self.assertEqual(report['baseline']['request_count'], 2)
        self.assertTrue(any('invalid JSON' in w for w in report['parse_warnings']))


if __name__ == '__main__':
    unittest.main()
