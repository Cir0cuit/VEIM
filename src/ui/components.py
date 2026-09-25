"""Shared presentational widgets.

Everything here draws itself from the active theme's tokens and carries an
objectName the global stylesheet targets, so no view needs its own CSS.
"""
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QComboBox, QListView, QHBoxLayout,
    QVBoxLayout, QMessageBox, QProxyStyle, QSizePolicy, QStyle, QLayout, QProgressBar,
    QToolTip
)
from PySide6.QtCore import Qt, QSize, QRect, QRectF, QPoint, QPointF
from PySide6.QtGui import (
    QBrush, QColor, QCursor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
)

from src.core import browser
from src.core.downloader import DownloadTask
from src.ui.theme import theme_manager


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


def show_progress(bar: QProgressBar, meta: QLabel, task: DownloadTask,
                  lead: str = "Downloading"):
    """Put a transfer on a row: fill the bar and state the numbers in `meta`."""
    done = task.downloaded_bytes / (1024 ** 2)
    if task.total_bytes > 0:
        pct = int(task.downloaded_bytes / task.total_bytes * 100)
        bar.setRange(0, 100)
        bar.setValue(pct)
        size = f"{done:.0f} / {task.total_bytes / (1024 ** 2):.0f} MB"
        bits = [f"{lead} {pct}%".strip(), f"{task.speed_mbps:.1f} MB/s", size,
                f"{fmt_eta(task.eta_seconds)} left"]
    else:
        # Unknown total: an indeterminate bar rather than a fake 0%.
        bar.setRange(0, 0)
        size = f"{done:.0f} MB"
        bits = [lead, f"{task.speed_mbps:.1f} MB/s", size]
    if task.note:
        # Between attempts: what is being waited for, not a speed of 0.
        bits = [task.note, size]
    meta.setText("  ·  ".join(b for b in bits if b))


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

        colors = theme_manager.current
        container = self.view().window()
        # Target the container by name: a bare "QFrame" also matches the
        # QListView inside it, which then draws its own border inside the
        # container's - the double box.
        container.setObjectName("comboPopup")
        # Styled before Qt sizes the popup, so the border is part of the height
        # it computes. Styled after, the border took 2px from a list sized to
        # fit its rows exactly, and the list scrolled by a whole row to an empty
        # line (Linux, where the container has no frame of its own).
        container.setStyleSheet(
            "QFrame#comboPopup {"
            f"  background-color: {colors.bg_card};"
            f"  border: 1px solid {colors.border_focus};"
            "}"
        )
        super().showPopup()


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

    It replaced a helper that elided once, at a width given up front, measuring
    with the font the label carried at call time - which is the application
    default, not the larger one the stylesheet applies on polish. The result
    was a drive path that overflowed its container and was clipped mid-glyph.
    Re-eliding on resize uses the real width and the real font instead of
    guessing both.
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
        restyle(self, "iconChipPlate" if needs_plate else "iconChip")

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

    TONES = {"neutral": "statusPill", "ok": "okPill", "warn": "warnPill",
             "accent": "accentPill"}

    def __init__(self, text: str = "", tone: str = "neutral", parent=None):
        super().__init__(text, parent)
        self.set_tone(tone)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

    def set_tone(self, tone: str):
        restyle(self, self.TONES.get(tone, "statusPill"))


class CapacityBar(QWidget):
    """Horizontal used/free indicator for a drive.

    A second, muted segment after the used one is space that downloads in
    flight are going to take: not used yet, not free either.
    """

    def __init__(self, height: int = 6, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._track = QFrame(self)
        self._track.setObjectName("capacityTrack")
        # Drawn first, so the used fill sits on top of it: the two together
        # read as one bar with a paler tail.
        self._reserved = QFrame(self._track)
        self._reserved.setObjectName("capacityReserved")
        self._reserved.hide()
        self._fill = QFrame(self._track)
        self._fill.setObjectName("capacityFill")
        self._ratio = 0.0
        self._reserved_ratio = 0.0

    def set_used_fraction(self, fraction: float, reserved: float = 0.0):
        self._ratio = max(0.0, min(1.0, fraction))
        self._reserved_ratio = max(0.0, min(1.0 - self._ratio, reserved))
        # Near-full drives read as a warning rather than "more blue is better".
        committed = self._ratio + self._reserved_ratio
        restyle(self._fill, "capacityFillWarn" if committed > 0.9 else "capacityFill")
        self._reserved.setVisible(self._reserved_ratio > 0)
        self._relayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self):
        width, height = self.width(), self.height()
        self._track.setGeometry(0, 0, width, height)
        self._fill.setGeometry(0, 0, int(width * self._ratio), height)
        self._reserved.setGeometry(
            0, 0, int(width * (self._ratio + self._reserved_ratio)), height)


def _gb_text(gb: float) -> str:
    return f"{gb:.1f} GB" if gb >= 1 else f"{gb * 1024:.0f} MB"


