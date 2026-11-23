"""Opt-in real Resolve screenshot fixture. Requires an empty starting project."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import uuid
import socket
import secrets
from resolve_bridge import Session, valid_auth

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'qa-artifacts/showcase'
state = {}


def prepare(resolve):
    manager = resolve.GetProjectManager()
    previous = manager.GetCurrentProject()
    if previous and (previous.GetTimelineCount() or previous.GetMediaPool().GetRootFolder().GetClipList() or previous.GetMediaPool().GetRootFolder().GetSubFolderList()):
        raise RuntimeError('Screenshot QA requires an empty starting project.')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('FFmpeg is needed to generate test footage.')
    run = BASE / uuid.uuid4().hex[:8]
    original = run / 'Originals'
    archive = run / 'Media Archive'
    cards = run / 'Camera Cards'
    missing = run / 'Unsearched Audio'
    for folder in (original, archive, cards, missing):
        folder.mkdir(parents=True)
    for name, pattern in [('Camera_A.mov', 'testsrc2=size=640x360:rate=24'), ('Camera_B.mov', 'smptebars=size=640x360:rate=24')]:
        subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', pattern, '-t', '1', '-c:v', 'dnxhd', '-profile:v', 'dnxhr_lb', '-pix_fmt', 'yuv422p', '-y', str(original / name)], check=True, timeout=30)
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', '-y', str(original / 'Ambience.wav')], check=True, timeout=10)
    name = 'MultiDiskSearch v1 QA ' + run.name
    project = manager.CreateProject(name)
    if not project:
        raise RuntimeError('Could not create screenshot project.')
    pool = project.GetMediaPool()
    clips = pool.ImportMedia([str(original / n) for n in ('Camera_A.mov', 'Camera_B.mov', 'Ambience.wav')])
    if len(clips) != 3:
        raise RuntimeError('Test footage import failed.')
    timeline = pool.CreateEmptyTimeline('Relink verification')
    items = pool.AppendToTimeline([{'mediaPoolItem': c} for c in clips])
    for n in ('Camera_A.mov', 'Camera_B.mov'):
        (original / n).rename(archive / n)
    shutil.copyfile(archive / 'Camera_B.mov', cards / 'Camera_B.mov')
    (original / 'Ambience.wav').rename(missing / 'Ambience.wav')
    settings = run / 'settings.json'
    settings.write_text(json.dumps({'roots': [str(archive), str(cards)]}), encoding='utf-8')
    state.update(project=name, previous=previous.GetName() if previous else None, settings=str(settings),
                 clips=clips, items=items, ids=[c.GetMediaId() for c in clips], run=run)
    return {'test_project':name, 'clips':len(clips), 'search_locations':2}


def launch(resolve):
    installed = Path(os.environ['PROGRAMDATA']) / 'Blackmagic Design/DaVinci Resolve/Support/Workflow Integration Plugins/MultiDiskSearch.py'
    source = installed.read_text(encoding='utf-8-sig')
    def work():
        previous = os.environ.get('MDS_SETTINGS_PATH')
        os.environ['MDS_SETTINGS_PATH'] = state['settings']
        try:
            exec(compile(source, str(installed), 'exec'), {'resolve': resolve})
        finally:
            if previous is None:
                os.environ.pop('MDS_SETTINGS_PATH', None)
            else:
                os.environ['MDS_SETTINGS_PATH'] = previous
    thread = threading.Thread(target=work, daemon=True)
    state['thread'] = thread
    thread.start()
    return {'installed_launcher_started':True}


def verify(resolve):
    assert resolve.GetProjectManager().GetCurrentProject().GetName() == state['project']
    paths = [c.GetClipProperty('File Path') for c in state['clips']]
    ids = [c.GetMediaId() for c in state['clips']]
    timeline_ids = [i.GetMediaPoolItem().GetMediaId() for i in state['items']]
    assert ids == state['ids'] and timeline_ids == ids
    return {'media_identity_preserved':True, 'accessible_sources':sum(Path(p).is_file() for p in paths), 'clips':len(paths)}


def start_capture_bridge(resolve):
    """Expose the production Session to a desktop Qt process for screenshots."""
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    token = secrets.token_hex(32)
    session = Session(resolve)
    connection_file = state['run'] / 'capture-connection.json'
    connection_file.write_text(json.dumps({'port':listener.getsockname()[1], 'token':token, 'settings':state['settings']}), encoding='utf-8')
    def work():
        with listener:
            connection, _ = listener.accept()
            with connection, connection.makefile('rwb') as stream:
                if not valid_auth(stream.readline(65536), token):
                    return
                while True:
                    line = stream.readline(1048576)
                    if not line:
                        break
                    try:
                        response = {'result':session.request(json.loads(line))}
                    except Exception as error:
                        response = {'error':str(error)}
                    stream.write((json.dumps(response) + '\n').encode())
                    stream.flush()
        connection_file.unlink(missing_ok=True)
    thread = threading.Thread(target=work, daemon=True)
    state['thread'] = thread
    thread.start()
    return {'connection_file':str(connection_file)}


def cleanup(resolve):
    thread = state.get('thread')
    if thread and thread.is_alive():
        raise RuntimeError('Close the screenshot plugin window before cleanup.')
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject()
    if project and project.GetName() == state['project']:
        manager.CloseProject(project)
    deleted = manager.DeleteProject(state['project'])
    restored = manager.LoadProject(state['previous']) if state.get('previous') else None
    if not restored and state.get('previous'):
        restored = manager.CreateProject(state['previous'])
    return {'temporary_project_deleted':deleted, 'empty_starting_project_open':bool(restored)}
