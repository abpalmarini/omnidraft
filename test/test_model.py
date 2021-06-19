import unittest

import torch
import transformers

from deepdraft import positionless_bert


class TestPositionlessBert(unittest.TestCase):

    def test_position_invariance(self):
        config = transformers.BertConfig(hidden_size=12)
        model = positionless_bert.BertModel(config)

        x_0 = torch.rand(1, 2, config.hidden_size) # batch size, seq len, h
        x_1 = x_0.flip(1)
        self.assertTrue((x_0[0, 0] == x_1[0, 1]).all())

        model.eval()
        with torch.no_grad():
            y_0 = model(inputs_embeds=x_0).last_hidden_state
            y_1 = model(inputs_embeds=x_1).last_hidden_state

        self.assertTrue((y_0[0, 0] == y_1[0, 1]).all())


if __name__ == '__main__':
    unittest.main()
