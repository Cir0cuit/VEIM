<div align="center">

<img src="src/assets/branding/veim-128.png" width="96" alt="">

# VEIM

**Ventoy Easy ISO Manager**

The ISOs on your [Ventoy](https://www.ventoy.net/) USB drive, kept current.

[![CI](https://github.com/Cir0cuit/VEIM/actions/workflows/ci.yml/badge.svg)](https://github.com/Cir0cuit/VEIM/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

[**Download**](https://github.com/Cir0cuit/VEIM/releases/latest) · 64 distributions and tools · 216 editions

![The library](docs/images/library.png)

<em>Fedora has a newer release. Linux Mint is being replaced on its own row.
A fresh Ubuntu is on its way. Two ISOs copied onto the drive by hand are
waiting to be adopted; a third, which VEIM does not recognise, is left alone.</em>

</div>

---

## Why

Ventoy turns one USB drive into a boot menu: copy ISO files onto it and pick
one at boot. The drive fills up with installers, live desktops and rescue tools,
and then it sits in a drawer. A year on, every file on it is a year old, and
the only way to find out which ones have been superseded is to open each
project's download page and compare version numbers by hand.

VEIM does that. Point it at the drive and it lists what is on there, asks each
project what its current release is, marks what has moved on, and downloads the
replacement in place. It also gives the boot menu readable names instead of
`linuxmint-22.3-cinnamon-64bit.iso`.

> **VEIM is not Ventoy.** Ventoy is a separate tool that you install onto the
> drive once, [from its own site](https://www.ventoy.net/). VEIM manages the
> ISO files on a drive that already has it. It never formats, partitions or
> reflashes anything.

## Install

Get the file for your system from the
[latest release](https://github.com/Cir0cuit/VEIM/releases/latest). There is
nothing else to install.

| | |
|---|---|
| **Windows** | `VEIM-x.y.z-windows-setup.exe` installs for your user only, so there is no administrator prompt. `VEIM-x.y.z-windows-portable.zip` runs from wherever you unpack it. |
| **macOS** | `VEIM-x.y.z-macos-arm64.dmg` for Apple Silicon, `-x86_64.dmg` for Intel. Open it and drag VEIM to Applications. |
| **Linux** | `VEIM-x.y.z-x86_64.AppImage`. `chmod +x` it once, then double-click. No packages, no dependencies. |

Every release also carries `SHA256SUMS.txt`.

<details>
<summary>The first launch says the app is unidentified</summary>

Releases are not code-signed: a certificate costs a few hundred dollars a year,
and this is a free tool.

- **Windows** — SmartScreen shows "Windows protected your PC". Click **More
  info**, then **Run anyway**.
- **macOS** — right-click VEIM in Applications and choose **Open** the first
  time, then confirm. Double-clicking is enough after that.

</details>

VEIM checks for a new release of itself on every start and, if there is one,
asks once: **Download**, **Skip This Version**, or **Remind Me in a Week**.
Closing the dialog means "not now", and it asks again next time. The version
you are running is shown next to the wordmark, and the drive picker has a
**Check for VEIM Updates** button for asking on demand.

## Using it

### Choose a drive

The first screen lists the removable drives it can see and marks the ones that
look like Ventoy: a `ventoy/` folder, a `Managed_ISOs/` folder, or "ventoy" in
the volume label. Pick yours, or **Browse Folder…** to any directory. A tiny
partition is flagged — that is Ventoy's EFI partition, not the one your ISOs
go on — and so is a read-only mount.

Only what is really mounted is offered: drive letters on Windows, `/Volumes`
on macOS, and mounts under `/media`, `/run/media` and `/mnt` on Linux. An empty
directory left behind by an unplugged drive is not, because the free space it
reports belongs to your system disk. Plug the drive in and press **Refresh**.

### The library

**Installed** is everything VEIM manages on the drive. Press **Check All
Updates** and every row asks its project for the current release, at once.
While an answer is pending the row reads **Checking…**, and so does the button.
Then each row settles on one of these:

| | |
|---|---|
| **Up to date** | The installed version is what the project publishes now. |
| **Update to 44** | A newer release exists, and the row names it. The row grows an **Update** button. |
| **Newer than 43** | The drive holds a *later* release than the catalog can find: a pre-release you fetched yourself, or a recipe that has fallen behind upstream. Nothing is offered, because it would be a downgrade. |
| **No current release** | The project's download page could not be read — a mirror is down, or the page has changed. The ISO is still fine to boot; VEIM just cannot say whether a newer one exists, and says that instead of guessing. |

The header sums it up — *2 updates available*, or *all up to date* — and a
single row can be asked on its own with **Check**.

### Updating

**Update** downloads the new release and replaces the old file. The transfer
shows on the row itself: percentage, speed, bytes, time left, and a **Cancel**
button. The old ISO stays on the drive and bootable until the new one has
fully arrived and been verified; only then is it swapped in and the old file
deleted. Several updates can run at the same time.

Every download works the same way, whether it is an update or a fresh install:

- It streams to a `.part` file next to the destination. If the connection
  drops it retries, and if VEIM is closed it picks up where it stopped the
  next time you press the button, using an HTTP range request. Cancelling on
  purpose is the one case that discards the partial file.
- Free space is checked before a byte is written.
- Where the project publishes a SHA-256, the finished file is hashed before it
  is renamed from `.part` to `.iso`. A mismatch deletes it, and the row says so.
- Memtest86+ ships its image inside a `.zip`; VEIM unpacks the ISO and drops
  the archive, so what lands on the drive is what Ventoy can boot.

### The catalog

**Browse Catalog** is the full list, filtered by category or by typing. A
project with several images has one row and a selector on it — Ubuntu's twelve
flavors, Debian's nine, Proxmox's four products — rather than a row per image.
Fedora has thirty-one, so it is four entries, split the way fedoraproject.org
splits them: Editions, Atomic Desktops, Spins and Labs.

**Download** starts the transfer and shows its progress on that row, so you
can queue the next one without leaving the page. A row whose edition is already
on the drive reads **Installed** and offers **Reinstall**.

### ISOs you copied there yourself

An ISO you put on the drive is not taken over on sight. It is offered for
adoption only if it is named exactly as the project itself names that download,
because that is the one case in which VEIM knows what it is and which version
it is, and can genuinely keep it current.

<div align="center">

![Adopting ISOs](docs/images/adopt.png)

</div>

When there are such files, the library shows **Adopt ISOs (2)**. Each one gets
its own answer:

- **Adopt** — it becomes a row, checked and updated like anything VEIM
  downloaded. One sitting in the drive root is moved into `Managed_ISOs/`.
- **Leave alone** — it is not asked about again. The button becomes
  **Excluded ISOs** once nothing is waiting, so the answer can be changed.
- Neither — asked again next time.

A renamed, remastered or otherwise unrecognised ISO is never listed, tracked or
touched. It boots as usual, and the library says how many of those it is
leaving alone. This is deliberate: a customised Clonezilla filed as the
official one would be "updated" — overwritten — at the next check. VEIM does
not guess.

### Removing

**Remove** asks which of two things you mean: **Delete File**, or **Keep File,
Stop Managing**. A kept file stays where it is and keeps booting; VEIM will not
check, update or offer it again. That is the way out for an ISO adopted by
mistake, or one you have customised since.

## What it never does

- **Download from a remembered URL.** Every transfer starts by reading the
  project's release page at that moment. A saved URL keeps working long after
  it has stopped pointing at the current release, which is how a "latest" ISO
  turns out to be two years old.
- **Trust a label.** Names like `-latest`, `-current` and `-stable` are not
  versions. A recipe reads the release listing and takes the newest by number.
- **Fall back to an older release.** When a mirror cannot be reached, the row
  says **No current release**. It does not quietly report the last release it
  managed to find as current.
- **Offer a downgrade.** See **Newer than 43** above.
- **Touch a file it did not download or you did not adopt.** ISOs live in
  `Managed_ISOs/`; the rest of the drive is Ventoy's and yours.

## Catalog

<!-- catalog:start -->

| Category | Distributions |
|---|---|
| **Beginner Friendly** | elementary OS, FydeOS, Linux Lite, Linux Mint, Pop!_OS, TUXEDO OS, Ubuntu, Zorin OS |
| **General Purpose** | Debian, Fedora, Fedora Atomic Desktops, Fedora Labs, Fedora Spins, KDE Neon, Mageia, MX Linux, openSUSE |
| **Rolling Release** | Arch Linux, Artix Linux, EndeavourOS, Manjaro, Omarchy |
| **Enthusiast** | Devuan, Gentoo, NixOS, Slackware, Void Linux |
| **Gaming & Performance** | Bazzite, CachyOS, Garuda Linux, Nobara Project, PikaOS |
| **Security & Privacy** | CAINE, HackerOS, Kali Linux, Parrot OS, Qubes OS, Tails |
| **Server & Enterprise** | AlmaLinux OS, CentOS Stream, FreeBSD, IPFire, openEuler, Oracle Linux, Proxmox, Rocky Linux, Talos Linux, XCP-ng |
| **Rescue & Diagnostics** | Clonezilla, GParted Live, Grml, hrmpf, Memtest86+, netboot.xyz, Rescuezilla, ShredOS, Super GRUB2 Disk, SystemRescue |
| **Lightweight** | Alpine Linux, antiX, Puppy Linux, Q4OS, SparkyLinux, Tiny Core Linux |

<details>
<summary>Every edition, by entry</summary>

**Beginner Friendly**

- **elementary OS** — Standard 64-bit Edition
- **FydeOS** — Intel Modern (6th - 14th Gen), AMD Graphics & APUs, Intel Slim (Celeron & Pentium)
- **Linux Lite** — 64-bit (Xfce)
- **Linux Mint** — Cinnamon, MATE, Xfce
- **Pop!_OS** — Standard (Intel / AMD), NVIDIA Edition
- **TUXEDO OS** — Standard Edition (KDE Plasma)
- **Ubuntu** — Ubuntu Desktop, Ubuntu Server, Kubuntu, Xubuntu, Lubuntu, Ubuntu MATE, Ubuntu Budgie, Ubuntu Cinnamon, Ubuntu Unity, Ubuntu Studio, Edubuntu, Ubuntu Kylin
- **Zorin OS** — Core Edition, Education Edition

**General Purpose**

- **Debian** — Netinst (Network Installer), Live GNOME, Live KDE Plasma, Live Xfce, Live Cinnamon, Live MATE, Live LXQt, Live LXDE, Live Standard (Console)
- **Fedora** — Workstation (GNOME), KDE Plasma Desktop, Server (DVD), Server (Network Install), IoT, Everything (Network Install)
- **Fedora Atomic Desktops** — Silverblue (GNOME), Kinoite (KDE Plasma), Sway Atomic, Budgie Atomic, COSMIC Atomic
- **Fedora Labs** — Astronomy, Design Suite, Games, Jam, Python Classroom, Robotics Suite, Scientific, Security Lab
- **Fedora Spins** — Xfce, Cinnamon, Budgie, COSMIC, MATE-Compiz, LXQt, LXDE, i3, Sway, Miracle, KDE Plasma Mobile, Sugar on a Stick
- **KDE Neon** — User Edition
- **Mageia** — Classic Installer (DVD), Live Edition (KDE Plasma), Live Edition (GNOME), Live Edition (Xfce)
- **MX Linux** — Xfce, Xfce AHS, KDE Plasma, Fluxbox
- **openSUSE** — Tumbleweed (Offline DVD), Tumbleweed Live (KDE Plasma), Tumbleweed Live (GNOME), Tumbleweed (Network Install), Leap (Offline DVD), Leap (Network Install)

**Rolling Release**

- **Arch Linux** — Standard ISO
- **Artix Linux** — KDE Plasma (OpenRC), Xfce Edition (OpenRC), Base Edition (OpenRC), Base Edition (Runit), Cinnamon Edition (OpenRC), MATE Edition (OpenRC)
- **EndeavourOS** — Galileo Neo
- **Manjaro** — KDE Plasma, GNOME, Xfce
- **Omarchy** — Standard

**Enthusiast**

- **Devuan** — Desktop Live, Net Install, Server
- **Gentoo** — Minimal Install CD, LiveGUI
- **NixOS** — Graphical Live Installer (GNOME), Minimal Console Edition
- **Slackware** — Install DVD (64-bit)
- **Void Linux** — Base (glibc), Xfce (glibc), Base (musl), Xfce (musl)

**Gaming & Performance**

- **Bazzite** — Desktop Edition (KDE Plasma), Desktop Edition (GNOME), Handheld Edition (Steam Deck / Ally), NVIDIA Desktop (KDE Plasma)
- **CachyOS** — Desktop Edition, Handheld Edition
- **Garuda Linux** — Dr460nized (KDE), Dr460nized Gaming Edition, GNOME Edition, KDE Lite, Xfce Edition, Cinnamon Edition, Mokka (KDE), Hyprland Edition, Sway Edition, i3 Edition
- **Nobara Project** — Official (GNOME), KDE Plasma, GNOME, Steam HTPC, Steam Handheld
- **PikaOS** — KDE Plasma, GNOME, Hyprland, KDE Plasma (NVIDIA), GNOME (NVIDIA)

**Security & Privacy**

- **CAINE** — Live 64-bit
- **HackerOS** — LTS Edition (Long Term Support), Official Edition, Cybersecurity Edition, Gaming Edition, NVIDIA Edition
- **Kali Linux** — Installer, Network Installer, Kali Purple
- **Parrot OS** — Security Edition, Home Edition
- **Qubes OS** — Installer
- **Tails** — Standard ISO Image

**Server & Enterprise**

- **AlmaLinux OS** — Minimal Install, Full DVD, Boot / Netinstall
- **CentOS Stream** — DVD, Boot
- **FreeBSD** — Installer (disc1), Installer with packages (dvd1), Network installer (bootonly)
- **IPFire** — Installer x86_64
- **openEuler** — LTS (DVD), LTS (Network Install), Innovation release (DVD), Innovation release (Network Install)
- **Oracle Linux** — Full ISO (DVD), Boot ISO
- **Proxmox** — Virtual Environment, Backup Server, Mail Gateway, Datacenter Manager
- **Rocky Linux** — DVD, Minimal, Boot
- **Talos Linux** — Bare metal (amd64)
- **XCP-ng** — Installer, Network installer

**Rescue & Diagnostics**

- **Clonezilla** — Alternative Stable (Ubuntu Base), Standard Stable (Debian Base)
- **GParted Live** — Live AMD64
- **Grml** — Full, Small
- **hrmpf** — x86_64
- **Memtest86+** — 64-bit, 64-bit (GRUB)
- **netboot.xyz** — Standard ISO
- **Rescuezilla** — Standard 64-bit
- **ShredOS** — Standard x86-64
- **Super GRUB2 Disk** — Hybrid (BIOS and UEFI), 64-bit UEFI, Legacy BIOS, 32-bit UEFI
- **SystemRescue** — Live AMD64

**Lightweight**

- **Alpine Linux** — Standard x86_64, Extended x86_64, Virtual x86_64, Xen x86_64
- **antiX** — Full, Core
- **Puppy Linux** — BookwormPup64, FossaPup64, TrixiePup64
- **Q4OS** — KDE Plasma Live, Trinity Live, Install CD
- **SparkyLinux** — Xfce Edition, KDE Plasma Edition, LXQt Edition, MATE Edition, MinimalGUI (Openbox), MinimalCLI (Console), Rolling: Xfce, Rolling: KDE Plasma, Rolling: LXQt, Rolling: MATE, Rolling: MinimalGUI, Rolling: MinimalCLI, Rolling: GameOver, Rolling: Multimedia, Rolling: Rescue
- **Tiny Core Linux** — CorePlus (x86), TinyCore (x86), CorePure64 (x86_64), TinyCorePure64 (x86_64), Core (x86)

</details>

<!-- catalog:end -->

A few things are absent on purpose. Kali's Live and Everything images are
torrent-only, so there is no download to keep current. Images published under
a name that never changes — Bazzite's `-stable`, `netboot.xyz.iso`, anything
called `-latest` — can be downloaded and updated through the catalog, but a
copy found on a drive cannot be told apart from an older one, so they are never
offered for adoption.

Adding an entry is a small, well-trodden job:
[CONTRIBUTING.md](CONTRIBUTING.md) walks through it.

## Where things live

On the drive:

| | |
|---|---|
| `Managed_ISOs/` | The ISOs, and `veim_inventory.json` — what each one is, which version, and which files you asked to be left alone. Delete it and you lose only the list: the ISOs stay, and are offered for adoption again. |
| `ventoy/ventoy.json` | Written by VEIM. Points Ventoy at `Managed_ISOs/` and gives each managed ISO a menu name such as `Linux Mint Cinnamon`. Aliases for files elsewhere on the drive are kept as you wrote them. Because the menu is limited to `Managed_ISOs/`, an ISO left in the drive root drops out of it — the library says so and offers to move it in, without managing it. |

On your computer, in `%LOCALAPPDATA%\VEIM`, `~/.local/share/VEIM` or
`~/Library/Application Support/VEIM`: the log, the rendered logos, and the
record of which VEIM release you skipped or snoozed. Deleting the folder costs
nothing.

## Themes

Dark Modern, Amoled Black, Gruvbox Dark, Cyberpunk, Nord, Dracula, Solarized
Light and Clean Light, or **System** to follow the desktop.

<div align="center">

![The catalog](docs/images/catalog.png)

<em>Gruvbox Dark · Amoled Black · Solarized Light</em>

<img src="docs/images/theme-gruvbox.png" width="32%"> <img src="docs/images/theme-amoled.png" width="32%"> <img src="docs/images/theme-solarized.png" width="32%">

</div>

## From source

```bash
git clone https://github.com/Cir0cuit/VEIM
cd VEIM
pip install -r requirements.txt
python main.py
```

Python 3.10 or newer. [CONTRIBUTING.md](CONTRIBUTING.md) covers the test
suite, the layout, how to add a distribution or a theme, and how the installers
are built.

## License

MIT — see [LICENSE](LICENSE).

Distribution names and logos are trademarks of their respective projects and
are used only to identify them. The rendered logos are in
[`src/assets/icons/`](src/assets/icons/); if you fork and redistribute VEIM,
check each project's trademark policy.
