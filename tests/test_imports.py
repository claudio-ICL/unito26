import unittest


class TestImports(unittest.TestCase):
    def test_scientific_packages(self):
        import numpy as np
        import scipy
        from scipy.stats import norm
        import pandas as pd
        self.assertTrue(isinstance(np.__version__, str))
        self.assertTrue(isinstance(pd.__version__, str))
        self.assertTrue(isinstance(scipy.__version__, str))
        self.assertAlmostEqual(norm.cdf(0.0), 0.5)
