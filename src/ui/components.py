"""Shared presentational widgets.

Everything here draws itself from the active theme's tokens and carries an
objectName the global stylesheet targets, so no view needs its own CSS.
"""
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QComboBox, QListView, QHBoxLayout,
    QVBoxLayout, QMessageBox, QProxyStyle, QSizePolicy, QStyle, QLayout
)
from PySide6.QtCore import Qt, QSize, QRect, QPoint
from PySide6.QtGui import QCursor, QPixmap, QFontMetrics

from src.core import browser
from src.ui.theme import theme_manager


def elide(label: QLabel, text: str, width: int):
    """Set text on a label, truncating with an ellipsis to fit `width`.

    The old toolbar painted the full drive path into a fixed-width label, so a
    long path ran underneath the buttons and got visually chopped mid-word.
    """
    metrics = QFontMetrics(label.font())
    label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideMiddle, max(40, width)))
    label.setToolTip(text)


def fmt_eta(seconds: int) -> str:
    """Format a remaining time at a precision the estimate actually supports.

    A multi-gigabyte download is not knowable to the second, so past ten
    minutes the seconds are dropped rather than churning on every refresh.
    """
    if seconds <= 0:
        return "--"
    if seconds < 60:
        # Round to 5s so the last minute counts down steadily.
        return f"{max(5, round(seconds / 5) * 5)}s"
    mins, secs = divmod(seconds, 60)
    if mins < 10:
        return f"{mins}m {secs:02d}s"
    if mins < 60:
        return f"{mins}m"
    hours, mins = divmod(mins, 60)
    return f"{hours}h {mins:02d}m"


class _PlainListPopup(QProxyStyle):
    """Style that refuses a menu-style combo popup.

    Qt's combo container always builds a scroller widget above and below the
    list, which scroll the list on hover. Normally they stay hidden, but they
    are what appears when the popup gets capped, and hover-scrolling is the
    wrong interaction for a list of at most seven flavors.

    Turning SH_ComboBox_Popup off makes the container omit them entirely rather
    than merely hide them, so they cannot appear whatever the geometry. When
    the popup will not fit below the combo, Qt repositions it instead -
    verified by opening a seven-item list with 120px of screen below it, where
    every entry stayed reachable with no scrollers and no scrollbar.
    """

    def styleHint(self, hint, option=None, widget=None, returnData=None):
        if hint == QStyle.StyleHint.SH_ComboBox_Popup:
            return 0
        return super().styleHint(hint, option, widget, returnData)


