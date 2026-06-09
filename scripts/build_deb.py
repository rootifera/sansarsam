from __future__ import annotations

from email.utils import formatdate
from pathlib import Path
import gzip
import os
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
PACKAGE_ROOT = BUILD_DIR / "debroot"

sys.path.insert(0, str(ROOT))
from version import APP_NAME, APP_VERSION, PACKAGE_NAME  # noqa: E402


def main() -> int:
    pyinstaller = ROOT / ".venv" / "bin" / "pyinstaller"
    if not pyinstaller.exists():
        pyinstaller = Path("pyinstaller")

    DIST_DIR.mkdir(exist_ok=True)
    BUILD_DIR.mkdir(exist_ok=True)

    run(
        [
            str(pyinstaller),
            "--onefile",
            "--windowed",
            "--name",
            APP_NAME,
            "--add-data",
            f"{ROOT / 'assets'}:assets",
            "--icon",
            str(ROOT / "assets" / "icon.png"),
            "--distpath",
            str(DIST_DIR),
            "--workpath",
            str(BUILD_DIR / "pyinstaller"),
            "--specpath",
            str(BUILD_DIR / "pyinstaller"),
            "main.py",
        ]
    )

    app_binary = DIST_DIR / APP_NAME
    if not app_binary.exists():
        raise SystemExit(f"PyInstaller did not create {app_binary}")

    if PACKAGE_ROOT.exists():
        shutil.rmtree(PACKAGE_ROOT)

    install_binary = PACKAGE_ROOT / "usr" / "lib" / PACKAGE_NAME / APP_NAME
    install_binary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(app_binary, install_binary)
    install_binary.chmod(0o755)

    bin_dir = PACKAGE_ROOT / "usr" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    os.symlink(f"../lib/{PACKAGE_NAME}/{APP_NAME}", bin_dir / PACKAGE_NAME)

    icon_dir = PACKAGE_ROOT / "usr" / "share" / "icons" / "hicolor" / "1024x1024" / "apps"
    icon_dir.mkdir(parents=True, exist_ok=True)
    icon_path = icon_dir / f"{PACKAGE_NAME}.png"
    shutil.copy2(ROOT / "assets" / "icon.png", icon_path)
    icon_path.chmod(0o644)

    desktop_dir = PACKAGE_ROOT / "usr" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        desktop_dir / f"{PACKAGE_NAME}.desktop",
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={APP_NAME}",
                "Comment=Simple Greaseweazle UI for floppy image workflows",
                f"Exec={PACKAGE_NAME}",
                f"Icon={PACKAGE_NAME}",
                "Terminal=false",
                "Categories=Utility;",
                "",
            ]
        ),
        0o644,
    )

    doc_dir = PACKAGE_ROOT / "usr" / "share" / "doc" / PACKAGE_NAME
    doc_dir.mkdir(parents=True, exist_ok=True)
    write_text(
        doc_dir / "README.Debian",
        f"{APP_NAME} is packaged as a PyInstaller desktop application.\n",
        0o644,
    )
    write_gzip(
        doc_dir / "changelog.gz",
        "\n".join(
            [
                f"{PACKAGE_NAME} ({APP_VERSION}) unstable; urgency=medium",
                "",
                "  * Add Tools tab for erase, clean, and firmware update actions.",
                "  * Add visible application version.",
                "",
                f" -- Omur <omur@example.com>  {formatdate(localtime=True)}",
                "",
            ]
        ).encode(),
    )
    write_text(
        doc_dir / "copyright",
        "\n".join(
            [
                "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/",
                "Source: https://github.com/omur/sansarsam",
                "",
                "Files: *",
                "Copyright: Omur",
                "License: MIT",
                "",
                "License: MIT",
                " Permission is hereby granted, free of charge, to any person obtaining a copy",
                " of this software and associated documentation files (the Software), to deal",
                " in the Software without restriction, including without limitation the rights",
                " to use, copy, modify, merge, publish, distribute, sublicense, and/or sell",
                " copies of the Software, and to permit persons to whom the Software is",
                " furnished to do so, subject to the following conditions.",
                "",
                " The above copyright notice and this permission notice shall be included in",
                " all copies or substantial portions of the Software.",
                "",
                " THE SOFTWARE IS PROVIDED AS IS, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR",
                " IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,",
                " FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.",
                "",
            ]
        ),
        0o644,
    )

    man_dir = PACKAGE_ROOT / "usr" / "share" / "man" / "man1"
    man_dir.mkdir(parents=True, exist_ok=True)
    write_gzip(
        man_dir / f"{PACKAGE_NAME}.1.gz",
        "\n".join(
            [
                f".TH {PACKAGE_NAME.upper()} 1",
                f".SH NAME",
                f"{PACKAGE_NAME} \\- simple Greaseweazle UI",
                ".SH SYNOPSIS",
                f".B {PACKAGE_NAME}",
                ".SH DESCRIPTION",
                f"{APP_NAME} is a desktop UI for reading, writing, converting, and managing floppy disks with gw.",
                "",
            ]
        ).encode(),
    )

    control_dir = PACKAGE_ROOT / "DEBIAN"
    control_dir.mkdir(parents=True, exist_ok=True)
    installed_size = directory_size_kib(PACKAGE_ROOT / "usr")
    write_text(
        control_dir / "control",
        "\n".join(
            [
                f"Package: {PACKAGE_NAME}",
                f"Version: {APP_VERSION}",
                "Section: utils",
                "Priority: optional",
                "Architecture: amd64",
                "Maintainer: Omur <omur@example.com>",
                "Depends: libc6 (>= 2.34), zlib1g",
                "Recommends: greaseweazle",
                f"Installed-Size: {installed_size}",
                "Homepage: https://github.com/omur/sansarsam",
                "Description: Simple Greaseweazle UI for floppy image workflows",
                " Sansarsam is a small desktop UI for reading, writing, converting,",
                " erasing, cleaning, and updating Greaseweazle floppy workflows.",
                "",
            ]
        ),
        0o644,
    )

    normalize_package_modes(PACKAGE_ROOT)

    deb_path = DIST_DIR / f"{PACKAGE_NAME}_{APP_VERSION}_amd64.deb"
    if deb_path.exists():
        deb_path.unlink()

    run(["dpkg-deb", "--root-owner-group", "--build", str(PACKAGE_ROOT), str(deb_path)])
    write_release_tarball(app_binary)

    print(deb_path)
    return 0


def run(command: list[str]) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def write_text(path: Path, content: str, mode: int) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(mode)


def write_gzip(path: Path, content: bytes) -> None:
    with gzip.open(path, "wb", compresslevel=9) as handle:
        handle.write(content)
    path.chmod(0o644)


def directory_size_kib(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file() and not child.is_symlink():
            total += child.stat().st_size
    return max(1, (total + 1023) // 1024)


def normalize_package_modes(path: Path) -> None:
    for child in path.rglob("*"):
        if child.is_dir():
            child.chmod(0o755)
    path.chmod(0o755)


def write_release_tarball(app_binary: Path) -> None:
    tar_path = DIST_DIR / f"{PACKAGE_NAME}_{APP_VERSION}_linux.tar.gz"
    if tar_path.exists():
        tar_path.unlink()
    with tarfile.open(tar_path, "w:gz") as archive:
        archive.add(app_binary, arcname=APP_NAME)


if __name__ == "__main__":
    raise SystemExit(main())
