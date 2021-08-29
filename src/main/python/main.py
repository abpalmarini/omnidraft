from fbs_runtime.application_context.PySide6 import ApplicationContext
from PySide6.QtWidgets import QMainWindow, QTableView, QWidget, QVBoxLayout, QLineEdit, QPushButton, QAbstractItemView, QGridLayout, QSplitter
from PySide6.QtCore import Slot, QItemSelectionModel, Qt

import sys
import random

from rewards import *


# @Temp heroes while I focus on building main structure. Will need a
# way to select game and load in all heroes @Later.
all_heroes = [
    'Aatrox', 'Ahri', 'Akali', 'Akshan',
    'Alistar', 'Amumu', 'Anivia', 'Annie',
    'Aphelios', 'Ashe', 'AurelionSol', 'Azir',
    'Bard', 'Blitzcrank', 'Brand', 'Braum',
]
all_roles = ('Top', 'Jungle', 'Mid', 'Support', 'Bot')


class TestWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        # role rewards 
        self.role_model = RoleRewardsModel(all_heroes, 'FNC', 'G2')
        self.role_view = QTableView()
        self.role_view.setModel(self.role_model)
        self.role_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.role_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        # synergy rewards
        self.synergy_model = SynergyRewardsModel('FNC', 'G2')
        self.synergy_view = QTableView()
        self.synergy_view.setModel(self.synergy_model)
        self.synergy_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.synergy_view.setSelectionBehavior(QAbstractItemView.SelectRows)

        # counter rewards
        self.counter_model = CounterRewardsModel('FNC', 'G2')
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

    @Slot()
    def add_role_reward(self):
        role_reward = RoleReward(
            random.choice(all_heroes),
            random.choice(all_roles),
            random.randrange(0, 1000) / 100,
            random.randrange(0, 1000) / 100,
        )
        self.role_model.add_reward(role_reward)

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

if __name__ == '__main__':
    appctxt = ApplicationContext()       # 1. Instantiate ApplicationContext
    window = TestWindow()
    window.resize(1600, 800)
    window.show()
    exit_code = appctxt.app.exec()      # 2. Invoke appctxt.app.exec()
    sys.exit(exit_code)
