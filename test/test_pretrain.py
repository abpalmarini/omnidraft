import unittest
import random
import torch
from autodraft.draft import Draft
from autodraft.pretrain import PretrainDataset, pretrain_collate
from autodraft.model import DeepDraftModel


class TestPretrain(unittest.TestCase):

    def test_correct_A_examples(self):
        pretrain_dataset = PretrainDataset(None)
        for seed in range(0, 10, 2):
            # Can simulate the draft that will be created initially.
            random.seed(seed)
            draft = Draft()
            for _ in range(len(draft.format) - 2):
                action = random.choice(draft.legal_actions())
                draft.apply(action)

            example = pretrain_dataset.create_example(seed)
            state, role_rs, combo_rs, action_hat, value_hat = example

            # Check that value_hat returned is in accordance with team B
            # playing optimally.
            draft_copy = draft.clone()
            draft_copy.apply(action_hat)
            # All team B actions (except the optimal one) should lead A
            # to getting a higher value than expected.
            for action in draft_copy.legal_actions():
                draft_copy_2 = draft_copy.clone()
                draft_copy_2.apply(action)
                self.assertLessEqual(value_hat, draft_copy_2.terminal_value())

            # Check that no other A action leads to higher value if team B
            # plays optimally.
            for action in draft.legal_actions():
                if action == action_hat:
                    continue
                draft_copy = draft.clone()
                draft_copy.apply(action)
                best_value = 1000
                for B_action in draft_copy.legal_actions():
                    draft_copy_2 = draft_copy.clone()
                    draft_copy_2.apply(B_action)
                    terminal_value = draft_copy_2.terminal_value()
                    # Team B wants to minimise the terminal value from team
                    # A's perspective.
                    if terminal_value < best_value:
                        best_value = terminal_value
                self.assertLess(best_value, value_hat)

            # Ensure correct state, role_rs and combo_rs are provided for
            # these targets.
            self.assertEqual(state[0], 1) # Team A selecting.
            self.assertEqual(state[1], 1) # Team A picking.
            self.assertEqual(state[3 + len(draft.format) - 2], 1) # Team A last pick.
            rr = draft.rewards['role'][0]
            self.assertAlmostEqual(role_rs[0][0], rr.A_value)
            self.assertAlmostEqual(role_rs[0][1], rr.B_value)
            cr = draft.rewards['combo'][0]
            self.assertAlmostEqual(combo_rs[0][0], cr.A_value)
            self.assertAlmostEqual(combo_rs[0][1], cr.B_value)

    def test_correct_B_examples(self):
        pretrain_dataset = PretrainDataset(None)
        for seed in range(1, 10, 2):
            random.seed(seed)
            draft = Draft()
            for _ in range(len(draft.format) - 1):
                action = random.choice(draft.legal_actions())
                draft.apply(action)

            example = pretrain_dataset.create_example(seed)
            state, role_rs, combo_rs, action_hat, value_hat = example

            # Check that target action leads to target value.
            draft_copy = draft.clone()
            draft_copy.apply(action_hat)
            self.assertEqual(-draft_copy.terminal_value(), value_hat)

            # Check that no other action leads to higher target value.
            for action in draft.legal_actions():
                if action == action_hat:
                    continue
                draft_copy = draft.clone()
                draft_copy.apply(action)
                self.assertLess(-draft_copy.terminal_value(), value_hat)

            # Ensure correct state, role_rs and combo_rs are provided for
            # these targets.
            self.assertEqual(state[0], 0) # Team B selecting.
            self.assertEqual(state[1], 1) # Team B picking.
            self.assertEqual(state[3 + len(draft.format) - 1], 1) # Team B last pick.
            rr = draft.rewards['role'][0]
            self.assertAlmostEqual(role_rs[0][0], rr.B_value)
            self.assertAlmostEqual(role_rs[0][1], rr.A_value)
            cr = draft.rewards['combo'][0]
            self.assertAlmostEqual(combo_rs[0][0], cr.B_value)
            self.assertAlmostEqual(combo_rs[0][1], cr.A_value)

    def test_correct_attention_mask(self):
        # From inspection example 1 is shorter than 0 so we pass it
        # through the model first, then with example 0 and check that
        # the outputs are the same.
        pretrain_dataset = PretrainDataset(None)
        solo = pretrain_collate([pretrain_dataset.create_example(1)])
        batch = pretrain_collate([pretrain_dataset.create_example(1),
                                  pretrain_dataset.create_example(0)])
        model = DeepDraftModel(Draft.state_dim(),
                                 Draft.role_reward_dim(),
                                 Draft.combo_reward_dim(),
                                 Draft.num_champs)
        model.eval()
        with torch.no_grad():
            solo_p, solo_v = model(solo.states, solo.role_rs, solo.combo_rs)
            batch_p, batch_v = model(batch.states, batch.role_rs,
                                     batch.combo_rs, batch.attention_mask)
        for i in range(Draft.num_champs):
            self.assertAlmostEqual(solo_p[0][i].item(), batch_p[0][i].item(), 5)
        self.assertAlmostEqual(solo_v[0].item(), batch_v[0].item(), 5)


if __name__ == '__main__':
    unittest.main()
