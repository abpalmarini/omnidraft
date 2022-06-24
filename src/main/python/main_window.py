from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QIcon

from rewards_page import RewardsPage
from reward_models import RoleReward
from draft_page import DraftPage
from ai.draft_ai import A, B, PICK, BAN
from game_constants import ROLES

# @Temp heroes and draft format while I focus on building the main
# structure. Need a way to select game and load in all heroes @Later.
all_heroes = [
    "Aatrox", "Ahri", "Akali", "Akshan",
    "Alistar", "Amumu", "Anivia", "Annie",
    "Aphelios", "Ashe", "AurelionSol", "Azir",
    "Bard", "Blitzcrank", "Brand", "Braum",
    "Caitlyn", "Camille", "Cassiopeia", "Corki",
    "Darius", "Diana", "DrMundo", "Draven",
    "Ekko", "Elise", "Evelynn", "Ezreal", 
    "Fiddlesticks", "Fiora", "Fizz", "Galio",
    "Gangplank", "Garen",
]
team_tags = ('FNC', 'G2')
draft_format = [
    (A, BAN),
    (B, BAN),
    (A, BAN),
    (B, BAN),
    (A, PICK),
    (B, PICK),
    (B, PICK),
    (A, PICK),
    (A, PICK),
    (B, PICK),
    (B, PICK),
    (A, PICK),
    (A, PICK),
    (B, PICK),
]


class MainWindow(QMainWindow):

    def __init__(self, appctxt):
        super().__init__()

        # @Later I'll want to place files in a more organised structure
        hero_icons = {h: QIcon(appctxt.get_resource(h + '.png')) for h in all_heroes}
        role_icons = {r: QIcon(appctxt.get_resource(r + '.png')) for r in ROLES}
        arrow_icon = QIcon(appctxt.get_resource("right-arrow.png"))
        ban_icons = (
            QIcon(appctxt.get_resource("ban-0.png")),
            QIcon(appctxt.get_resource("ban-1.png")),
        )

        self.rewards_page = RewardsPage(hero_icons, role_icons, arrow_icon, team_tags)
        self.add_test_rewards()
        self.draft_page = DraftPage(
            hero_icons,
            ban_icons,
            ROLES,
            draft_format,
            team_tags,
            self.rewards_page.team_builder,
        )

        self.tab_widget = QTabWidget()
        self.tab_widget.addTab(self.rewards_page, "Rewards")
        self.tab_widget.addTab(self.draft_page, "Draft")
        self.tab_widget.currentChanged.connect(self.tab_changed)

        self.setCentralWidget(self.tab_widget)

    @Slot()
    def tab_changed(self, index):
        if index == 1:
            rewards = self.rewards_page.get_rewards()
            self.draft_page.set_rewards(*rewards)

    # @Temp method to add in some test rewards to help with implementing
    # other features.
    def add_test_rewards(self):
        role_model = self.rewards_page.reward_types[0].model
        role_model.add_reward(RoleReward(all_heroes[0], ROLES[0], 10, 10))
        role_model.add_reward(RoleReward(all_heroes[1], ROLES[1], 10, 0))
        role_model.add_reward(RoleReward(all_heroes[2], ROLES[2], 0, 10))
        role_model.add_reward(RoleReward(all_heroes[3], ROLES[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[4], ROLES[4], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[5], ROLES[0], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[6], ROLES[1], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[7], ROLES[2], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[8], ROLES[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[9], ROLES[4], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[10], ROLES[0], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[11], ROLES[1], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[12], ROLES[2], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[13], ROLES[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[14], ROLES[4], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[15], ROLES[0], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[16], ROLES[1], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[17], ROLES[2], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[18], ROLES[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[19], ROLES[4], 1, 1))
