import torch
import torch.nn as nn

from transformers import BertConfig
from .positionless_bert import BertModel


# The model takes in a draft state and any number of supplied rewards
# to draft in accordance with--outputting a policy prediction on the
# best champ to select and how much value it believes it will receive.
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
        self.transformer = BertModel(config, add_pooling_layer=False)

        self.policy_head = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size),
            nn.Tanh(),
            nn.Linear(config.hidden_size, num_champs),
        )
        self.value_head = nn.Sequential(
            nn.Linear(config.hidden_size, config.hidden_size),
            nn.Tanh(),
            nn.Linear(config.hidden_size, 1),
        )

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

        # A layernorm and dropout will still be applied to the
        # embeddings before being passed to the encoder blocks.
        transformer_outputs = self.transformer(
            inputs_embeds=embeddings,
            attention_mask=attention_mask,
        )

        # Extract the final hidden representation of the draft state
        # (first element in sequence) which will have aggregated
        # knowledge from the rewards to predict the policy and value.
        sequence_output = transformer_outputs[0] # (batch size, sequence size, hidden size)
        draft_state_output = sequence_output[:, 0, :]

        # Send the draft state output (body) to the two heads.
        policy_logits = self.policy_head(draft_state_output)
        values = self.value_head(draft_state_output)

        return policy_logits, values
