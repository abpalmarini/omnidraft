from fbs_runtime.application_context.PySide6 import ApplicationContext
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QIcon

import sys

from rewards_page import RewardsPage
from reward_models import RoleReward
from draft_page import DraftPage
from ai.draft_ai import A, B, PICK, BAN


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
all_roles = ("Top Laner", "Jungler", "Mid Laner", "Bot Laner", "Support")
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


# @Temp way to allow the role rewards created in the rewards page to
# be used in the draft page that simply takes the current rewards
# stored in each model when switching to the draft page. @Later I
# will need to implement an approach that handles saving of the TT
# if required while also allowing for a smooth experience of moving
# back and forth between adjusting rewards and running search.
# There will also be no need to create a new DraftAI object each time
# the user switches to the draft page if nothing has changed.
class TabWidget(QTabWidget):

    def __init__(self, rewards_page, draft_page):
        super().__init__()

        self.rewards_page = rewards_page
        self.add_test_rewards()
        self.draft_page = draft_page
        self.addTab(rewards_page, "Rewards")
        self.addTab(draft_page, "Draft")

        self.currentChanged.connect(self.handle_current_changed)

    @Slot()
    def handle_current_changed(self, index):
        if index == 1:
            rewards = self.rewards_page.get_rewards()
            self.draft_page.set_rewards(*rewards)

    # @Temp method to add in some test rewards to help with implementing
    # other features.
    def add_test_rewards(self):
        role_model = self.rewards_page.reward_types[0].model
        role_model.add_reward(RoleReward(all_heroes[0], all_roles[0], 10, 10))
        role_model.add_reward(RoleReward(all_heroes[1], all_roles[1], 10, 0))
        role_model.add_reward(RoleReward(all_heroes[2], all_roles[2], 0, 10))
        role_model.add_reward(RoleReward(all_heroes[3], all_roles[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[4], all_roles[4], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[5], all_roles[0], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[6], all_roles[1], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[7], all_roles[2], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[8], all_roles[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[9], all_roles[4], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[10], all_roles[0], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[11], all_roles[1], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[12], all_roles[2], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[13], all_roles[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[14], all_roles[4], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[15], all_roles[0], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[16], all_roles[1], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[17], all_roles[2], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[18], all_roles[3], 1, 1))
        role_model.add_reward(RoleReward(all_heroes[19], all_roles[4], 1, 1))


if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext

    # icons
    hero_icons = {h: QIcon(appctxt.get_resource(h + '.png')) for h in all_heroes}
    role_icons = {r: QIcon(appctxt.get_resource(r + '.png')) for r in all_roles}
    arrow_icon = QIcon(appctxt.get_resource("right-arrow.png"))
    ban_icons = [QIcon(appctxt.get_resource("ban-0.png")), QIcon(appctxt.get_resource("ban-1.png"))]

    # pages
    rewards_page = RewardsPage(hero_icons, role_icons, arrow_icon, team_tags)
    draft_page = DraftPage(hero_icons, ban_icons, all_roles, draft_format, team_tags, rewards_page.team_builder)
    tab_widget = TabWidget(rewards_page, draft_page)

    window = QMainWindow()
    window.setCentralWidget(tab_widget)
    window.resize(1600, 800)
    window.show()

    exit_code = appctxt.app.exec()      # 2. Invoke appctxt.app.exec()
    sys.exit(exit_code)
