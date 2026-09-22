<div align="center">

<img src="src/assets/branding/veim-128.png" width="96" alt="">

# VEIM

**Ventoy Easy ISO Manager**

Keep the operating systems and tools on your [Ventoy](https://www.ventoy.net/)
USB drive up to date, without hunting down a download page for every one.

[![CI](https://github.com/Cir0cuit/VEIM/actions/workflows/ci.yml/badge.svg)](https://github.com/Cir0cuit/VEIM/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

[**Download**](https://github.com/Cir0cuit/VEIM/releases/latest) · 64 distributions and tools · 216 editions

![The installed library](docs/images/library.png)

<em>Fedora has a newer release, Linux Mint is being replaced on its own row, a
fresh Ubuntu is on its way, two are current, and Tails' download page could not
be read. Two ISOs copied on by hand are waiting to be adopted; a third, which
VEIM does not recognise, is left alone.</em>

</div>

---

## What it is

Ventoy makes a single USB drive boot anything you copy onto it. Put a dozen ISO
files on the stick and choose one from a menu at boot: try a live desktop, run
an installer, boot a rescue system, test your RAM. No reflashing between them.

The hard part is keeping that collection current. Six months later the files on
the drive look exactly as they did the day you copied them, and the only way to
find out which ones have been superseded is to open a dozen download pages and
compare version numbers by hand. Most sticks quietly go stale instead.

VEIM does that checking for you. Point it at the drive and it lists what is on
there, marks what has a newer release available, downloads the replacement, and
gives the boot menu readable names instead of
`linuxmint-22.3-cinnamon-64bit.iso`.

> **VEIM is not Ventoy, and does not replace it.** Ventoy is a separate tool
> that you install onto the drive once, [from its own site](https://www.ventoy.net/).
> VEIM manages the ISO files on a drive that already has it. It never formats,
> partitions or reflashes anything.

## Download

Grab the file for your system from the
[latest release](https://github.com/Cir0cuit/VEIM/releases/latest) and open it.
Nothing else to install.

| | |
|---|---|
| **Windows** | `VEIM-x.y.z-windows-setup.exe` — double-click, next, done. Installs for your user only, so there is no administrator prompt. A portable `.zip` is there too if you would rather not install anything. |
| **macOS** | `VEIM-x.y.z-macos-arm64.dmg` (Apple Silicon) or `-x86_64.dmg` (Intel). Open it and drag VEIM to Applications. |
| **Linux** | `VEIM-x.y.z-x86_64.AppImage` — `chmod +x` it once and double-click. No packages, no dependencies. |

The app checks for a new version of itself each time it starts and asks, in so
many words, what you want to do about it: download it, skip that version, or
hear nothing for a week. The version it is running sits next to the VEIM wordmark,
and the drive picker has a **Check for VEIM Updates** button — separate from
**Check All Updates**, which is about the ISOs on your drive.

<details>
<summary>The first launch warns that the app is unidentified</summary>

Releases are not code-signed, because a certificate costs a few hundred dollars
a year and this is a free tool.

- **Windows** — SmartScreen shows "Windows protected your PC". Click **More
  info**, then **Run anyway**.
- **macOS** — right-click VEIM in Applications and choose **Open** the first
  time, then confirm. Double-clicking is enough after that.

Every release also ships a `SHA256SUMS.txt` if you want to check what you
downloaded.

</details>

## First run

1. Plug in the drive and start the app. It lists the removable drives it can
   see and marks the ones that look like Ventoy — pick yours, or browse to a
   folder.
2. **Installed** is what is already on the drive. ISOs you copied there
   yourself are offered for adoption if VEIM can tell what they are — see
   [below](#isos-you-put-there-yourself).
3. **Browse Catalog** is the list of 64 entries. Choose an edition from the
   selector on a row and press **Download**. It streams straight to the drive
   and reports progress on that row, so you can queue up another while it runs.
4. Come back later and press **Check All Updates**.

## Keeping the drive current

**Check All Updates** looks up the current release of everything on the drive,
all at once. Each row shows **Checking…** while its answer is pending — so does
the button, and pressing it again while a check runs does nothing — and then
settles on one of these:

| | |
|---|---|
| **Up to date** | The installed version matches what the project publishes now. |
| **Update to 44** | A newer release exists, and the row names it. The row grows an **Update** button that downloads the new version and replaces the old file; while it does, the row itself shows the progress and a **Cancel** button, and the old ISO stays bootable until the new one has arrived and been verified. |
| **Newer than 43** | The drive holds a *later* release than the catalog can find — a pre-release you fetched yourself, or a recipe that has fallen behind upstream. Nothing is offered: that would be a downgrade. |
| **No current release** | The current version could not be worked out — a mirror is down, or a download page has changed. Deliberately *not* reported as up to date. |

The header sums it up: *2 updates available*, or *all up to date*. Individual
rows can be checked on their own with **Check**. An update is just a download:
resumable, verified where a checksum exists, reported on the row.

Every download URL is read from the project's own release page at the moment
you press Download. None is stored — a saved URL keeps working long after it
has stopped pointing at the current release, which is how you end up booting a
two-year-old ISO that looked fine in the list. For the same reason a recipe
never pins a release folder and never trusts a "latest" label: it reads the
release listing and takes the newest.

## ISOs you put there yourself

An ISO you copied onto the drive is *not* taken over on sight. It is offered for
adoption only if it is named exactly like an official download — the same name
the project's own mirror would have given it — because that is the only case in
which VEIM knows its version and can genuinely keep it current.

<div align="center">

![Adopting ISOs](docs/images/adopt.png)

</div>

**Adopt ISOs** in the header lists those, and each one is yours to decide:

- **Adopt** — it becomes a row in the list, checked and updated like any other.
  An ISO sitting in the drive root is moved into `Managed_ISOs/` on the way in.
- **Leave alone** — it stays as it is and is not asked about again. The button
  becomes **Excluded ISOs** once nothing is waiting, so the choice can be
  undone. One left in the drive root is offered a plain move into
  `Managed_ISOs/`, where Ventoy looks, and is still not managed.
- Neither — asked again next time.

A renamed, customised or unrecognised ISO is never listed, tracked or changed:
a customised Clonezilla filed as the official release would be "updated" —
overwritten — by the next check, so VEIM refuses to guess. The library says how
many such files it is leaving alone. **Remove** on a row offers the same
distinction: delete the file, or keep it and merely stop managing it.

## What else it does

| | |
|---|---|
| **Browse and install** | 64 entries, 216 editions, filtered by category or free-text search. Downloads start from the row you are looking at and report progress there, so you can queue several without leaving the catalog. |
| **Resumable transfers** | Downloads stream to a `.part` file and pick up where they stopped, using HTTP range requests. Several can run at once, and free space is checked before any of them starts. |
| **Checksum verification** | Where a project publishes a SHA-256, the finished file is hashed before it is renamed from `.part` to `.iso`, and a mismatch deletes it instead of writing it to your drive. |
| **Readable boot menu** | Writes `ventoy/ventoy.json` aliases like `Fedora 44 KDE Plasma`, and points Ventoy at `Managed_ISOs/` so the menu shows the collection and nothing else. Aliases you added by hand are preserved, and if an ISO in the drive root drops out of the menu as a result, the library says so and offers to move it in. |
| **Unpacks archive-only releases** | Memtest86+ ships its image only inside a `.zip`, and Ventoy boots `.iso` files. VEIM checks the archive, extracts the ISO and deletes the zip. |
| **Eight themes** | Dark Modern, Amoled Black, Gruvbox Dark, Cyberpunk, Nord, Dracula, Solarized Light and Clean Light, plus System Match. |

<div align="center">

![The catalog](docs/images/catalog.png)

<em>Gruvbox Dark · Amoled Black · Solarized Light</em>

<img src="docs/images/theme-gruvbox.png" width="32%"> <img src="docs/images/theme-amoled.png" width="32%"> <img src="docs/images/theme-solarized.png" width="32%">

</div>

## Catalog

Every entry is read from the project's own release page or mirror listing each
time it is asked, so what VEIM offers is what the project publishes today.
Editions of one project are picked from a selector on its row rather than
filling the list with near-duplicates: Ubuntu has twelve flavors, Proxmox four
products, SparkyLinux a stable and a rolling line. Fedora publishes some forty
images, so it is four entries, split the way fedoraproject.org splits them:
Editions, Atomic Desktops, Spins and Labs.

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

A few things are deliberately absent. Kali's Live and Everything images are
torrent-only, so there is no download to keep current. Images published under
a name that never changes — Bazzite's `-stable`, netboot.xyz, anything called
`-latest` — cannot be recognised on a drive by name, so they are downloaded and
updated through the catalog but never offered for adoption.

Missing something? Adding an entry is a small, well-worn job — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Questions

**Do I need Ventoy installed first?** Yes. Making the drive bootable is a
one-time job for [Ventoy's own installer](https://www.ventoy.net/). VEIM never
formats a drive — it creates `Managed_ISOs/` and `ventoy/` on one and writes
only in there.

**The drive is not in the list.** VEIM offers what is really mounted: the drive
letters on Windows, `/Volumes` on macOS, and whatever is mounted under `/media`,
`/run/media` and `/mnt` on Linux. An empty directory left behind by an unmounted
drive is not offered — the free space such a folder reports belongs to the
system disk, not to anything you plugged in. Mount the drive and press
**Refresh**, or point **Browse Folder…** straight at it.

**Will it touch files I put on the drive myself?** Not without asking. ISOs
live in `Managed_ISOs/`, the boot menu is `ventoy/ventoy.json`, and aliases you
wrote by hand in that file are kept. An ISO is only ever adopted, moved,
replaced or deleted because you chose that for it.

**Can I use ISOs I already downloaded?** Yes. Copy them onto the drive and
press **Adopt ISOs**. Anything named like an official download is offered;
anything else boots as usual and is left alone.

**What happens if a download is interrupted?** It leaves a `.part` file beside
the destination and resumes with a range request the next time you start it.
Cancelling on purpose is the one case that throws the partial file away.

**A row says "No current release" — is something broken?** Upstream, probably.
It means VEIM could not read that project's download page, usually because a
mirror is down or the page has been redesigned. The ISO on your drive is still
fine to boot; VEIM simply cannot tell you whether a newer one exists, so it says
that instead of guessing.

**Where does it keep its own files?** The logo cache and the update-check record
go in `%LOCALAPPDATA%\VEIM`, `~/.local/share/VEIM` or
`~/Library/Application Support/VEIM`. On the drive itself, the inventory is
`Managed_ISOs/veim_inventory.json`. Deleting either costs you nothing but the
list: the ISOs stay, and are offered for adoption again.

## Building it yourself

```bash
git clone https://github.com/Cir0cuit/VEIM
cd VEIM
pip install -r requirements.txt
python main.py
```

Python 3.10 or newer. [CONTRIBUTING.md](CONTRIBUTING.md) covers the test suite,
the layout, how to add a distribution or a theme, and how the installers are
built.

## License

MIT — see [LICENSE](LICENSE).

Distribution names and logos are trademarks of their respective projects, and
are included here solely to identify them. The rendered logos live in
[`src/assets/icons/`](src/assets/icons/); if you fork and redistribute VEIM,
check each project's own trademark policy.
