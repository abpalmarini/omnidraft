import torch
import torch.nn as nn

from transformers import BertConfig
from .positionless_bert import BertModel


# This model takes in a draft state and any number of supplied rewards
# to draft in accordance with.
class DeepDraftModel(nn.Module):

    def __init__(self, state_dim, role_r_dim, combo_r_dim, num_champs):
        super().__init__()

        config = BertConfig()

        self.embed_state = nn.Linear(state_dim, config.hidden_size)
        self.embed_role_rs = nn.Linear(role_r_dim, config.hidden_size)
        self.embed_combo_rs = nn.Linear(combo_r_dim, config.hidden_size)

        # Default HuggingFace BERT with token type and position
        # embeddings removed. The transformer will be reasoning over
        # the state and provided rewards where position is irrelevant.
        self.transformer = BertModel(config)

        # Simple policy and value heads that will be applied to the
        # output hidden representation of the draft state.
        self.policy_head = nn.Linear(config.hidden_size, num_champs)
        self.value_head = nn.Linear(config.hidden_size, 1)

    def forward(self, states, role_rs, combo_rs, attention_mask=None):
        # Embed the state, role rewards and combo rewards separately.
        state_embeddings = self.embed_state(states)
        role_rs_embeddings = self.embed_role_rs(role_rs)
        combo_rs_embeddings = self.embed_combo_rs(combo_rs)

        # Concatenate the state and reward embeddings along the sequence
        # dimension (1).
        state_embeddings = state_embeddings.unsqueeze(dim=1)
        embeddings = (state_embeddings, role_rs_embeddings, combo_rs_embeddings)
        embeddings = torch.cat(embeddings, dim=1)

        # A layernorm and dropout will still be applied to embeddings
        # before being passed to encoder.
        transformer_outputs = self.transformer(
            inputs_embeds=embeddings,
            attention_mask=attention_mask,
        )

        # Extract the final hidden representation of the draft state
        # (first element in sequence) to be used for predicting the
        # policy and expected value.
        state_output = transformer_outputs.pooler_output

        policy_logits = self.policy_head(state_output)
        value = self.value_head(state_output)

        return policy_logits, value
