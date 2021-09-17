from fbs_runtime.application_context.PySide6 import ApplicationContext
from PySide6.QtWidgets import QMainWindow, QTabWidget
from PySide6.QtGui import QIcon

import sys

from rewards_page import RewardsPage
from draft_page import DraftPage
from ai.draft_ai import A, B, PICK, BAN


# @Temp heroes and draft format while I focus on building the main
# structure. Need a way to select game and load in all heroes @Later.
all_heroes = [
    'Aatrox', 'Ahri', 'Akali', 'Akshan',
    'Alistar', 'Amumu', 'Anivia', 'Annie',
    'Aphelios', 'Ashe', 'AurelionSol', 'Azir',
    'Bard', 'Blitzcrank', 'Brand', 'Braum',
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


if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext

    # icons
    hero_icons = {h: QIcon(appctxt.get_resource(h + '.png')) for h in all_heroes}
    role_icons = {r: QIcon(appctxt.get_resource(r + '.png')) for r in all_roles}
    arrow_icon = QIcon(appctxt.get_resource("right-arrow.png"))

    # pages
    tab_widget = QTabWidget()
    tab_widget.addTab(RewardsPage(hero_icons, role_icons, arrow_icon, team_tags), "Rewards")
    tab_widget.addTab(DraftPage(hero_icons, draft_format, team_tags), "Draft")

    window = QMainWindow()
    window.setCentralWidget(tab_widget)
    window.resize(1600, 800)
    window.show()

    exit_code = appctxt.app.exec()      # 2. Invoke appctxt.app.exec()
    sys.exit(exit_code)