class FlavorCombo(QComboBox):
    """Combo box whose dropdown shows every option at once, in a single box.

    Two things had to be undone. Qt wraps the list in a container frame that
    paints its own opaque background, so putting the border and rounded corners
    on the list left the container showing through as a dark square halo; the
    container cannot be made transparent (WA_TranslucentBackground is accepted
    and reported as set, but it still paints opaquely - checked by opening a
    popup over a magenta backdrop). So the container draws the frame and the
    list draws only its items, which is also what stops the two nesting into a
    visible box-in-a-box.

    Setting an explicit QListView also matters for looks rather than only for
    behaviour: the stylesheet's `QComboBox QAbstractItemView::item` rules do
    not reach the view Qt builds by default, so rows came out at the unstyled
    25px instead of the 44px the padding asks for. See also _PlainListPopup.

    This is a plain QComboBox underneath, and deliberately so - but it is drawn
    by the stylesheet, not by the platform. A widget under a stylesheet is
    painted by QStyleSheetStyle, so a natively drawn dropdown and an
    eight-theme palette are mutually exclusive for the same widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # QProxyStyle(style) takes ownership of what it is given, and deleting
        # the shared application style on teardown kills the process. With no
        # argument it proxies that style without owning it. setStyle() does not
        # take ownership either, hence the attribute.
        self._popup_style = _PlainListPopup()
        self.setStyle(self._popup_style)

        view = QListView()
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setUniformItemSizes(True)
        self.setView(view)

    def showPopup(self):
        # Every entry is shown; a dropdown that scrolls hides options behind
        # an interaction.
        self.setMaxVisibleItems(max(1, self.count()))
        super().showPopup()

        colors = theme_manager.current
        container = self.view().window()
        # Target the container by name: a bare "QFrame" also matches the
        # QListView inside it, which then draws its own border inside the
        # container's - the double box.
        container.setObjectName("comboPopup")
        container.setStyleSheet(
            "QFrame#comboPopup {"
            f"  background-color: {colors.bg_card};"
            f"  border: 1px solid {colors.border_focus};"
            "}"
        )


class FlowLayout(QLayout):
    """Left-to-right layout that wraps onto a new line when it runs out of room.

    Qt ships no wrapping layout, so a row of category chips in a QHBoxLayout
    simply overflowed its viewport: at the app's minimum window width the chips
    needed 866px and had 632px, and the last two were cut off at the edge.
    This follows Qt's own FlowLayout example.
    """

    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 8,
                 v_spacing: int = 8):
        super().__init__(parent)
        self._items: list = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)

    # -- QLayout plumbing -------------------------------------------------

    def addItem(self, item):
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    # -- wrapping ---------------------------------------------------------

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(),
                            margins.top() + margins.bottom())

    def _arrange(self, rect: QRect, apply: bool) -> int:
        """Place items across as many lines as needed; return the total height."""
        margins = self.contentsMargins()
        left = rect.x() + margins.left()
        right = rect.right() - margins.right()
        x, y = left, rect.y() + margins.top()
        line_height = 0

        for item in self._items:
            hint = item.sizeHint()
            next_x = x + hint.width()
            if next_x > right and line_height > 0:
                # Does not fit on this line - start another.
                x = left
                y += line_height + self._v_spacing
                next_x = x + hint.width()
                line_height = 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x + self._h_spacing
            line_height = max(line_height, hint.height())

        return (y + line_height) - rect.y() + margins.bottom()


class ElidingLabel(QLabel):
    """A label that truncates to whatever width it is actually given.

    `elide()` has to be told a width up front and measures with the font the
    label carries at call time - which is the application default, not the
    larger one the stylesheet applies on polish. The result was a drive path
    that overflowed its container and was clipped mid-glyph. Re-eliding on
    resize uses the real width and the real font instead of guessing both.
    """

    def __init__(self, text: str = "", mode=Qt.TextElideMode.ElideMiddle, parent=None):
        super().__init__(parent)
        self._full = ""
        self._mode = mode
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setFullText(text)

    def setFullText(self, text: str):
        self._full = text or ""
        self.setToolTip(self._full)
        self._relayout()

    def fullText(self) -> str:
        return self._full

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        width = max(0, self.width() - 2)
        if width <= 0:
            super().setText(self._full)
            return
        super().setText(self.fontMetrics().elidedText(self._full, self._mode, width))


class IconChip(QLabel):
    """A distro logo on a rounded backdrop.

    Upstream logos are wildly inconsistent - Tails ships a baked white
    background, TUXEDO is black-on-transparent - so drawing them straight onto
    a dark card makes some invisible and others look like pasted stickers. A
    constant chip behind every icon normalises them.
    """

    # Fraction of the chip the logo occupies. The remainder reads as padding.
    FILL = 0.76

    def __init__(self, size: int = 44, parent=None):
        super().__init__(parent)
        self.setObjectName("iconChip")
        self._size = size
        self.setFixedSize(size, size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setScaledContents(False)

    def set_backdrop(self, needs_plate: bool):
        """Pick the chip surface: themed by default, a light plate if required.

        Only a logo that is almost entirely dark gets the plate - see
        IconManager.needs_light_backdrop.
        """
        self.setObjectName("iconChipPlate" if needs_plate else "iconChip")
        self.style().unpolish(self)
        self.style().polish(self)

    def set_icon(self, pixmap: Optional[QPixmap]):
        if pixmap is None or pixmap.isNull():
            self.clear()
            return

        # QPixmap.scaled() works in DEVICE pixels and carries the source's
        # devicePixelRatio onto the result, so a logical size comes out half
        # size on a 2x pixmap. Scale in device pixels, then restore the ratio.
        dpr = pixmap.devicePixelRatio() or 1.0
        inner = int(round(self._size * self.FILL * dpr))

        scaled = pixmap.scaled(
            inner, inner,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        self.setPixmap(scaled)

    def set_distro(self, key: str):
        """Load a distro's logo and choose the chip surface that suits it."""
        from src.core.icons import icon_manager
        self.set_backdrop(icon_manager.needs_light_backdrop(key))
        self.set_icon(icon_manager.get_pixmap(key, self._size))


