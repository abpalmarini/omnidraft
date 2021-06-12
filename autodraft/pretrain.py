from draft import Draft
import random
import torch
from torch.utils.data import Dataset, DataLoader


class PretrainDataset(Dataset):

    def __init__(self, size, train=True):
        pass

    def __len__(self):
        pass

    def __getitem__(self, index):
        pass

    # To create an example input a draft with random rewards is created
    # and random actions are applied up to a team's final action. The
    # reamining actions are then brute forced to find the optimal
    # action and value targets.
    def create_example(self, seed):
        random.seed(seed)
        draft = Draft()

        def optimal_team_B_final_action(draft):
            optimal_action = None
            optimal_value = -1000
            for action in draft.legal_actions():
                simulator_draft = draft.clone()
                simulator_draft.apply(action)
                terminal_value = - simulator_draft.terminal_value()
                if terminal_value > optimal_value:
                    optimal_action = action
                    optimal_value = terminal_value
            return optimal_action, optimal_value

        # Create a team A example for even seeds and a team B for odd.
        if seed % 2 == 0:
            for _ in range(len(draft.format) - 2):
                action = random.choice(draft.legal_actions())
                draft.apply(action)
            target_action = None
            target_value = -1000
            for action in draft.legal_actions():
                simulator_draft = draft.clone()
                simulator_draft.apply(action)
                # Find max value given team B plays optimally.
                _, B_terminal_value = optimal_team_B_final_action(simulator_draft)
                terminal_value = - B_terminal_value
                if terminal_value > target_value:
                    target_value = terminal_value
                    target_action = action
        else:
            for _ in range(len(draft.format) - 1):
                action = random.choice(draft.legal_actions())
                draft.apply(action)
            target_action, target_value = optimal_team_B_final_action(draft)

        return *draft.make_nn_input(), target_action, target_value
