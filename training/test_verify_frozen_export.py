import unittest
import numpy as np
from verify_frozen_export import metrics, bootstrap

class MetricsTests(unittest.TestCase):
    def test_auc_direction_and_ties(self):
        y = np.array([0, 0, 1, 1])
        self.assertEqual(metrics(y, np.array([.1, .2, .8, .9]))['roc_auc'], 1.)
        self.assertEqual(metrics(y, np.array([.9, .8, .2, .1]))['roc_auc'], 0.)
        self.assertEqual(metrics(y, np.array([.5]*4))['roc_auc'], .5)

    def test_bootstrap_reproducible(self):
        y = np.array([0, 0, 1, 1])
        p = np.array([.1, .2, .8, .9])
        a = bootstrap(y, p, draws=10)
        self.assertEqual(a, bootstrap(y, p, draws=10))
        self.assertEqual(a['roc_auc'], [1., 1.])

if __name__ == '__main__':
    unittest.main()
