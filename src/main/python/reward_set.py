import pickle
import re
from pathlib import Path


class RewardSet:
    """
    Class with functionality for the creation, editing and saving of reward
    sets along with any cached transposition tables.
    """

    data_filename = "data.p"

    def __init__(self, name):
        """
        Load the reward set with the given name to allow for access to, and 
        editing of, its data.
        """
        self.path = self.reward_sets_dir() / name
        if not self.path.is_dir():
            raise ValueError(f"No reward set called '{name}' exists.")
        with open(self.path / self.data_filename, 'rb') as data_file:
            self.data = pickle.load(data_file)

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

    @classmethod
    def new_reward_set(cls, name, team_tags, draft_format):
        """
        Create a new reward set entry with the given name, data and an empty
        set of rewards. The method creates a folder, saves the initial data
        and returns a RewardSet object for the newly created reward set.
        """
        if not re.match("^[A-Za-z0-9 _-]*$", name):  # ensure name can be used as a dirname
            raise ValueError("Name contains invalid characters.")

        path = cls.reward_sets_dir() / name
        path.mkdir()
        reward_set_data = {
            "name": name,
            "team_tags": team_tags,
            "draft_format": draft_format,
            "role_rs": [],
            "synergy_rs": [],
            "counter_rs": [],
            "team_1_A_tt": None,
            "team_2_A_tt": None,
        }
        with open(path / cls.data_filename, 'wb') as data_file:
            pickle.dump(reward_set_data, data_file)
        return RewardSet(name)
