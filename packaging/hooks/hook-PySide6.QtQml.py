"""Collect only QML modules used by this application (PyInstaller 6.22.3)."""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
root = Path(pyside6_library_info.location['QmlImportsPath'])
allowed = {
    'QtQml', 'QtQml/Models', 'QtQml/WorkerScript', 'QtCore',
    'QtQuick', 'QtQuick/Window', 'QtQuick/Layouts', 'QtQuick/Templates',
    'QtQuick/Controls', 'QtQuick/Controls/impl', 'QtQuick/Controls/Basic',
    'QtQuick/Controls/Basic/impl', 'QtQuick/Dialogs', 'QtQuick/Dialogs/quickimpl',
    'QtQuick/Effects', 'Qt/labs/folderlistmodel', 'Qt/labs/platform',
}
for module in sorted(root.rglob('qmldir')):
    relative = module.parent.relative_to(root).as_posix()
    if relative not in allowed:
        continue
    plugin_binaries, plugin_datas = pyside6_library_info._process_qml_plugin(module)
    for source in plugin_binaries:
        binaries.append((str(source), str(Path('PySide6/qml') / source.parent.relative_to(root))))
    for source in plugin_datas:
        destination = source.relative_to(root) if source.is_dir() else source.parent.relative_to(root)
        datas.append((str(source), str(Path('PySide6/qml') / destination)))
