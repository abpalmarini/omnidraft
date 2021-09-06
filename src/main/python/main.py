from fbs_runtime.application_context.PySide6 import ApplicationContext
from PySide6.QtWidgets import QMainWindow
from PySide6.QtGui import QIcon

import sys

from rewards_page import RewardsPage


# @Temp heroes while I focus on building main structure. Will need a
# way to select game and load in all heroes @Later.
all_heroes = [
    'Aatrox', 'Ahri', 'Akali', 'Akshan',
    'Alistar', 'Amumu', 'Anivia', 'Annie',
    'Aphelios', 'Ashe', 'AurelionSol', 'Azir',
    'Bard', 'Blitzcrank', 'Brand', 'Braum',
]
all_roles = ("Top Laner", "Jungler", "Mid Laner", "Bot Laner", "Support")
team_tags = ('FNC', 'G2')


if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext

    hero_icons = {h: QIcon(appctxt.get_resource(h + '.png')) for h in all_heroes}
    window = QMainWindow()
    window.setCentralWidget(RewardsPage(hero_icons, team_tags))
    window.resize(1600, 800)
    window.show()

    exit_code = appctxt.app.exec()      # 2. Invoke appctxt.app.exec()
    sys.exit(exit_code)
