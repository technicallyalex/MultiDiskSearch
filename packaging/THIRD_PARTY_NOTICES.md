# Third-party components

MultiDiskSearch 1.1.0 bundles Python 3.14.6, PySide6/Shiboken6 6.12.0 and Qt 6.12.0 shared libraries. The executable is assembled with PyInstaller 6.22.3 and the installer is built with NSIS 3.12.

- Python: Python Software Foundation license and incorporated component notices. See licenses/Python-LICENSE.txt and https://www.python.org/downloads/source/.
- PySide6, Shiboken6 and the included Qt modules: used under the applicable LGPL v3 terms. Copies of LGPL v3 and GPL v3 are in licenses/. Component notices distributed with the wheels are retained there. Source: https://download.qt.io/official_releases/QtForPython/pyside6/ and https://download.qt.io/official_releases/qt/6.12/.
- PyInstaller bootloader: GPL with its distribution exception; see licenses/pyinstaller/ and https://pyinstaller.org/en/stable/license.html.
- NSIS: component notices are in licenses/NSIS-COPYING.txt; https://nsis.sourceforge.io/License.

Qt DLLs remain separate shared libraries in _internal/PySide6. Users may replace the LGPL components with compatible modified versions and reverse-engineer the application as needed to debug those modifications. The application contains no license restriction intended to prevent these rights. The repository contains the application source and packaging recipe: https://github.com/technicallyalex/MultiDiskSearch.

FFmpeg is not bundled. If available on the computer, it is used as a separate optional program for local thumbnail decoding. Resolve and Blackmagic SDK binaries are not bundled.

Filesystem notifications use watchdog 7.1.1 under the Apache License 2.0. Its license is included in licenses/watchdog/. Source: https://pypi.org/project/watchdog/7.1.1/.
