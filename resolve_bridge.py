"""Resolve objects stay on the Scripts-menu thread; Qt runs separately."""
import json
import os
import secrets
import socket
import subprocess
from pathlib import Path
from relink_core import collect, filename


def valid_auth(payload, expected):
    try:
        value = json.loads(payload).get('token')
        return isinstance(value, str) and secrets.compare_digest(value, expected)
    except (ValueError, AttributeError, TypeError):
        return False


class Session:
    def __init__(self, resolve):
        self.resolve = resolve
        self.project = None
        self.clips = {}

    def request(self, message):
        command = message['command']
        current = self.resolve.GetProjectManager().GetCurrentProject()
        if not current:
            raise RuntimeError('Open a Resolve project first.')
        if command == 'inventory':
            self.project = current
            self.clips = {}
            rows = []
            for clip in collect(current.GetMediaPool().GetRootFolder()):
                props = clip.GetClipProperty() or {}
                path = props.get('File Path', '')
                if not path or os.path.isfile(path):
                    continue
                key = str(len(rows))
                self.clips[key] = (clip, path)
                rows.append(dict(key=key, name=props.get('Clip Name') or filename(path), old=path,
                                 target='', status='Searching', thumbnail='', previewLabel='No preview available'))
            return rows
        if not self.project or current.GetUniqueId() != self.project.GetUniqueId():
            raise RuntimeError('Project changed. Find missing media again.')
        clip, original = self.clips[message['key']]
        if command == 'thumbnail':
            # Export does not move the playhead or import replacement footage.
            try:
                method = getattr(clip, 'ExportFrame', None)
                result = method(0, {'outputType': 'encodedString', 'encodedImageFormat': 'jpg', 'maxDimension': 320}) if callable(method) else {}
                if result and result.get('success') and result.get('data'):
                    return 'data:image/jpeg;base64,' + result['data']
            except Exception:
                pass
            return ''
        if command == 'relink':
            target = message['target']
            if filename(target) != filename(original) or not os.path.isfile(target):
                raise RuntimeError('Matching source is no longer available.')
            if clip.GetClipProperty('File Path') != original:
                raise RuntimeError('Source changed. Search again.')
            ok = current.GetMediaPool().RelinkClips([clip], os.path.dirname(target))
            actual = clip.GetClipProperty('File Path')
            if not ok or os.path.normcase(os.path.abspath(actual)) != os.path.normcase(os.path.abspath(target)):
                raise RuntimeError('Resolve did not confirm the target.')
            return True
        raise ValueError('Unknown command')


def serve(resolve, directory):
    directory = Path(directory)
    runtime = directory / '.venv/Scripts/pythonw.exe'
    if not runtime.exists():
        raise RuntimeError('Qt runtime missing. Run Install.ps1 again.')
    session = Session(resolve)
    token = secrets.token_hex(32)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(0.5)
        env = os.environ.copy()
        env['MDS_TOKEN'] = token
        for key in ('QT_PLUGIN_PATH', 'QT_QPA_PLATFORM_PLUGIN_PATH', 'QML2_IMPORT_PATH', 'PYTHONHOME', 'PYTHONPATH'):
            env.pop(key, None)
        logdir = Path(os.environ['APPDATA']) / 'MultiDiskSearch'
        logdir.mkdir(parents=True, exist_ok=True)
        with (logdir / 'qt.log').open('w', encoding='utf-8') as log:
            process = subprocess.Popen([str(runtime), str(directory / 'qt_app.py'), str(listener.getsockname()[1])], env=env, stdout=log, stderr=log)
            while process.poll() is None:
                try:
                    connection, _ = listener.accept()
                except socket.timeout:
                    continue
                with connection:
                    connection.settimeout(5)
                    stream = connection.makefile('rwb')
                    try:
                        first = stream.readline(65536)
                    except OSError:
                        stream.close()
                        continue
                    if not valid_auth(first, token):
                        stream.close()
                        continue
                    connection.settimeout(None)
                    while process.poll() is None:
                        line = stream.readline(1048576)
                        if not line:
                            break
                        try:
                            response = {'result': session.request(json.loads(line))}
                        except Exception as error:
                            response = {'error': str(error)}
                        stream.write((json.dumps(response) + '\n').encode())
                        stream.flush()
                    stream.close()
            if process.returncode:
                raise RuntimeError('Qt Quick could not start. See ' + str(logdir / 'qt.log'))
