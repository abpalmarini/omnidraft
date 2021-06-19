import os
import random
from collections import namedtuple

import torch
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from torch.nn.utils.rnn import pad_sequence
import pytorch_lightning as pl

from .draft import Draft


class PretrainDataset(Dataset):

    def __init__(self, seed_range, preload=False):
        self.seed_range = seed_range
        self.preload = preload

        # Optionally save and load example data beforehand. (Useful
        # for validation set where examples will be resued).
        if preload:
            data_dir = './data/'
            file_name = 'pretrain_{}_{}.pt'.format(seed_range[0], seed_range[-1])
            try:
                self.examples = torch.load(data_dir + file_name)
            except FileNotFoundError:
                self.examples = [self.create_example(seed) for seed in seed_range]
                os.makedirs(data_dir, exist_ok=True)
                torch.save(self.examples, data_dir + file_name)

    def __len__(self):
        return len(self.seed_range)

    def __getitem__(self, index):
        if self.preload:
            return self.examples[index]
        else:
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
            target_action = None
            target_value = -1000
            for action in draft.legal_actions():
                draft_copy = draft.clone()
                draft_copy.apply(action)
                # Find max value given team B plays optimally.
                _, B_terminal_value = optimal_team_B_final_action(draft_copy)
                terminal_value = -B_terminal_value
                if terminal_value > target_value:
                    target_value = terminal_value
                    target_action = action
        else:
            for _ in range(len(draft.format) - 1):
                action = random.choice(draft.legal_actions())
                draft.apply(action)
            target_action, target_value = optimal_team_B_final_action(draft)

        draft_state, role_rs, combo_rs = draft.make_nn_input()
        return draft_state, role_rs, combo_rs, target_action, target_value


PretrainBatch = namedtuple(
    'PretrainBatch',
    [                     # Sizes:
        'states',         # (batch_size, state_dim)
        'role_rs',        # (batch_size, num_role_rs, role_r_dim)
        'combo_rs',       # (batch_size, num_combo_rs, combo_r_dim)
        'target_actions', # (batch_size)
        'target_values',  # (batch_size)
        'attention_mask', # (batch_size, 1 + num_role_rs + num_combo_rs)
    ],
)


# Collates a list of input examples into tensors that the neural
# network can recieve.
def pretrain_collate(batch):
    batch_states = []
    batch_role_rs = []
    batch_combo_rs = []
    batch_target_actions = []
    batch_target_values = []

    for example in batch:
        state, role_rs, combo_rs, target_action, target_value = example
        batch_states.append(torch.from_numpy(state))
        batch_role_rs.append(torch.from_numpy(role_rs))
        batch_combo_rs.append(torch.from_numpy(combo_rs))
        batch_target_actions.append(target_action)
        batch_target_values.append(target_value)

    # The draft state, role rewards and combo rewards will be embedded
    # separately before being stacked to form the sequence input for
    # the transformer so they must be padded separately.
    states = torch.stack(batch_states)
    role_rs = pad_sequence(batch_role_rs, batch_first=True)
    combo_rs = pad_sequence(batch_combo_rs, batch_first=True)

    target_actions = torch.tensor(batch_target_actions)
    target_values = torch.tensor(batch_target_values).unsqueeze(1)

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
    masks = (state_mask, role_rs_mask, combo_rs_mask)
    attention_mask = torch.cat(masks, dim=1)

    return PretrainBatch(
        states,
        role_rs,
        combo_rs,
        target_actions,
        target_values,
        attention_mask,
    )


class PretrainDataModule(pl.LightningDataModule):

    def __init__(
        self,
        train_seed_range=range(10000, int(1e6)),
        preload_train_data=False,
        val_seed_range=range(0, 10000),
        preload_val_data=True,
        batch_size=32,
        num_workers=0,
        shuffle=False,
    ):
        super().__init__()

        self.train_seed_range = train_seed_range
        self.preload_train_data = preload_train_data
        self.val_seed_range = val_seed_range
        self.preload_val_data = preload_val_data

        self.batch_size = batch_size
        self.num_workers = num_workers
        self.shuffle = shuffle

    def prepare_data(self):
        # Create and download examples if required.
        PretrainDataset(self.train_seed_range, preload=self.preload_train_data)
        PretrainDataset(self.val_seed_range, preload=self.preload_val_data)

    def setup(self, stage=None):
        self.train_dataset = PretrainDataset(
            self.train_seed_range,
            preload=self.preload_train_data,
        )
        self.val_dataset = PretrainDataset(
            self.val_seed_range,
            preload=self.preload_val_data,
        )

    def train_dataloader(self):
        return DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            shuffle=self.shuffle,
            collate_fn=pretrain_collate,
        )

    def val_dataloader(self):
        return DataLoader(
            self.val_dataset,
            batch_size=self.batch_size,
            num_workers=self.num_workers,
            collate_fn=pretrain_collate,
        )


class LitPretrainModel(pl.LightningModule):

    def __init__(
        self,
        model,
        mse_value_weight=1,
        lr=1e-4,
        weight_decay=0.01,
        warmup_steps=0,
    ):
        super().__init__()

        self.model = model

        self.mse_value_weight = mse_value_weight
        self.lr = lr
        self.weight_decay = weight_decay
        self.warmup_steps = warmup_steps

    def training_step(self, batch, batch_idx):
        policy_logits, values = self.model(
            batch.states,
            batch.role_rs,
            batch.combo_rs,
            batch.attention_mask,
        )

        # Similar loss to AlphaZero except that in pretraining the model
        # is learning to predict the optimal final pick rather than
        # from self-play search results.
        policy_loss = F.cross_entropy(policy_logits, batch.target_actions)
        value_loss = F.mse_loss(values, batch.target_values) * self.mse_value_weight
        loss = policy_loss + value_loss

        self.log_dict({
            'train_policy_loss': policy_loss,
            'train_value_loss': value_loss,
            'train_loss': loss,
        })

        return loss

    def validation_step(self, batch, batch_idx):
        policy_logits, values = self.model(
            batch.states,
            batch.role_rs,
            batch.combo_rs,
            batch.attention_mask,
        )

        policy_loss = F.cross_entropy(policy_logits, batch.target_actions)
        value_loss = F.mse_loss(values, batch.target_values) * self.mse_value_weight
        loss = policy_loss + value_loss

        # Action prediction accuracy and how far off the model is from
        # estimating the correct value.
        predicted_actions = torch.argmax(policy_logits, dim=1)
        correct = torch.sum(predicted_actions == batch.target_actions)
        action_accuracy = correct / len(batch.target_actions)
        value_diff = (values - batch.target_values).abs().mean()

        self.log_dict({
            'val_policy_loss': policy_loss,
            'val_value_loss': value_loss,
            'val_loss': loss,
            'val_action_accuracy': action_accuracy,
            'val_value_diff': value_diff,
        })

    def configure_optimizers(self):
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=self.lr,
            weight_decay=self.weight_decay,
        )
        if self.warmup_steps:
            # Linear learning rate warmup.
            scheduler = torch.optim.lr_scheduler.LambdaLR(
                optimizer,
                lambda steps: min(1., (steps + 1) / self.warmup_steps),
            )
            return [optimizer], [{'scheduler': scheduler, 'interval': 'step'}]
        else:
            return optimizer
