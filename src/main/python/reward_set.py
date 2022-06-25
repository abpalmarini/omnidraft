import pickle
import re
from pathlib import Path

from game_constants import ROLES
from reward_models import TEAM_1, TEAM_2
from ai.draft_ai import DraftAI, RoleR, SynergyR, CounterR


class RewardSet:
    """
    Class with functionality for the creation, editing and saving of reward
    sets along with any cached transposition tables.
    """

    data_filename = "data.p"
    team_1_A_tt_filename = "team_1_A_tt.bin"
    team_2_A_tt_filename = "team_2_A_tt.bin"
    ai_roles = {role: i for i, role in enumerate(ROLES)}

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

    def save_rewards(self, role_rs, synergy_rs, counter_rs):
        """Save the given rewards to the instantiated reward set."""
        role_rs = sorted(self.ai_reward_format(r, 'role') for r in role_rs)
        synergy_rs = sorted(self.ai_reward_format(r, 'synergy') for r in synergy_rs)
        counter_rs = sorted(self.ai_reward_format(r, 'counter') for r in counter_rs)

        if (role_rs == self.data['role_rs'] and
            synergy_rs == self.data['synergy_rs'] and
            counter_rs == self.data['counter_rs']):
            # Nothing to do as rewards are already saved.
            return
        # Save new rewards and remove any (now invalid) transposition tables.
        self.data["role_rs"] = role_rs
        self.data["synergy_rs"] = synergy_rs
        self.data["counter_rs"] = counter_rs
        self.data["team_1_A_tt"] = None
        self.data["team_2_A_tt"] = None
        with open(self.path / self.data_filename, 'wb') as data_file:
            pickle.dump(self.data, data_file)

    def ai_reward_format(self, reward, reward_type):
        """
        Convert the reward classes used by the reward models to tuples ready to
        instantiate a DraftAI with.
        """
        # Scaled by 100 because users use 2 decimal places.
        def ai_value(value): 
            return int(value * 100)
        # Maps applicable roles to AI roles for heroes in a combo reward.
        def ai_heroes(heroes):
            _ai_heroes = []
            for hero_name, appl_roles in heroes:
                ai_appl_roles = [self.ai_roles[role] for role in appl_roles]
                _ai_heroes.append((hero_name, ai_appl_roles))
            return _ai_heroes
        # Team 1 set to team A for saved rewards
        A_value = ai_value(reward.team_1_value)
        B_value = ai_value(reward.team_2_value)
        if reward_type == 'role':
            role = self.ai_roles[reward.role]
            return RoleR(reward.name, role, A_value, B_value)
        elif reward_type == 'synergy':
            heroes = ai_heroes(reward.heroes)
            return SynergyR(heroes, A_value, B_value)
        elif reward_type == 'counter':
            heroes = ai_heroes(reward.heroes)
            foes = ai_heroes(reward.foes)
            return CounterR(heroes, foes, A_value, B_value)
        else:
            raise ValueError

    def get_draft_ai(self, side_A_team):
        if side_A_team == TEAM_1:
            role_rs = self.data["role_rs"]
            synergy_rs = self.data["synergy_rs"]
            counter_rs = self.data["counter_rs"]
            if self.data["team_1_A_tt"] is None:
                tt_file = None
            else:
                tt_file = str(self.path / self.team_1_A_tt_filename)
        else:
            def switch_values(r):
                if isinstance(r, RoleR):
                    return RoleR(r.hero_name, r.role, r.B_value, r.A_value)
                elif isinstance(r, SynergyR):
                    return SynergyR(r.heroes, r.B_value, r.A_value)
                elif isinstance(r, CounterR):
                    return CounterR(r.heroes, r.foes, r.B_value, r.A_value)
                else:
                    raise ValueError
            role_rs = [switch_values(r) for r in self.data["role_rs"]]
            synergy_rs = [switch_values(r) for r in self.data["synergy_rs"]]
            counter_rs = [switch_values(r) for r in self.data["counter_rs"]]
            if self.data["team_2_A_tt"] is None:
                tt_file = None
            else:
                tt_file = str(self.path / self.team_2_A_tt_filename)
        return DraftAI(
            self.data["draft_format"],
            role_rs,
            synergy_rs,
            counter_rs,
            tt_file,
        )