class Pill(QLabel):
    """Small status badge. `tone` picks the stylesheet variant."""

    TONES = {"neutral": "statusPill", "ok": "okPill", "warn": "warnPill"}

    def __init__(self, text: str = "", tone: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.set_tone(tone)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_tone(self, tone: str):
        self.setObjectName(self.TONES.get(tone, "statusPill"))
        # Re-polish so the new objectName takes effect on an existing widget.
        self.style().unpolish(self)
        self.style().polish(self)


class CapacityBar(QWidget):
    """Horizontal used/free indicator for a drive."""

    def __init__(self, height: int = 6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._track = QFrame(self)
        self._track.setObjectName("capacityTrack")
        self._fill = QFrame(self._track)
        self._fill.setObjectName("capacityFill")
        self._ratio = 0.0

    def set_used_fraction(self, fraction: float):
        self._ratio = max(0.0, min(1.0, fraction))
        # Near-full drives read as a warning rather than "more blue is better".
        self._fill.setObjectName("capacityFillWarn" if self._ratio > 0.9 else "capacityFill")
        self._fill.style().unpolish(self._fill)
        self._fill.style().polish(self._fill)
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        self._track.setGeometry(0, 0, self.width(), self.height())
        self._fill.setGeometry(0, 0, int(self.width() * self._ratio), self.height())


BUTTON_OBJECT_NAMES = {
    "primary": "primaryBtn", "ghost": "ghostBtn", "danger": "quietDanger",
}


def make_button(text: str, kind: str = "ghost", on_click: Optional[Callable] = None,
                parent=None) -> QPushButton:
    """Create a themed button.

    kind: "primary" | "ghost" | "danger"
    """
    btn = QPushButton(text, parent)
    btn.setObjectName(BUTTON_OBJECT_NAMES.get(kind, "ghostBtn"))
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setMinimumHeight(34)
    if on_click:
        btn.clicked.connect(on_click)
    return btn


def open_link(url: str, parent=None) -> bool:
    """Open a URL in the user's browser, and say where to go when that fails.

    Every caller is a button whose whole purpose is that link, so a click that
    quietly does nothing is the one outcome worth ruling out: if no browser can
    be started, the address goes on screen where it can be read and copied.
    """
    if browser.open_url(url):
        return True

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Open this page")
    box.setText("VEIM could not start a browser on this system.")
    box.setInformativeText(url)
    box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    box.exec()
    return False


def set_button_kind(btn: QPushButton, kind: str):
    """Restyle a button that already exists.

    Re-polishing is the part that matters: a widget the stylesheet has already
    seen keeps its old appearance until the style is told to look at the new
    objectName.
    """
    name = BUTTON_OBJECT_NAMES.get(kind, "ghostBtn")
    if btn.objectName() == name:
        return
    btn.setObjectName(name)
    btn.style().unpolish(btn)
    btn.style().polish(btn)


class EmptyState(QFrame):
    """Centred 'nothing here yet' panel with a single call to action."""

    def __init__(self, title: str, body: str, action_text: str = "",
                 on_action: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("emptyState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 44, 40, 44)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel(title)
        lbl_title.setObjectName("emptyTitle")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl_title)

        lbl_body = QLabel(body)
        lbl_body.setObjectName("emptyBody")
        lbl_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_body.setWordWrap(True)
        layout.addWidget(lbl_body)

        if action_text:
            layout.addSpacing(8)
            btn = make_button(action_text, "primary", on_action)
            btn.setMinimumWidth(230)
            holder = QHBoxLayout()
            holder.addStretch()
            holder.addWidget(btn)
            holder.addStretch()
            layout.addLayout(holder)


class Row(QFrame):
    """Base horizontal list row: icon chip, text block, trailing actions.

    Rows are ~72px instead of the previous ~280px cards, so a full catalog is
    scannable instead of showing four entries per screen.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("row")

        self.layout_main = QHBoxLayout(self)
        self.layout_main.setContentsMargins(14, 12, 14, 12)
        self.layout_main.setSpacing(14)

        self.icon = IconChip(44)
        self.layout_main.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignVCenter)

        self.text_col = QVBoxLayout()
        self.text_col.setSpacing(3)
        self.text_col.setContentsMargins(0, 0, 0, 0)

        self.title = QLabel()
        self.title.setObjectName("rowTitle")
        self.text_col.addWidget(self.title)

        self.meta = QLabel()
        self.meta.setObjectName("rowMeta")
        self.text_col.addWidget(self.meta)

        self.layout_main.addLayout(self.text_col, 1)

        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        self.layout_main.addLayout(self.actions, 0)

    def add_action(self, widget: QWidget):
        self.actions.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)
