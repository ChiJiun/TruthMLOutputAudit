import copy
import unittest

from run_experiment import audit_report
from privacy_boundary import scalar_floor, scalar_epsilon, scenario


class AuditTests(unittest.TestCase):
    def fixture(self):
        attacks = ['duplicate_submission','client_swap','round_swap','model_swap',
                   'noisy_update_tamper','corrupt_proof','retry_after_failure']
        return {'clients':1,'rounds':1,
                'updates':[{'round':0,'client':0,'gate':'accepted','proof_sha256':'x'}],
                'probes':[{'round':0,'client':0,'attack':a,'gate':'rejected',
                           'cryptographic_verified':a in ['duplicate_submission','retry_after_failure']} for a in attacks],
                'trajectory':[{'same_noisy_updates_without_gate_max_abs_difference':0}]}

    def test_incomplete_or_duplicate_attack_matrix_rejected(self):
        valid = self.fixture()
        audit_report(valid)
        bad = copy.deepcopy(valid)
        bad['probes'][-1] = bad['probes'][0]
        with self.assertRaises(AssertionError):
            audit_report(bad)
        bad = copy.deepcopy(valid)
        bad['updates'] = []
        with self.assertRaises(AssertionError):
            audit_report(bad)

    def test_replay_must_pass_crypto_but_fail_state(self):
        bad = self.fixture()
        bad['probes'][0]['cryptographic_verified'] = False
        with self.assertRaises(AssertionError):
            audit_report(bad)

    def test_support_floor_and_parameter_monotonicity(self):
        self.assertAlmostEqual(float(scalar_floor(16)), 33/2**32)
        self.assertIsNone(scalar_epsilon(16,1e-10))
        short, long = scenario(4,3,16),scenario(4,10,16)
        self.assertLess(short['basic_composition_epsilon'],long['basic_composition_epsilon'])
        self.assertTrue(scenario(385,20,16)['below_support_floor'])


if __name__ == '__main__':
    unittest.main()
