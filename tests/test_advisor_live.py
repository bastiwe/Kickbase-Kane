import json
import unittest
from unittest.mock import Mock, patch

import requests

from features.advisor_live import LiveKickbase
from features.ai_advisor import prepare_context, ask_advisor
from test_ai_advisor import fixture


class LiveTests(unittest.TestCase):
    def setup_live(self, acquired=False):
        report, state = fixture()
        report.update(user='me', league='league')
        client = LiveKickbase('PRIVATE_EMAIL', 'PRIVATE_PASSWORD')
        squad = [{'i': p['id'], 'fn': p['name'], 'pos': p['position'], 'tid': p['teamId'],
                  'mv': 200, 'isOwn': True} for p in report['players']]
        if acquired:
            squad.append({'i': 'target', 'fn': 'Target', 'pos': 2, 'tid': 'target', 'mv': 200})
        market = [{'i': 'target', 'fn': 'Target', 'pos': 2, 'tid': 'target', 'mv': 200, 'prc': 220, 'exs': 60},
                  {'i': 'bench', 'fn': 'Bench', 'pos': 2, 'mv': 200, 'ui': 'me'}]
        responses = {'/user/settings': {'u': {'i': 'me'}}, '/leagues/selection': {'it': [{'i': 'league'}]},
                     '/leagues/league/squad': {'it': squad}, '/leagues/league/market': {'it': market},
                     '/leagues/league/me/budget': {'b': 70}}
        client.get = Mock(side_effect=lambda path: responses[path])
        return client, report, state

    def test_live_values_replace_snapshot_without_mutation_and_exclude_owned_market(self):
        client, report, state = self.setup_live()
        fresh, plan, info = client.refresh(report, state)
        context = prepare_context(fresh, plan)
        self.assertEqual(context['checkedCurrentPlan']['endBudget'], 70)
        self.assertEqual(context['marketPlayers'][0]['askingPrice'], 220)
        self.assertEqual([p['id'] for p in context['marketPlayers']], ['target'])
        self.assertEqual(fresh['players'][0]['mv'], 200)
        self.assertEqual(fresh['players'][0]['l3'], 50)
        self.assertEqual(state['budget'], 50)
        self.assertEqual(report['players'][0]['mv'], 100)
        self.assertEqual(info['marketCount'], 1)
        self.assertNotIn('PRIVATE', json.dumps(context))

    def test_completed_buy_is_retained_without_double_charge(self):
        client, report, state = self.setup_live(acquired=True)
        report['players'].append(report['marketPlayers'][0])
        state['plans']['target'] = {'action': 'buy', 'price': 170, 'locked': True}
        fresh, plan, _ = client.refresh(report, state)
        self.assertEqual(plan['plans']['target']['action'], 'keep')
        self.assertTrue(plan['plans']['target']['locked'])
        context = prepare_context(fresh, plan)
        self.assertEqual(context['checkedCurrentPlan']['purchases'], 0)
        self.assertEqual(context['marketPlayers'], [])

    def test_wrong_account_stops_before_league_data(self):
        client, report, state = self.setup_live()
        report['user'] = 'someone_else'
        with self.assertRaisesRegex(RuntimeError, 'Konto oder Liga'):
            client.refresh(report, state)
        self.assertEqual(client.get.call_count, 2)

    def test_sold_player_on_market_is_removed_from_old_lineup(self):
        client, report, state = self.setup_live()
        original = client.get.side_effect
        def get(path):
            result = original(path)
            if path.endswith('/squad'):
                result['it'] = [p for p in result['it'] if p['i'] != '1']
            if path.endswith('/market'):
                result['it'].append({'i': '1', 'fn': 'Sold', 'pos': 2, 'mv': 200})
            return result
        client.get.side_effect = get
        fresh, plan, _ = client.refresh(report, state)
        self.assertIsNone(plan['selection'][1])
        self.assertNotIn('1', plan['plans'])
        self.assertIn('Startelf unvollständig.', prepare_context(fresh, plan)['checkedCurrentPlan']['warnings'])

    def test_rate_limit_does_not_fall_back_or_leak_request(self):
        client, report, state = self.setup_live()
        response = requests.Response()
        response.status_code = 429
        client.get.side_effect = requests.HTTPError('PRIVATE_PASSWORD', response=response)
        with self.assertRaisesRegex(RuntimeError, 'Anfragelimit') as error:
            client.refresh(report, state)
        self.assertNotIn('PRIVATE', str(error.exception))

    def test_locked_replaced_player_stays_and_costs_budget(self):
        report, state = fixture()
        state['plans']['1']['locked'] = True
        swap = prepare_context(report, state)['checkedSinglePlayerSwaps'][0]
        self.assertEqual(swap['replaceId'], '1')
        self.assertEqual(swap['endBudget'], -120)
        self.assertEqual(swap['rosterSize'], 13)

    @patch('features.ai_advisor.requests.post')
    def test_web_search_enabled_and_citations_returned(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': 'Regel mit Quelle.', 'annotations': [
                {'type': 'url_citation', 'url': 'https://www.kickbase.com/', 'title': 'Kickbase'},
                {'type': 'url_citation', 'url': 'javascript:bad', 'title': 'Bad'}]}]}]}
        result = ask_advisor('sk-test', 'gpt-5-mini', {}, 'Regeln?', [])
        self.assertEqual(post.call_args.kwargs['json']['tools'], [{'type': 'web_search'}])
        self.assertEqual(len(result['sources']), 1)


if __name__ == '__main__':
    unittest.main()
