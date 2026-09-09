import json
import threading
import unittest
from unittest.mock import Mock, patch

import requests

from advisor_server import create_server, read_report
from features.ai_advisor import ask_advisor, prepare_context


def fixture():
    positions = [1] + [2]*4 + [3]*4 + [4]*2
    players = [{'id': str(i), 'name': f'Player {i}', 'position': pos, 'teamId': str(i), 'owned': True,
                'mv': 100, 'l3': 50, 'season': 30} for i, pos in enumerate(positions)]
    players.append({'id': 'bench', 'name': 'Bench', 'position': 2, 'teamId': 'bench', 'owned': True, 'mv': 100, 'l3': 20})
    market = [{'id': 'target', 'name': 'Target', 'position': 2, 'teamId': 'target', 'owned': False,
               'mv': 150, 'askingPrice': 170, 'l3': 80}]
    report = {'players': players, 'marketPlayers': market, 'generated': 'TEST', 'budget': 50}
    state = {'formation': '4-4-2', 'mode': 'l3', 'budget': 50, 'limit': 3, 'sellbench': False,
             'selection': [str(i) for i in range(11)], 'plans': {p['id']: {'action': 'keep', 'price': 100} for p in players}}
    return report, state


class AdviserTests(unittest.TestCase):
    def test_current_plan_and_swap_are_calculated_not_taken_from_browser(self):
        report, state = fixture()
        state['endBudget'] = 999999
        context = prepare_context(report, state)
        self.assertEqual(context['checkedCurrentPlan']['endBudget'], 50)
        self.assertEqual(context['checkedSinglePlayerSwaps'][0]['endBudget'], -20)
        self.assertEqual(context['checkedSinglePlayerSwaps'][0]['pointsGain'], 30)
        state['sellbench'] = True
        self.assertEqual(prepare_context(report, state)['checkedSinglePlayerSwaps'][0]['endBudget'], 80)

    def test_negative_cash_within_team_value_limit_is_allowed(self):
        report, state = fixture()
        state['budget'] = -20
        report['maxNegative'] = -30
        result = prepare_context(report, state)['checkedCurrentPlan']
        self.assertEqual(result['budgetStatus'], 'im erlaubten Minus')
        self.assertNotIn('Minuslimit überschritten.', result['warnings'])

    def test_missing_price_and_illegal_positions_are_not_accepted_as_valid(self):
        report, state = fixture()
        state['plans']['bench'] = {'action': 'sell', 'price': None}
        self.assertIsNone(prepare_context(report, state)['checkedCurrentPlan']['endBudget'])
        state['selection'][0] = '2'
        with self.assertRaises(ValueError):
            prepare_context(report, state)

    def test_locked_bench_player_is_not_sold_by_bank_sale(self):
        report, state = fixture()
        state['sellbench'] = True
        state['plans']['bench']['locked'] = True
        context = prepare_context(report, state)
        self.assertIn('bench', context['checkedCurrentPlan']['retainedIds'])
        self.assertNotIn('bench', context['checkedCurrentPlan']['soldIds'])

    def test_existing_planned_purchase_is_not_charged_twice_in_swap(self):
        report, state = fixture()
        report['players'].append(report['marketPlayers'][0])
        state['plans']['target'] = {'action': 'buy', 'price': 170}
        context = prepare_context(report, state)
        self.assertEqual(context['checkedCurrentPlan']['endBudget'], -120)
        self.assertEqual(context['checkedSinglePlayerSwaps'][0]['endBudget'], -20)

    def test_unrelated_fields_and_private_ids_are_not_sent(self):
        report, state = fixture()
        report['secret'] = 'DO_NOT_SEND'
        report['user'] = 'PRIVATE_USER_ID'
        context = prepare_context(report, state)
        self.assertNotIn('DO_NOT_SEND', json.dumps(context))
        self.assertNotIn('PRIVATE_USER_ID', json.dumps(context))

    @patch('features.ai_advisor.requests.post')
    def test_api_request_is_stateless_and_parses_output_messages(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'status': 'completed', 'output': [{'type': 'reasoning'},
            {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Dein Plan.'}]}]}
        answer = ask_advisor('sk-test', 'gpt-5-mini', {}, 'Was tun?', [])
        self.assertEqual(answer['answer'], 'Dein Plan.')
        request = post.call_args.kwargs
        self.assertFalse(request['json']['store'])
        self.assertNotIn('sk-test', json.dumps(request['json']))
        self.assertEqual(post.call_args.args[0], 'https://api.openai.com/v1/responses')

    @patch('features.ai_advisor.requests.post')
    def test_model_context_hides_internal_player_ids(self, post):
        report, state = fixture()
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': 'Verstanden.'}]}]}
        ask_advisor('sk-test', 'gpt-5-mini', prepare_context(report, state), 'Wer ist sinnvoll?', [])
        payload = json.dumps(post.call_args.kwargs['json']['input'], ensure_ascii=False)
        self.assertIn('Player 0', payload)  # names remain readable for the adviser
        self.assertNotIn('"id"', payload)
        self.assertNotIn('retainedIds', payload)

    def test_import_extracts_only_data_and_does_not_execute_scripts(self):
        report, _ = fixture()
        self.assertEqual(read_report('<script>alert(1)</script><script id="data">'+json.dumps(report)+'</script>'), report)


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.report, self.state = fixture()
        self.server = create_server(0, self.report, 'sk-test')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.headers = {'Origin': self.server.origin, 'X-Advisor-Token': self.server.csrf}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_server_never_serves_keys_or_workspace_files(self):
        self.assertEqual(requests.get(self.server.origin+'/.env').status_code, 404)
        response = requests.get(self.server.origin+'/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('sk-test', response.text)
        self.assertEqual(requests.post(self.server.origin+'/api/key', json={'key': 'sk-other'}).status_code, 403)
        foreign = {**self.headers, 'Origin': 'https://example.com'}
        self.assertEqual(requests.post(self.server.origin+'/api/key', headers=foreign, json={'key': 'sk-other'}).status_code, 403)

    @patch('advisor_server.ask_advisor', return_value={'answer': 'Test advice'})
    def test_followup_uses_changed_plan_and_old_report_tabs_are_rejected(self, ask):
        body = {'revision': 1, 'message': 'Nächster Schritt?', 'history': [], 'state': self.state}
        self.assertEqual(requests.post(self.server.origin+'/api/chat', headers=self.headers, json=body).status_code, 200)
        self.state['budget'] = -50
        response = requests.post(self.server.origin+'/api/chat', headers=self.headers, json=body)
        self.assertEqual(response.json()['checkedPlan']['endBudget'], -50)
        imported = '<script id="data">'+json.dumps(self.report)+'</script>'
        requests.post(self.server.origin+'/api/report', headers=self.headers, json={'html': imported})
        self.assertEqual(requests.post(self.server.origin+'/api/chat', headers=self.headers, json=body).status_code, 409)