def _hue_distance(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


class DriveMap(QWidget):
    """The drive to scale, left to right: each managed ISO as a block the size
    of its file, everything else on the drive, the downloads in flight (what
    they have written, then what they still need), then free space.

    Each ISO's block takes the hue of its logo. Pointing at a block names it,
    and pointing at a row outlines that row's block.
    """

    BAR = 24
    GAP = 2
    LEGEND_GAP = 10
    SWATCH = 10
    WRITTEN = "Downloaded so far"
    RESERVED = "Reserved for downloads"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("driveMap")
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._isos: list = []           # (ident, distro key, name, bytes), in row order
        self._total = self._free = self._reserved = self._written = 0.0
        self._blocks: list = []         # (QRectF, tooltip) as last painted
        self._hovered = -1              # block under the pointer
        self._marked = None             # ident of the ISO whose row is under it
        self.hide()

    # -- data -------------------------------------------------------------

    def set_isos(self, isos):
        """(ident, distro key, name, size in bytes) for each managed ISO."""
        self._isos = list(isos)
        self.update()

    def set_drive(self, total_gb: float, free_gb: float, reserved_gb: float = 0.0,
                  written_gb: float = 0.0):
        """`reserved_gb` is what downloads in flight still have to write, and
        `written_gb` what they already have: used space, but no ISO yet."""
        self._total, self._free = total_gb, free_gb
        self._reserved = max(0.0, min(reserved_gb, free_gb))
        self._written = max(0.0, written_gb)
        self.setVisible(total_gb > 0)
        self.update()

    def mark(self, ident):
        """Outline one ISO's block, or none."""
        self._marked = ident
        self.update()

    def parts(self) -> list:
        """(name, GB, colour) of each block, left to right. Free space is what
        the blocks leave of the bar; `colour` None is drawn hatched."""
        from src.core.icons import icon_manager

        c = theme_manager.current
        base, alternate = (0.56, 0.70) if c.mode == "Dark" else (0.46, 0.34)
        parts = []
        previous, lightness = None, base
        for _, key, name, size in self._isos:
            hue = icon_manager.brand_hue(key)
            if hue is None:
                # Brighter than the other files' grey, so it is not read as them.
                colour = QColor(c.text_secondary)
            else:
                # Two blues side by side would read as one block.
                near = previous is not None and _hue_distance(hue, previous) < 25
                lightness = (alternate if lightness == base else base) if near else base
                colour = QColor.fromHslF(hue / 360, 0.55, lightness)
            previous = hue
            parts.append((name, size / (1024 ** 3), colour))

        isos_gb = sum(gb for _, gb, _ in parts)
        other = max(0.0, self._total - self._free - isos_gb - self._written)
        if other > 0:
            neutral = QColor(c.text_muted)
            neutral.setAlphaF(0.4)
            parts.append(("Other files", other, neutral))
        if self._written > 0:
            written = QColor(c.accent)
            written.setAlphaF(0.6)
            parts.append((self.WRITTEN, self._written, written))
        if self._reserved > 0:
            parts.append((self.RESERVED, self._reserved, None))
        return parts

    # -- geometry ---------------------------------------------------------

    def sizeHint(self) -> QSize:
        return QSize(400, self.BAR + self.LEGEND_GAP + self.fontMetrics().height() + 2)

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.sizeHint().height())

    # -- painting ---------------------------------------------------------

    def paintEvent(self, event):
        c = theme_manager.current
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width = self.width()
        bar = QRectF(0.5, 0.5, width - 1, self.BAR - 1)

        # An empty well is the whole drive; whatever no block covers is free.
        outline = QPainterPath()
        outline.addRoundedRect(bar, 6, 6)
        p.fillPath(outline, QColor(c.bg_input))
        p.setClipPath(outline)

        parts = self.parts()
        marked = next((i for i, iso in enumerate(self._isos) if iso[0] == self._marked), -1)
        self._blocks = []
        scale = width / self._total if self._total > 0 else 0
        x = 0.0
        for index, (name, gb, colour) in enumerate(parts):
            # Never narrower than a sliver: a small ISO still has to be seen.
            w = max(3.0, gb * scale)
            rect = QRectF(x, 0, max(1.0, w - self.GAP), self.BAR)
            if colour is None:
                self._paint_reserved(p, rect, c)
            else:
                p.fillRect(rect, colour)
            if index in (self._hovered, marked):
                p.setPen(QPen(QColor(c.text_primary), 2))
                p.drawRect(rect.adjusted(1, 1, -1, -1))
            self._blocks.append((rect, f"{name}, {_gb_text(gb)}"))
            x += w

        p.setClipping(False)
        p.setPen(QPen(QColor(c.border), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(outline)

        self._paint_legend(p, c, parts)
        p.end()

    @staticmethod
    def _paint_reserved(p: QPainter, rect: QRectF, c):
        """Hatched: not written yet, but no longer free either."""
        tint = QColor(c.accent)
        tint.setAlphaF(0.25)
        p.fillRect(rect, tint)
        p.fillRect(rect, QBrush(QColor(c.accent_fg), Qt.BrushStyle.BDiagPattern))

    def _paint_legend(self, p: QPainter, c, parts):
        metrics = self.fontMetrics()
        baseline = self.BAR + self.LEGEND_GAP + metrics.ascent()
        mid = self.BAR + self.LEGEND_GAP + metrics.height() / 2

        count = len(self._isos)
        items = []
        if count:
            isos_gb = sum(gb for _, gb, _ in parts[:count])
            plural = "ISO" if count == 1 else "ISOs"
            items.append(([colour for _, _, colour in parts[:min(count, 3)]],
                          f"{_gb_text(isos_gb)} in {count} {plural}"))
        for name, gb, colour in parts[count:]:
            if name == "Other files":
                items.append(([colour], f"Other files {_gb_text(gb)}"))
        in_flight = self._written + self._reserved
        if in_flight > 0:
            items.append(([None], f"Downloads {_gb_text(in_flight)}"))

        # How much room is left is the question the map is here to answer.
        free_text = f"{_gb_text(self._free - self._reserved)} free"
        of_text = f" of {self._total:.0f} GB"
        bold = QFont(self.font())
        bold.setWeight(QFont.Weight.DemiBold)
        of_x = self.width() - metrics.horizontalAdvance(of_text)
        free_x = of_x - QFontMetrics(bold).horizontalAdvance(free_text)
        p.setPen(QColor(c.text_secondary))
        p.drawText(QPointF(of_x, baseline), of_text)
        p.setFont(bold)
        p.setPen(QColor(c.text_primary))
        p.drawText(QPointF(free_x, baseline), free_text)
        p.setFont(self.font())

        p.setPen(QColor(c.text_secondary))
        x = 0.0
        for colours, label in items:
            span = self.SWATCH + 6 + metrics.horizontalAdvance(label)
            if x + span > free_x - 16:
                break           # a narrow window keeps the free figure over these
            self._paint_swatch(p, QRectF(x, mid - self.SWATCH / 2, self.SWATCH, self.SWATCH),
                               colours, c)
            p.drawText(QPointF(x + self.SWATCH + 6, baseline), label)
            x += span + 18

    def _paint_swatch(self, p: QPainter, rect: QRectF, colours, c):
        path = QPainterPath()
        path.addRoundedRect(rect, 2, 2)
        p.save()
        p.setClipPath(path)
        if colours == [None]:
            self._paint_reserved(p, rect, c)
        else:
            # A stripe per colour: the ISOs are several hues, not one.
            step = rect.width() / len(colours)
            for i, colour in enumerate(colours):
                p.fillRect(QRectF(rect.x() + i * step, rect.y(), step + 0.5, rect.height()),
                           colour)
        p.restore()

    # -- hover ------------------------------------------------------------

    def mouseMoveEvent(self, event):
        pos = event.position()
        hovered = next((i for i, (rect, _) in enumerate(self._blocks)
                        if rect.adjusted(0, 0, self.GAP, 0).contains(pos)), -1)
        if hovered != self._hovered:
            self._hovered = hovered
            self.update()
        if hovered >= 0:
            QToolTip.showText(event.globalPosition().toPoint(), self._blocks[hovered][1], self)
        else:
            QToolTip.hideText()

    def leaveEvent(self, event):
        self._hovered = -1
        self.update()
        super().leaveEvent(event)


BUTTON_OBJECT_NAMES = {
    "primary": "primaryBtn", "tonal": "tonalBtn", "ghost": "ghostBtn",
    "quiet": "quietBtn", "danger": "quietDanger", "subtle-danger": "subtleDanger",
}


def make_button(text: str, kind: str = "ghost", on_click: Optional[Callable] = None,
                parent=None) -> QPushButton:
    """Create a themed button.

    kind: "primary" | "tonal" | "ghost" | "quiet" | "danger" | "subtle-danger"
    """
    btn = QPushButton(text, parent)
    btn.setObjectName(BUTTON_OBJECT_NAMES.get(kind, "ghostBtn"))
    btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    btn.setMinimumHeight(34)
    # Reachable with Tab, but a click leaves no focus ring behind.
    btn.setFocusPolicy(Qt.FocusPolicy.TabFocus)
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


def restyle(widget: QWidget, name: str):
    """Give a widget that already exists a new objectName, and its styling.

    Re-polishing is the part that matters: a widget the stylesheet has already
    seen keeps its old appearance until the style is told to look at the new
    objectName.
    """
    if widget.objectName() == name:
        return
    widget.setObjectName(name)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_button_kind(btn: QPushButton, kind: str):
    """Restyle a button that already exists."""
    restyle(btn, BUTTON_OBJECT_NAMES.get(kind, "ghostBtn"))


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
