"""Multi-disk relinker. Run from Resolve's Workspace > Scripts > Utility."""
import json
import ntpath
import os
from pathlib import Path
import queue
import sys
import threading


def linked_directory(path):
    return os.path.islink(path) or getattr(os.path, 'isjunction', os.path.islink)(path)


EXCLUDED_DIRS = frozenset(name.casefold() for name in (
    'System Volume Information', '$RECYCLE.BIN', 'RECYCLER', 'Recovery',
    '$WinREAgent', '$Windows.~BT', '$Windows.~WS', 'Windows',
    'Program Files', 'Program Files (x86)', 'ProgramData',
    'Documents and Settings', 'Config.Msi', 'MSOCache',
    'EFI', 'Boot', '$Extend', '$WINDOWS.~TMP',
))


def protected_location(path):
    return any(part.casefold() in EXCLUDED_DIRS for part in ntpath.normpath(path).split(ntpath.sep))


def location_name(path):
    """Use Windows volume labels for disks and leaf names for folders."""
    normalized = ntpath.normpath(path)
    drive, tail = ntpath.splitdrive(normalized)
    if drive and tail in ('', '\\'):
        if os.name == 'nt':
            try:
                import ctypes
                label = ctypes.create_unicode_buffer(261)
                if ctypes.windll.kernel32.GetVolumeInformationW(drive + '\\', label, len(label), None, None, None, None, 0):
                    return label.value or 'Local disk'
            except (OSError, AttributeError):
                pass
        return 'Disk ' + drive
    return ntpath.basename(normalized) or normalized


def filename(path):
    return ntpath.basename(path).casefold()


def scan(roots, names, cancel, progress=lambda _: None, counts=lambda done, total: None):
    """Search once for all wanted names; never follow directory junctions."""
    matches = {name: set() for name in names}
    errors = []
    seen = set()
    count = 0
    inventory = []
    progress('Discovering searchable folders…')
    for root in roots:
        if protected_location(root) or linked_directory(root):
            continue
        if not os.path.isdir(root):
            errors.append('Unavailable: ' + root)
            continue
        def onerror(error):
            errors.append(str(error))
        for directory, dirs, files in os.walk(root, onerror=onerror, followlinks=False):
            if cancel.is_set():
                return matches, errors, True
            dirs[:] = [d for d in dirs if d.casefold() not in EXCLUDED_DIRS
                       and not os.path.islink(os.path.join(directory, d))
                       and not getattr(os.path, 'isjunction', os.path.islink)(os.path.join(directory, d))]
            key = os.path.normcase(os.path.abspath(directory))
            if key in seen:
                dirs[:] = []
                continue
            seen.add(key)
            count += 1
            inventory.append(directory)
            if count % 200 == 0:
                progress('Discovering: ' + directory)
    total = len(inventory)
    counts(0, total)
    for done, directory in enumerate(inventory, 1):
        if cancel.is_set():
            counts(done - 1, total)
            return matches, errors, True
        if linked_directory(directory):
            errors.append('Location changed to a link during search: ' + directory)
            counts(done, total)
            continue
        try:
            with os.scandir(directory) as entries:
                files = [entry.name for entry in entries if not entry.is_symlink() and entry.is_file(follow_symlinks=False)]
            for name in files:
                folded = name.casefold()
                if folded in matches:
                    matches[folded].add(os.path.abspath(os.path.join(directory, name)))
        except OSError as error:
            errors.append(str(error))
        if done % 25 == 0 or done == total:
            counts(done, total)
    return matches, errors, False


def collect(folder):
    yield from (folder.GetClipList() or [])
    for child in folder.GetSubFolderList() or []:
        yield from collect(child)


def connect():
    existing = globals().get('resolve')
    if existing:
        return existing
    modules = Path(os.environ.get('PROGRAMDATA', 'C:/ProgramData')) / 'Blackmagic Design/DaVinci Resolve/Support/Developer/Scripting/Modules'
    sys.path.insert(0, str(modules))
    import DaVinciResolveScript
    return DaVinciResolveScript.scriptapp('Resolve')
