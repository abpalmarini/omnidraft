from fbs_runtime.application_context.PySide6 import ApplicationContext
from PySide6.QtWidgets import QMainWindow, QTableView, QWidget, QVBoxLayout, QLineEdit, QPushButton, QAbstractItemView, QGridLayout, QSplitter
from PySide6.QtCore import Slot, QItemSelectionModel, Qt
from PySide6.QtGui import QIcon

import sys
import random

from reward_models import *
from reward_dialogs import RoleRewardDialog


# @Temp heroes while I focus on building main structure. Will need a
# way to select game and load in all heroes @Later.
all_heroes = [
    'Aatrox', 'Ahri', 'Akali', 'Akshan',
    'Alistar', 'Amumu', 'Anivia', 'Annie',
    'Aphelios', 'Ashe', 'AurelionSol', 'Azir',
    'Bard', 'Blitzcrank', 'Brand', 'Braum',
]
all_roles = ('Top', 'Jungle', 'Mid', 'Support', 'Bot')
team_tags = ('FNC', 'G2')


class TestWindow(QMainWindow):

    def __init__(self, appctxt):
        super().__init__()
        
        # set up initial hero icons once for all to use
        self.hero_icons = {h: QIcon(appctxt.get_resource(h + '.png')) for h in all_heroes}

        # role rewards 
        self.role_model = RoleRewardsModel(all_heroes, team_tags)
        self.role_view = QTableView()
        self.role_view.setModel(self.role_model)
        self.role_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.role_view.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.role_dialog = RoleRewardDialog(self.role_model, self.hero_icons, team_tags, self)

        # synergy rewards
        self.synergy_model = SynergyRewardsModel(team_tags)
        self.synergy_view = QTableView()
        self.synergy_view.setModel(self.synergy_model)
        self.synergy_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.synergy_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        # counter rewards
        self.counter_model = CounterRewardsModel(team_tags)
        self.counter_view = QTableView()
        self.counter_view.setModel(self.counter_model)
        self.counter_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.counter_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QGridLayout(self.central_widget)
        self.lists = QSplitter()
        self.lists.addWidget(self.role_view)
        self.lists.addWidget(self.synergy_view)
        self.lists.addWidget(self.counter_view)
        self.main_layout.addWidget(self.lists, 0, 0, 1, 3)

        # test sorting
        # @Important to do initial sort first so that a current sort gets set
        self.role_view.sortByColumn(2, Qt.DescendingOrder)
        self.role_view.setSortingEnabled(True)
        self.synergy_view.sortByColumn(5, Qt.DescendingOrder)
        self.synergy_view.setSortingEnabled(True)
        self.counter_view.sortByColumn(10, Qt.DescendingOrder)
        self.counter_view.setSortingEnabled(True)

        # test filtering
        self.filter_bar = QLineEdit()
        self.main_layout.addWidget(self.filter_bar, 1, 0, 1, 3)
        self.filter_bar.textChanged.connect(self.role_model.filter_rewards)
        self.filter_bar.textChanged.connect(self.synergy_model.filter_rewards)
        self.filter_bar.textChanged.connect(self.counter_model.filter_rewards)

        # test adding
        self.add_role_button = QPushButton("add random role reward")
        self.main_layout.addWidget(self.add_role_button, 2, 0)
        self.add_role_button.clicked.connect(self.add_role_reward)
        self.add_synergy_button = QPushButton("add random synergy reward")
        self.main_layout.addWidget(self.add_synergy_button, 2, 1)
        self.add_synergy_button.clicked.connect(self.add_synergy_reward)
        self.add_counter_button = QPushButton("add random counter reward")
        self.main_layout.addWidget(self.add_counter_button, 2, 2)
        self.add_counter_button.clicked.connect(self.add_counter_reward)

        # test deleting
        self.delete_button = QPushButton("delete selected rewards")
        self.main_layout.addWidget(self.delete_button, 3, 0, 1, 3)
        self.delete_button.clicked.connect(self.delete)

        # set team builder
        self.team_1 = []
        self.team_2 = []
        self.set_team_button = QPushButton("set team builder")
        self.main_layout.addWidget(self.set_team_button, 4, 0, 1, 1)
        self.set_team_button.clicked.connect(self.set_teams)
        self.clear_team_button = QPushButton("clear team builder")
        self.main_layout.addWidget(self.clear_team_button, 4, 1, 1, 1)
        self.clear_team_button.clicked.connect(self.clear_teams)

    @Slot()
    def add_role_reward(self):
        self.role_dialog.open_add()

    @Slot()
    def add_synergy_reward(self):
        num_heroes = random.randint(2, 5)
        names = random.sample(all_heroes, num_heroes)
        # just give each one a single role to avoid clashes for now
        roles = random.sample(all_roles, num_heroes)
        heroes = {name: [role] for name, role in zip(names, roles)}
        synergy_reward = SynergyReward(
            heroes,
            random.randrange(0, 1000) / 100,
            random.randrange(0, 1000) / 100,
        )
        self.synergy_model.add_reward(synergy_reward)

    @Slot()
    def add_counter_reward(self):
        num_heroes = random.randint(1, 5)
        num_foes = random.randint(1, 5)
        names = random.sample(all_heroes, num_heroes + num_foes)
        team_names = names[:num_heroes]
        team_roles = random.sample(all_roles, num_heroes)
        heroes = {name: [role] for name, role in zip(team_names, team_roles)}
        counter_reward = CounterReward(
            heroes,
            names[num_heroes:],
            random.randrange(0, 1000) / 100,
            random.randrange(0, 1000) / 100,
        )
        self.counter_model.add_reward(counter_reward)

    @Slot()
    def delete(self):
        views = (self.role_view, self.synergy_view, self.counter_view)
        models = (self.role_model, self.synergy_model, self.counter_model)
        for view, model in zip(views, models):
            selection_model = view.selectionModel()
            indexes = selection_model.selectedRows()
            if indexes:
                model.delete_rewards(indexes)
            view.clearSelection()

    @Slot()
    def set_teams(self):
        # add relevant rewards
        rr_1 = RoleReward('Ahri', 'Top', 2.4, 3.9)
        rr_2 = RoleReward('Ashe', 'Bot', 1.4, 8.9)
        self.role_model.add_reward(rr_1)
        self.role_model.add_reward(rr_2)

        sr = SynergyReward({'Ahri': ['Top', 'Jungle'], 'Bard': ['Mid']}, 4.56, 2.34)
        self.synergy_model.add_reward(sr)

        cr = CounterReward({'Bard': ['Mid']}, ['Ashe'], 9.56, 2.12)
        self.counter_model.add_reward(cr)

        self.team_1 = [('Ahri', 'Top'), ('Bard', 'Mid')]
        self.team_2 = [('Ashe', 'Bot')]

        # let models know teams have changed
        models = (self.role_model, self.synergy_model, self.counter_model)
        for model in models:
            model.update_reward_statuses(self.team_1, self.team_2)

    @Slot()
    def clear_teams(self):
        self.team_1 = []
        self.team_2 = []
        models = (self.role_model, self.synergy_model, self.counter_model)
        for model in models:
            model.update_reward_statuses(self.team_1, self.team_2)


if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext
    window = TestWindow(appctxt)
    window.resize(1600, 800)
    window.show()
    exit_code = appctxt.app.exec()      # 2. Invoke appctxt.app.exec()
    sys.exit(exit_code)
