from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QFrame, QSizePolicy


class HeroBox(QLabel):
    """Clickable box that can hold a hero name and display its icon."""

    clicked = Signal(str)

    def __init__(self, hero_icons, size):
        super().__init__()

        self.name = ""
        self.hero_icons = hero_icons
        self.selected = None  # can't set directly because frame won't get set up
        self.set_selected(False)

        self.size = size
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setLineWidth(2)

    def set_hero(self, name):
        self.name = name
        self.setPixmap(self.hero_icons[name].pixmap(self.size))

    def set_selected(self, selected):
        if selected == self.selected:
            return
        self.selected = selected
        if selected:
            self.setFrameStyle(QFrame.Box | QFrame.Raised)
        else:
            self.setFrameStyle(QFrame.Panel | QFrame.Raised)

    def sizeHint(self):
        return self.size

    def clear(self):
        self.name = ""
        QLabel.clear(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self.name)

    # Handles all situations of switching the contents of the hero box
    # with a different hero box for cases where it is clicked and the
    # other hero box is already selected.
    def switch_with_selected(self, selected_box):
        assert selected_box.selected and selected_box != self
        if not selected_box.name and not self.name:
            selected_box.set_selected(False)
            self.set_selected(True)
        else:
            selected_box.set_selected(False)
            if selected_box.name and not self.name:
                self.set_hero(selected_box.name)
                selected_box.clear()
            elif not selected_box.name and self.name:
                selected_box.set_hero(self.name)
                self.clear()
            else:
                selected_box_name = selected_box.name
                selected_box.set_hero(self.name)
                self.set_hero(selected_box_name)

    # Sets a hero item from a search model to the hero box, disabling
    # the item from search. If the hero box already contains a hero then
    # the corresponding item is re-enabled for search.
    def set_hero_from_search_item(self, search_item):
        if self.name:
            search_model = search_item.model()
            prev_item = search_model.findItems(self.name)[0]
            prev_item.setEnabled(True)
        search_item.setEnabled(False)
        self.set_selected(False)
        self.set_hero(search_item.text())
