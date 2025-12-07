import sys
import csv
import webbrowser
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QVBoxLayout,
    QHBoxLayout, QPushButton, QLineEdit, QFileDialog,
    QScrollArea, QFrame, QDialog, QFormLayout, QSpinBox,
    QGridLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt


SCORE_TYPES = ["Enjoyment", "Gameplay", "Music", "Narrative", "MetaCritic"]


def safe_float(x):
    try:
        return float(x)
    except:
        return None


def score_to_color(score):
    """Return a blended green→red color for score 0–10."""
    if score is None:
        return "#444"
    pct = max(0, min(1, score / 10))
    r = int((1 - pct) * 200)
    g = int(pct * 200)
    return f"rgb({r},{g},80)"


class EditDialog(QDialog):
    def __init__(self, game):
        super().__init__()
        self.setWindowTitle("Edit Game")
        self.game = game
        layout = QFormLayout()

        self.title_edit = QLineEdit(game["Game"])
        self.year_edit = QLineEdit(game["Release Year"])
        self.cover_edit = QLineEdit(game["Cover Path"])

        layout.addRow("Game Title:", self.title_edit)
        layout.addRow("Release Year:", self.year_edit)
        layout.addRow("Cover Path:", self.cover_edit)

        self.score_edits = {}
        for t in SCORE_TYPES:
            box = QSpinBox()
            box.setRange(0, 10)
            box.setValue(int(float(game[f"{t} Score"])))
            layout.addRow(f"{t} Score:", box)
            self.score_edits[t] = box

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        layout.addRow(save_btn)
        self.setLayout(layout)

    def get_data(self):
        result = {
            "Game": self.title_edit.text(),
            "Release Year": self.year_edit.text(),
            "Cover Path": self.cover_edit.text()
        }
        for t in SCORE_TYPES:
            result[f"{t} Score"] = str(self.score_edits[t].value())
        return result


class GameCard(QFrame):
    def __init__(self, game_data, parent):
        super().__init__()
        self.game_data = game_data
        self.parent = parent

        self.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.setStyleSheet("background-color: #222; border-radius: 12px; padding: 12px;")
        self.setMinimumHeight(200)

        main = QVBoxLayout()
        self.setLayout(main)

        # Top Row (Cover + Title)
        top = QHBoxLayout()
        main.addLayout(top)

        # Cover Art
        cover = QLabel()
        cover.setFixedSize(100, 140)
        if game_data["Cover Path"]:
            pix = QPixmap(game_data["Cover Path"])
            if not pix.isNull():
                cover.setPixmap(pix.scaled(100, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        top.addWidget(cover)

        # Title
        title = QLabel(f"{game_data['Game']} ({game_data['Release Year']})")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: white;")
        title.setWordWrap(True)
        top.addWidget(title)

        # Score Grid (Labels above bubbles)
        grid = QGridLayout()
        main.addLayout(grid)

        self.score_labels = {}

        for c, s in enumerate(SCORE_TYPES):
            title_lbl = QLabel(s)
            title_lbl.setStyleSheet("color: white; font-size: 12px; font-weight: bold;")
            title_lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(title_lbl, 0, c)

            val = safe_float(game_data[f"{s} Score"])
            bubble = QLabel(str(val) if val is not None else "N/A")
            bubble.setAlignment(Qt.AlignCenter)
            bubble.setFixedSize(55, 55)
            bubble.setStyleSheet(
                f"""
                background-color: {score_to_color(val)};
                border-radius: 10px;
                color: white;
                font-size: 18px;
                font-weight: bold;
                """
            )
            grid.addWidget(bubble, 1, c)
            self.score_labels[s] = bubble

        # Bottom Buttons
        bottom = QHBoxLayout()
        main.addLayout(bottom)

        music_btn = QPushButton("🎵")
        music_btn.setFixedSize(35, 35)
        music_btn.clicked.connect(self.open_youtube)
        bottom.addWidget(music_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setFixedSize(70, 35)
        edit_btn.clicked.connect(self.edit_game)
        bottom.addWidget(edit_btn)

        del_btn = QPushButton("Delete")
        del_btn.setFixedSize(70, 35)
        del_btn.clicked.connect(self.delete_game)
        bottom.addWidget(del_btn)

        bottom.addStretch()

        self.setMouseTracking(True)

    def open_youtube(self):
        webbrowser.open(f"https://www.youtube.com/results?search_query={self.game_data['Game']} OST")

    def edit_game(self):
        dlg = EditDialog(self.game_data)
        if dlg.exec_():
            updated = dlg.get_data()
            for k, v in updated.items():
                self.game_data[k] = v
            self.parent.refresh()

    def delete_game(self):
        self.parent.games.remove(self.game_data)
        self.parent.refresh()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Scoreboard")
        self.setStyleSheet("background-color: #111; color: white;")

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Search bar
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games...")
        self.search.textChanged.connect(self.refresh)
        layout.addWidget(self.search)

        # Load CSV Button
        load_btn = QPushButton("Load CSV")
        load_btn.clicked.connect(self.load_csv)
        layout.addWidget(load_btn)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)

        self.container = QVBoxLayout()
        w = QWidget()
        w.setLayout(self.container)
        self.scroll.setWidget(w)

        self.games = []

    def load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        self.games = []
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.games.append(row)
        self.refresh()

    def refresh(self):
        for i in reversed(range(self.container.count())):
            self.container.itemAt(i).widget().deleteLater()

        text = self.search.text().lower()

        for game in self.games:
            if text and text not in game["Game"].lower():
                continue
            card = GameCard(game, self)
            self.container.addWidget(card)

        self.container.addStretch()


app = QApplication(sys.argv)
w = MainWindow()
w.resize(900, 800)
w.show()
sys.exit(app.exec_())
