"""Choosing which ISOs already on the drive VEIM should look after.

VEIM used to take in every ISO it found, without asking. That filled the list
with rows nothing could update and, worse, filed a customised image as the
official release and offered to "update" - overwrite - it.

Now nothing is adopted unasked. Only an ISO named exactly like an official
download is even a candidate (see core/iso_identity), and each candidate gets
an answer here: adopt it, leave it alone for good, or decide another time.
"""
from typing import Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
)

from src.core.inventory import AdoptionCandidate
from src.ui.components import Row, make_button
from src.ui.distro_card import human_size

ADOPT = "adopt"
EXCLUDE = "exclude"
UNDECIDED = ""


class CandidateRow(Row):
    """One candidate, with its answer as a pair of toggles. Neither pressed
    means "ask me again"."""

    def __init__(self, candidate: AdoptionCandidate, display_name: str, parent=None):
        super().__init__(parent)
        self.candidate = candidate

        self.icon.set_distro(candidate.identity.key)
        self.title.setText(display_name)
        bits = [f"Version {candidate.identity.version}", human_size(candidate.size_bytes),
                candidate.filename]
        self.meta.setText("  ·  ".join(bits))
        self.meta.setToolTip(candidate.filename)

        if candidate.in_root:
            note = QLabel("In the drive root - adopting moves it into Managed_ISOs.")
            note.setObjectName("rowMeta")
            self.text_col.addWidget(note)

        self.btn_adopt = self._toggle("Adopt", "Track this ISO and offer updates for it.")
        self.btn_exclude = self._toggle(
            "Leave alone", "Keep it on the drive untouched, and do not ask about it again.")
        self.btn_adopt.clicked.connect(lambda on: on and self.btn_exclude.setChecked(False))
        self.btn_exclude.clicked.connect(lambda on: on and self.btn_adopt.setChecked(False))
        self.btn_exclude.setChecked(candidate.excluded)

    def _toggle(self, text: str, tip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("filterChip")
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(tip)
        self.add_action(btn)
        return btn

    def choice(self) -> str:
        if self.btn_adopt.isChecked():
            return ADOPT
        if self.btn_exclude.isChecked():
            return EXCLUDE
        return UNDECIDED

    def set_choice(self, choice: str):
        self.btn_adopt.setChecked(choice == ADOPT)
        self.btn_exclude.setChecked(choice == EXCLUDE)


class AdoptDialog(QDialog):
    def __init__(self, candidates: List[AdoptionCandidate], display_names: Dict[str, str],
                 unrecognised: int = 0, parent=None):
        super().__init__(parent)
        self.setObjectName("adoptDialog")
        self.setWindowTitle("ISOs on this drive")
        self.setModal(True)
        self.setMinimumSize(760, 420)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 20)
        root.setSpacing(6)

        title = QLabel("ISOs VEIM can keep up to date")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        subtitle = QLabel(
            "These are named exactly like official downloads from the catalog. "
            "Adopt the ones you want in your list. An ISO you have customised "
            "is better left alone: updating replaces the file. Leaving one alone "
            "never deletes it.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)
        root.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        rows_layout = QVBoxLayout(host)
        rows_layout.setContentsMargins(0, 0, 6, 0)
        rows_layout.setSpacing(8)

        self.rows: List[CandidateRow] = []
        for candidate in candidates:
            row = CandidateRow(candidate, display_names.get(candidate.filename, candidate.filename))
            self.rows.append(row)
            rows_layout.addWidget(row)
        rows_layout.addStretch()
        scroll.setWidget(host)
        root.addWidget(scroll, 1)

        if unrecognised:
            plural = "s are" if unrecognised != 1 else " is"
            others = QLabel(
                f"{unrecognised} other ISO{plural} not listed: renamed, customised, or not "
                "in the catalog, so there is nothing to update from. VEIM never changes those.")
            others.setObjectName("rowMeta")
            others.setWordWrap(True)
            root.addSpacing(8)
            root.addWidget(others)

        root.addSpacing(14)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.btn_all = make_button("Adopt All", "ghost", self._adopt_all)
        actions.addWidget(self.btn_all)
        actions.addStretch()
        self.btn_cancel = make_button("Cancel", "ghost", self.reject)
        actions.addWidget(self.btn_cancel)
        self.btn_apply = make_button("Apply", "primary", self.accept)
        self.btn_apply.setMinimumWidth(120)
        actions.addWidget(self.btn_apply)
        root.addLayout(actions)

    def _adopt_all(self):
        # Not the ones already told to be left alone: that answer was given on
        # purpose, quite possibly for a customised image.
        for row in self.rows:
            if row.choice() != EXCLUDE:
                row.set_choice(ADOPT)

    def choices(self) -> Dict[str, str]:
        """filename -> ADOPT, EXCLUDE or UNDECIDED."""
        return {row.candidate.filename: row.choice() for row in self.rows}
