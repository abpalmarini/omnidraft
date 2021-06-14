import random
import torch
from torch.utils.data import Dataset, DataLoader


class PretrainDataset(Dataset):

    def __init__(self, draft_class, seed_range):
        self.draft_class = draft_class
        self.seed_range = seed_range

    def __len__(self):
        return len(self.seed_range)

    def __getitem__(self, index):
        return self.create_example(self.seed_range[index])

    # To create the example input a draft with random rewards is created
    # and random actions are applied up to a team's final action. The
    # reamining actions are then brute forced to find the optimal action
    # and value targets.
    def create_example(self, seed):
        random.seed(seed)
        draft = self.draft_class()

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
