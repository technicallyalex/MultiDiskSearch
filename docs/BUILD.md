# Build Multi Disk Search 1.0.0

Build on 64-bit Windows with Python 3.14 and NSIS 3.12.

1. Create a virtual environment and install requirements.txt and packaging/requirements-build.txt.
2. Download the portable NSIS 3.12 archive from the official NSIS SourceForge project and unpack it under build-tools/nsis-3.12, or pass its compiler path with --nsis.
3. Place the official GNU LGPL v3 and GPL v3 license texts in build-tools/licenses/LGPL-3.0.txt and GPL-3.0.txt. These accompany the bundled Qt runtime.
4. Run the regression suite and installer builder from the repository root:

```powershell
.\.venv\Scripts\python.exe -B -m unittest -v
.\.venv\Scripts\python.exe -B tools\build_installer.py
```

The builder uses PyInstaller with a QML module allowlist, copies the Resolve host components and license notices, generates a payload hash inventory, and compiles packaging/installer.nsi. Output is dist/MultiDiskSearch-1.0.0-Setup.exe with a SHA-256 checksum.

The frontend is a bundled Qt Quick executable. The Resolve integration launcher stays with the installed app, and setup registers it in Resolve's Workflow Integration Plugins directory. No Blackmagic SDK binaries or FFmpeg executable are distributed.

Tests and build outputs are separate from the installed application. Source logo outlines can be regenerated with tools/trace_brand.py; the approved design reference is under design/branding/variations/.

References: https://nsis.sourceforge.io/Download, https://nsis.sourceforge.io/License, https://pyinstaller.org/en/stable/.
