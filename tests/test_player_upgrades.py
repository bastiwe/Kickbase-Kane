import unittest
import pandas as pd
import os
from unittest.mock import patch
from features.notifier import send_mail
from features.player_upgrades import player_upgrades


class PlayerUpgradeTests(unittest.TestCase):
    def test_report_shows_lineup_and_concrete_upgrade_without_goalkeeper_hint(self):
        positions = [1] + [2]*3 + [3]*5 + [4]*2
        squad = pd.DataFrame([dict(player_id=i, first_name='', last_name=f'Own{i}',
            position=pos, team_name=f'Team{i}', player_status='Fit', mv=1000000,
            kickbase_average_points=88 if pos == 1 else 50,
            last_3_points=999 if pos == 1 else 150,
            predicted_mv_target=0) for i, pos in enumerate(positions)])
        market = pd.DataFrame([
            dict(player_id=100, first_name='', last_name='LowerKeeper', position=1,
                 team_name='Market', player_status='Fit', mv=1000000,
                 kickbase_average_points=82, predicted_mv_target=0),
            dict(player_id=101, first_name='', last_name='UpgradeDefender', position=2,
                 team_name='Market', player_status='Fit', mv=2000000,
                 kickbase_average_points=80, predicted_mv_target=0),
        ])
        with patch.dict(os.environ, {'EMAIL_USER':'fake@example.com', 'EMAIL_PASS':'fake'}), \
                patch('features.notifier.smtplib.SMTP') as smtp:
            send_mail(pd.DataFrame(), market, squad, 'fake@example.com')
        message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
        html = message.get_body(preferencelist=('html',)).get_content()
        advice = html.split('Kaderanalyse</h3>')[1].split('Mögliche Tausche:</b>')[1].split('</div>')[0]
        self.assertIn('UpgradeDefender', advice)
        self.assertIn('statt', advice)
        self.assertIn('+30.0', advice)
        self.assertNotIn('LowerKeeper', advice)
        self.assertIn('Beste Elf', html)
        self.assertNotIn('niedrigsten Punkteschnitt', html)

    def compare(self, starters, market, owned=()):
        return player_upgrades(pd.DataFrame(starters), pd.DataFrame(market), int, owned)

    def test_lower_goalkeeper_average_is_not_an_upgrade(self):
        self.assertEqual(self.compare(
            [{'position': 1, 'kickbase_average_points': 88, 'last_3_points': 277}],
            [{'position': 1, 'kickbase_average_points': 82, 'last_3_points': 999}]), [])

    def test_replaces_individual_defender_not_group_average(self):
        result = self.compare(
            [{'position': 2, 'player_id': 1, 'kickbase_average_points': 169},
             {'position': 2, 'player_id': 2, 'kickbase_average_points': 30}],
            [{'position': 2, 'player_id': 3, 'kickbase_average_points': 80}])
        self.assertEqual(result[0]['starter']['player_id'], 2)
        self.assertEqual(result[0]['gain'], 50)

    def test_excludes_other_position_injured_and_owned_players(self):
        self.assertEqual(self.compare(
            [{'position': 2, 'kickbase_average_points': 30}],
            [{'position': 3, 'kickbase_average_points': 200},
             {'position': 2, 'player_status': 'Verletzt', 'kickbase_average_points': 200},
             {'position': 2, 'player_id': 7, 'kickbase_average_points': 200}], [7]), [])

    def test_no_mixing_season_and_previous_season(self):
        self.assertEqual(self.compare(
            [{'position': 2, 'kickbase_average_points': 30}],
            [{'position': 2, 'last_season_avg_points': 100}]), [])

    def test_equal_average_and_missing_points_are_not_upgrades(self):
        self.assertEqual(self.compare(
            [{'position': 2, 'kickbase_average_points': 30}],
            [{'position': 2, 'kickbase_average_points': 30}, {'position': 2}]), [])

    def test_full_club_limit_allows_same_club_swap_only(self):
        result = self.compare(
            [{'position': 2, 'team_name': 'A', 'kickbase_average_points': 30}],
            [{'position': 2, 'team_name': 'B', 'team_limit_warning': 'Vereinslimit voll',
              'kickbase_average_points': 200},
             {'position': 2, 'team_name': 'A', 'team_limit_warning': 'Vereinslimit voll',
              'kickbase_average_points': 80}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['candidate']['team_name'], 'A')
