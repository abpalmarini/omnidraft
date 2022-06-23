from pathlib import Path


class RewardSet:

    def __init__():
        pass

    @staticmethod
    def reward_sets_dir():
        """Return Path to dir where user created reward sets are saved."""
        return Path.home() / 'Omnidraft'

    @classmethod
    def create_reward_sets_dir(cls):
        """Create the top level folder to save all user created reward sets."""
        cls.reward_sets_dir().mkdir(exist_ok=True)

    @classmethod
    def all_reward_sets(cls):
        """Return a list of all the saved reward sets name/dirname."""
        return [p.name for p in cls.reward_sets_dir().iterdir() if p.is_dir()]
