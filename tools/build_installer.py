"""Build the bundled Windows v1 application and NSIS installer."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from version import VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--nsis', type=Path, default=ROOT/'build-tools/nsis-3.12/makensis.exe')
    args = parser.parse_args()
    if sys.platform != 'win32' or not args.nsis.is_file():
        raise RuntimeError('Build on Windows with the NSIS compiler available via --nsis.')
    build = ROOT/'build'
    output = ROOT/'dist'
    build.mkdir(exist_ok=True)
    output.mkdir(exist_ok=True)
    environment = os.environ.copy()
    windows = Path(os.environ.get('WINDIR', 'C:/Windows'))
    environment['PATH'] = os.pathsep.join(str(p) for p in (
        Path(sys.executable).parent, Path(sys.base_prefix), Path(sys.base_prefix)/'DLLs',
        windows/'System32', windows))
    for key in ('QT_PLUGIN_PATH','QT_QPA_PLATFORM_PLUGIN_PATH','QML2_IMPORT_PATH','PYTHONPATH'):
        environment.pop(key, None)
    from PySide6.QtGui import QGuiApplication, QIcon
    app = QGuiApplication.instance() or QGuiApplication([])
    icon = build/'app.ico'
    if not QIcon(str(ROOT/'assets/brand/mds-icon.svg')).pixmap(256,256).save(str(icon), 'ICO'):
        raise RuntimeError('Could not generate installer icon.')
    parts = tuple(int(n) for n in VERSION.split('.')) + (0,)
    version_info = build/'version-info.txt'
    version_info.write_text(f'''VSVersionInfo(ffi=FixedFileInfo(filevers={parts!r}, prodvers={parts!r}, mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0,0)), kids=[StringFileInfo([StringTable('040904B0', [StringStruct('ProductName','MultiDiskSearch'), StringStruct('FileDescription','MultiDiskSearch'), StringStruct('FileVersion','{VERSION}'), StringStruct('ProductVersion','{VERSION}')])]), VarFileInfo([VarStruct('Translation',[1033,1200])])])''', encoding='utf-8')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed',
               '--name', 'MultiDiskSearch', '--icon', str(icon), '--version-file', str(version_info),
               '--distpath', str(build/'bundle'), '--workpath', str(build/'pyinstaller'),
               '--specpath', str(build), '--additional-hooks-dir', str(ROOT/'packaging/hooks'),
               '--hidden-import', 'PySide6.QtSvg', '--hidden-import', 'watchdog.observers.read_directory_changes']
    for name in ('Main.qml','Theme.qml','ActionButton.qml','ChoiceBox.qml','NumberBox.qml','PanelDialog.qml','qmldir'):
        command += ['--add-data', f'{ROOT/name}:.']
    command += ['--add-data', f'{ROOT/"assets"}:assets', str(ROOT/'qt_app.py')]
    subprocess.run(command, cwd=ROOT, check=True, env=environment)
    payload = build/'bundle/MultiDiskSearch'
    for name in ('MultiDiskSearch.py','resolve_bridge.py','relink_core.py'):
        shutil.copy2(ROOT/name, payload/name)
    shutil.copy2(ROOT/'packaging/Register-Plugin.ps1', payload/'Register-Plugin.ps1')
    shutil.copy2(ROOT/'docs/USER_GUIDE.txt', payload/'USER_GUIDE.txt')
    shutil.copy2(ROOT/'packaging/THIRD_PARTY_NOTICES.md', payload/'THIRD_PARTY_NOTICES.md')
    shutil.copy2(icon, payload/'app.ico')
    (payload/'VERSION.txt').write_text(VERSION+'\n', encoding='utf-8')
    licenses = payload/'licenses'
    licenses.mkdir(exist_ok=True)
    for name in ('LGPL-3.0.txt','GPL-3.0.txt'):
        shutil.copy2(ROOT/'build-tools/licenses'/name, licenses/name)
    python_license = Path(sys.base_prefix)/'LICENSE.txt'
    if not python_license.exists():
        raise RuntimeError('Python distribution license is missing.')
    shutil.copy2(python_license, licenses/'Python-LICENSE.txt')
    for package in ('pyside6-essentials','pyside6-addons','shiboken6','pyinstaller','watchdog'):
        distribution = importlib.metadata.distribution(package)
        for entry in distribution.files or []:
            if 'licenses/' in str(entry).replace('\\','/'):
                source = Path(distribution.locate_file(entry))
                if source.is_file():
                    target = licenses/package/source.name
                    target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(source,target)
    nsis_license = args.nsis.parent/'COPYING'
    if nsis_license.exists(): shutil.copy2(nsis_license, licenses/'NSIS-COPYING.txt')
    forbidden = ('Qt6Charts','Qt6Graphs','Qt6DataVisualization','Qt6WebEngine','Qt6VirtualKeyboard')
    unwanted = [p.name for p in payload.rglob('*.dll') if p.name.startswith(forbidden)]
    if unwanted: raise RuntimeError('Unneeded Qt modules were collected: '+', '.join(unwanted))
    manifest = {'application':'MultiDiskSearch','version':VERSION,
                'python':sys.version.split()[0], 'PySide6':importlib.metadata.version('PySide6'),
                'files':[{'path':p.relative_to(payload).as_posix(),'bytes':p.stat().st_size,
                          'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in sorted(payload.rglob('*')) if p.is_file()]}
    (payload/'payload-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    setup = output/f'MultiDiskSearch-{VERSION}-Setup.exe'
    subprocess.run([str(args.nsis), '/V2', f'/DAPP_VERSION={VERSION}', f'/DPAYLOAD={payload}',
                    f'/DOUTPUT={setup}', str(ROOT/'packaging/installer.nsi')], check=True, cwd=ROOT, env=environment)
    digest = hashlib.sha256(setup.read_bytes()).hexdigest()
    Path(str(setup)+'.sha256').write_text(f'{digest}  {setup.name}\n',encoding='ascii')
    print(json.dumps({'installer':str(setup),'bytes':setup.stat().st_size,'sha256':digest}))


if __name__ == '__main__':
    main()
