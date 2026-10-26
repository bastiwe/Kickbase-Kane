import json
import unittest
from datetime import date
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
        client.player_profiles = Mock(return_value={})
        client.player_market_changes = Mock(return_value={'0': 15, 'target': -10})
        client.player_purchase_prices = Mock(return_value={})
        fresh, plan, info = client.refresh(report, state)
        context = prepare_context(fresh, plan)
        self.assertEqual(context['checkedCurrentPlan']['endBudget'], 70)
        self.assertEqual(context['marketPlayers'][0]['askingPrice'], 220)
        self.assertEqual([p['id'] for p in context['marketPlayers']], ['target'])
        self.assertEqual(fresh['players'][0]['mv'], 200)
        self.assertEqual(fresh['players'][0]['l3'], 50)
        self.assertEqual(fresh['players'][0]['lastMvChange'], 15)
        self.assertEqual(fresh['marketPlayers'][0]['lastMvChange'], -10)
        requested_ids = client.player_market_changes.call_args.args[0]
        self.assertIn('target', requested_ids)
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

    def test_missing_live_name_keeps_full_report_identity(self):
        client, report, state = self.setup_live()
        report['players'][1]['name'] = 'Chrislain Matsima'
        original = client.get.side_effect
        def get(path):
            result = original(path)
            if path.endswith('/squad'):
                for player in result['it']:
                    player.pop('fn', None)
            return result
        client.get.side_effect = get
        fresh, _, _ = client.refresh(report, state)
        self.assertEqual(fresh['players'][1]['name'], 'Chrislain Matsima')

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

    def test_squad_value_history_uses_complete_manager_transfers_and_live_anchor(self):
        client = LiveKickbase('PRIVATE_EMAIL', 'PRIVATE_PASSWORD')
        transfers = [
            {'pi': '2', 'tty': 1, 'trp': 200, 'dt': '2026-08-17T08:00:00Z'},
            {'pi': '3', 'tty': 2, 'trp': 300, 'dt': '2026-08-16T08:00:00Z'},
        ]
        responses = {
            '/leagues/league/squad': {'it': [
                {'i': '1', 'mv': 140}, {'i': '2', 'mv': 220},
            ]},
            '/user/settings': {'u': {'i': 'me', 'unm': 'Manager'}},
            '/leagues/league/managers/me/transfer?start=0': {'it': transfers},
        }
        client.get = Mock(side_effect=lambda path: responses[path])

        epoch = date(1970, 1, 1)
        def entry(day, value):
            return {'dt': (date.fromisoformat(day) - epoch).days, 'mv': value}
        client.player_market_histories = Mock(return_value={
            '1': [entry('2026-08-15', 100), entry('2026-08-16', 110),
                  entry('2026-08-17', 120), entry('2026-08-18', 130)],
            '2': [entry('2026-08-15', 190), entry('2026-08-16', 200),
                  entry('2026-08-17', 210), entry('2026-08-18', 215)],
            '3': [entry('2026-08-15', 300), entry('2026-08-16', 310),
                  entry('2026-08-17', 320), entry('2026-08-18', 330)],
        })

        with patch.dict('os.environ', {'KICK_LEAGUE_START_DATE': '2026-08-15'}):
            result = client.squad_value_history('league', ['stale-id'])

        by_day = {point['date']: point['value'] for point in result['series']}
        self.assertEqual(by_day['2026-08-15'], 400)
        self.assertEqual(by_day['2026-08-16'], 110)
        self.assertEqual(by_day['2026-08-17'], 330)
        self.assertEqual(result['series'][-1]['value'], 360)
        self.assertIn('360 €', result['note'])
        requested = [call.args[0] for call in client.get.call_args_list]
        self.assertNotIn('/leagues/league/activitiesFeed?max=5000', requested)
        self.assertIn('/leagues/league/managers/me/transfer?start=0', requested)

    def test_recent_transfers_are_live_enriched_and_overpay_is_calculated(self):
        client = LiveKickbase('PRIVATE_EMAIL', 'PRIVATE_PASSWORD')
        client.get = Mock(return_value={'af': [
            {'t': 22, 'dt': '2026-10-26T10:30:00Z', 'data': {}},
            {'t': 15, 'dt': '2026-10-26T10:00:00Z', 'data': {
                'pi': '7', 'pn': 'Live Name', 'byr': 'Anna',
                'trp': 12_000_000, 'mv': 10_000_000,
            }},
            {'t': 15, 'dt': '2026-10-26T09:00:00Z', 'data': {
                'pi': '8', 'slr': 'Ben', 'byr': 'Chris', 'trp': 8_500_000,
            }},
        ]})
        client.player_profiles = Mock(return_value={
            '7': {'pim': 'players/7.png'},
            '8': {'fn': 'Fallback', 'ln': 'Name', 'pim': 'players/8.png'},
        })
        epoch = date(1970, 1, 1)
        client.player_market_histories = Mock(return_value={'8': [
            {'dt': (date(2026, 10, 25) - epoch).days, 'mv': 8_000_000},
        ]})

        result = client.recent_transfers('league')

        self.assertEqual(len(result['transfers']), 2)
        first, second = result['transfers']
        self.assertEqual((first['from'], first['to']), ('Kickbase', 'Anna'))
        self.assertEqual(first['overpay'], 2_000_000)
        self.assertEqual(second['playerName'], 'Fallback Name')
        self.assertEqual(second['marketValue'], 8_000_000)
        self.assertEqual(second['overpay'], 500_000)
        self.assertTrue(first['image'].startswith('https://'))
        client.get.assert_called_once_with('/leagues/league/activitiesFeed?max=100')

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
