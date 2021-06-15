import random
from collections import namedtuple

import torch
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence

from draft import Draft


class PretrainDataset(Dataset):

    def __init__(self, seed_range):
        self.seed_range = seed_range

    def __len__(self):
        return len(self.seed_range)

    def __getitem__(self, index):
        seed = self.seed_range[index]
        return self.create_example(seed)

    # To create the example input a draft with random rewards is created
    # and random actions are applied up to a team's final action. The
    # reamining actions are then brute forced to find the optimal action
    # and value targets.
    def create_example(self, seed):
        random.seed(seed)
        draft = Draft()

        def optimal_team_B_final_action(draft):
            optimal_action = None
            optimal_value = -1000
            for action in draft.legal_actions():
                draft_copy = draft.clone()
                draft_copy.apply(action)
                # Take negation of terminal value for team B perspective.
                terminal_value = -draft_copy.terminal_value()
                if terminal_value > optimal_value:
                    optimal_action = action
                    optimal_value = terminal_value
            return optimal_action, optimal_value

        # Creating an example for team A's final pick when seed is even
        # and for team B's final pick when odd.
        if seed % 2 == 0:
            for _ in range(len(draft.format) - 2):
                action = random.choice(draft.legal_actions())
                draft.apply(action)
            action_hat = None
            value_hat = -1000
            for action in draft.legal_actions():
                draft_copy = draft.clone()
                draft_copy.apply(action)
                # Find max value given team B plays optimally.
                _, B_terminal_value = optimal_team_B_final_action(draft_copy)
                terminal_value = -B_terminal_value
                if terminal_value > value_hat:
                    value_hat = terminal_value
                    action_hat = action
        else:
            for _ in range(len(draft.format) - 1):
                action = random.choice(draft.legal_actions())
                draft.apply(action)
            action_hat, value_hat = optimal_team_B_final_action(draft)

        return *draft.make_nn_input(), action_hat, value_hat


PretrainBatch = namedtuple(
    'PretrainBatch',
    [
        'states',       # size [batch_size, state_dim]
        'role_rs',      # size [batch_size, num_role_rs, role_r_dim]
        'combo_rs',     # size [batch_size, num_combo_rs, combo_r_dim]
        'action_hats',  # size [batch_size]
        'value_hats',   # size [batch_size]
        'padding_mask', # size [batch_size, 1 + num_role_rs + num_combo_rs]
    ],
)


# Collates a list of input examples into tensors that the neural
# network can recieve.
def pretrain_collate(batch):
    batch_states = []
    batch_role_rs = []
    batch_combo_rs = []
    batch_action_hats = []
    batch_value_hats = []

    for example in batch:
        state, role_rs, combo_rs, action_hat, value_hat = example
        batch_states.append(torch.from_numpy(state))
        batch_role_rs.append(torch.from_numpy(role_rs))
        batch_combo_rs.append(torch.from_numpy(combo_rs))
        batch_action_hats.append(action_hat)
        batch_value_hats.append(value_hat)

    # The draft state, role rewards and combo rewards will be embedded
    # separately before being stacked to form the sequence input for
    # the transformer so they must be padded separately.
    states = torch.stack(batch_states)
    role_rs = pad_sequence(batch_role_rs, batch_first=True)
    combo_rs = pad_sequence(batch_combo_rs, batch_first=True)

    action_hats = torch.tensor(batch_action_hats)
    value_hats = torch.tensor(batch_value_hats)

    # The fact that role and combo rewards got padded separately must
    # be taken into account when creating the attention mask for the
    # final sequence (state embedding, followed by role rewards,
    # followed by combo rewards). Here, 1 is for elements that can be
    # attended to and 0 if they are to be ignored.
    state_mask = torch.ones((len(batch), 1))
    attended_role_rs = [torch.ones(len(rs)) for rs in batch_role_rs]
    role_rs_mask = pad_sequence(attended_role_rs, batch_first=True)
    attended_combo_rs = [torch.ones(len(rs)) for rs in batch_combo_rs]
    combo_rs_mask = pad_sequence(attended_combo_rs, batch_first=True)
    padding_mask = torch.cat((state_mask, role_rs_mask, combo_rs_mask), dim=1)

    return PretrainBatch(states,
                         role_rs,
                         combo_rs,
                         action_hats,
                         value_hats,
                         padding_mask)
