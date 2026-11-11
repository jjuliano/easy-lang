"""Install Easy for this Python without changing a Homebrew install.

    curl -fsSL -A easy-lang https://raw.githubusercontent.com/jjuliano/easy-lang/main/install.py | python3

Creates ~/.easy-lang and links the package into this Python's user site,
so `python3 -m easy` works. Homebrew's Python refuses pip install and
reports externally-managed-environment. This script does not pass
--break-system-packages.
"""

import shutil
import site
import subprocess
import sys
from pathlib import Path

HOME_VENV = Path.home() / ".easy-lang"
PACKAGE = "git+https://github.com/jjuliano/easy-lang.git"


def venv_python(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def site_packages(venv: Path) -> Path:
    if sys.platform == "win32":
        return venv / "Lib" / "site-packages"
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return venv / "lib" / version / "site-packages"


def ensure_venv(venv: Path) -> Path:
    python = venv_python(venv)
    if python.exists():
        version = subprocess.check_output(
            [
                str(python),
                "-c",
                "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
            ],
            text=True,
        ).strip()
        want = f"{sys.version_info.major}.{sys.version_info.minor}"
        if version == want:
            return python
        shutil.rmtree(venv)
    subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    return venv_python(venv)


def link_package(venv: Path) -> Path:
    if not site.ENABLE_USER_SITE:
        raise SystemExit(
            "easy: this Python ignores the user site. "
            f"Run {venv_python(venv)} -m easy URL"
        )
    source = site_packages(venv) / "easy"
    if not source.is_dir():
        raise SystemExit(f"easy: install did not produce {source}")
    user_site = Path(site.getusersitepackages())
    user_site.mkdir(parents=True, exist_ok=True)
    link = user_site / "easy"
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise SystemExit(f"easy: {link} already exists and is not a link from this installer")
    link.symlink_to(source, target_is_directory=True)
    return link


def main() -> None:
    python = ensure_venv(HOME_VENV)
    subprocess.check_call([str(python), "-m", "pip", "install", "--upgrade", PACKAGE])
    link = link_package(HOME_VENV)
    print(f"Installed for {sys.executable}")
    print(f"Linked {link}")
    print("Run: python3 -m easy URL")


if __name__ == "__main__":
    main()
