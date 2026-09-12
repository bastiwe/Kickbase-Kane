import unittest
from features.advisor_live import normalize_lineup
from features.lineup_optimizer import market_context


class LivePayloadTests(unittest.TestCase):
    def test_partial_lineup_uses_slots_excludes_bench(self):
        result = normalize_lineup({'it': [
            {'i': '1', 'pos': 1, 'lo': 0}, {'i': '2', 'pos': 2, 'lo': 4},
            {'i': '3', 'pos': 3, 'lo': 5}, {'i': '4', 'pos': 4, 'lo': 9},
            {'i': '5', 'pos': 2}, {'i': '6', 'pos': 3, 'lo': 11}]})
        self.assertEqual(result['formation'], '4-4-2')
        self.assertEqual(result['players'], ['1', '2', '3', '4'])
        self.assertNotIn('1', result['slots'])

    def test_empty_lineup_is_valid(self):
        self.assertEqual(normalize_lineup({'it': []})['players'], [])

    def test_legacy_payload(self):
        self.assertEqual(normalize_lineup({'type': '442', 'players': [{'i': 1}]}),
                         {'formation': '442', 'players': ['1']})

    def test_missing_list_is_not_an_empty_lineup(self):
        with self.assertRaises(ValueError):
            normalize_lineup({})

    def test_live_image_is_kept(self):
        player = market_context([{'i': '1', 'pos': 1, 'pim': 'content/file/player.png'}],
                                set(), None, {}, None, None)[0]
        self.assertEqual(player['image'], 'https://kickbase.b-cdn.net/content/file/player.png')
