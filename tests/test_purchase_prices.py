import unittest

import pandas as pd

from features.predictions.predictions import extract_purchase_price_column


class PurchasePricesTests(unittest.TestCase):
    def test_live_gain_loss_recovers_old_purchases_and_zero_gain(self):
        squad = pd.DataFrame([
            {'mv': 11643600, 'mvgl': -3711956},
            {'mv': 27490469, 'mvgl': -85206},
            {'mv': 59603361, 'mvgl': -4096644},
            {'mv': 46847938, 'mvgl': -10727619},
            {'mv': 500000, 'mvgl': 0},
            {'mv': 500000},
        ])
        result = extract_purchase_price_column(squad)
        self.assertEqual(result.iloc[:5].tolist(), [15355556, 27575675, 63700005, 57575557, 500000])
        self.assertTrue(pd.isna(result.iloc[5]))

    def test_invalid_or_missing_gain_loss_stays_unknown(self):
        squad = pd.DataFrame([
            {'mv': 100, 'mvgl': 200},
            {'mv': 100, 'purchasePrice': 80},
            {'mv': 100, 'mvgl': float('inf')},
        ])
        self.assertTrue(extract_purchase_price_column(squad).isna().all())


if __name__ == '__main__':
    unittest.main()
