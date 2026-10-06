"""Row for a bootable file on the drive that VEIM does not manage.

These used to be one sentence under the list - "3 other ISOs are not managed"
- with the names in a tooltip. That said they were there and nothing more:
no way to name one in the boot menu or delete it, and nothing at all for a
.efi or anything outside Managed_ISOs.
"""
import os
from typing import Callable

from src.core.inventory import UnmanagedImage
from src.ui.components import Row, make_button
from src.ui.distro_card import human_size

ImageAction = Callable[[UnmanagedImage], None]


class UnmanagedRow(Row):
    """One image VEIM leaves alone, with what can still be done to it.

    Only the dashboard knows whether the catalog can update an image, so it
    says whether to offer Adopt each time it hands the row an image.
    """

    def __init__(self, image: UnmanagedImage, adoptable: bool,
                 on_adopt: ImageAction, on_rename: ImageAction, on_delete: ImageAction,
                 parent=None):
        super().__init__(parent, elide_meta=True)

        self.btn_adopt = make_button("Adopt", "tonal", lambda: on_adopt(self.image))
        self.btn_adopt.setToolTip("Track this ISO and offer updates for it")
        self.add_action(self.btn_adopt)

        # Only for an image VEIM cannot adopt. One it can is named for what
        # it is once adopted, like everything in the library.
        self.btn_rename = make_button("Menu Name…", "quiet", lambda: on_rename(self.image))
        self.btn_rename.setToolTip("Choose the name the Ventoy boot menu shows for it")
        self.add_action(self.btn_rename)

        self.btn_delete = make_button("Delete", "subtle-danger", lambda: on_delete(self.image))
        self.btn_delete.setToolTip("Delete the file from the drive")
        self.add_action(self.btn_delete)

        self.set_image(image, adoptable)

    def set_image(self, image: UnmanagedImage, adoptable: bool):
        self.image = image
        if image.identity:
            self.icon.set_distro(image.identity.key)
        else:
            # No logo to show, so the chip names the kind of file instead.
            self.icon.set_backdrop(False)
            self.icon.set_icon(None)
            self.icon.setText(os.path.splitext(image.filename)[1][1:].upper())

        title = image.alias or image.filename
        self.title.setText(title)
        bits = [image.path if image.path != title else "",
                human_size(image.size_bytes), image.kind]
        if image.excluded:
            bits.append("Left alone")
        self.meta.setText("  ·  ".join(b for b in bits if b))

        self.btn_adopt.setVisible(adoptable)
        # Whatever VEIM cannot adopt is the user's to name.
        self.btn_rename.setVisible(not adoptable)
