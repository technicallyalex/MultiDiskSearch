"""Opt-in Resolve test using generated media only; never run on a working project."""
import json
from pathlib import Path
import shutil
import threading
import uuid
import subprocess
from relink_core import scan
from resolve_bridge import Session


def run(resolve):
    manager = resolve.GetProjectManager()
    previous = manager.GetCurrentProject()
    if previous and (previous.GetTimelineCount() or previous.GetMediaPool().GetRootFolder().GetClipList() or previous.GetMediaPool().GetRootFolder().GetSubFolderList()):
        raise RuntimeError('Live QA requires an empty current project to avoid disturbing work.')
    base = Path(__file__).resolve().parents[1] / 'qa-artifacts/live'
    fixture = base / 'original/QA_RELINK.mov'
    if not fixture.exists():
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise RuntimeError('FFmpeg is required to generate the disposable QA fixture.')
        fixture.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                        'testsrc2=size=640x360:rate=24', '-t', '1', '-c:v', 'dnxhd',
                        '-profile:v', 'dnxhr_lb', '-pix_fmt', 'yuv422p', '-y', str(fixture)],
                       check=True, timeout=30)
    run_id = uuid.uuid4().hex[:10]
    directory = base / run_id
    source = directory / 'original/QA_RELINK.mov'
    target = directory / 'archive/QA_RELINK.mov'
    source.parent.mkdir(parents=True)
    target.parent.mkdir(parents=True)
    shutil.copyfile(fixture, source)
    name = 'MultiDiskSearch QA ' + run_id
    test = manager.CreateProject(name)
    if not test:
        raise RuntimeError('Could not create QA project.')
    report = {'resolve': resolve.GetVersionString(), 'test_project': name}
    try:
        pool = test.GetMediaPool()
        clips = pool.ImportMedia([str(source)])
        if not clips:
            raise RuntimeError('Generated media could not be imported.')
        clip = clips[0]
        media_id = clip.GetMediaId()
        timeline = pool.CreateEmptyTimeline('Relink verification')
        items = pool.AppendToTimeline([{'mediaPoolItem':clip}])
        if not timeline or not items:
            raise RuntimeError('Could not create QA timeline.')
        source.rename(target)
        session = Session(resolve)
        rows = session.request({'command':'inventory'})
        row = next(r for r in rows if r['old'] == str(source))
        matches, errors, stopped = scan([str(target.parent)], {'qa_relink.mov'}, threading.Event())
        assert not errors and not stopped and len(matches['qa_relink.mov']) == 1
        session.request({'command':'relink', 'key':row['key'], 'target':str(target)})
        assert clip.GetMediaId() == media_id
        assert items[0].GetMediaPoolItem().GetMediaId() == media_id
        assert Path(clip.GetClipProperty('File Path')) == target
        preview = session.request({'command':'thumbnail', 'key':row['key']})
        report.update(relinked=True, timeline_media_identity_preserved=True, thumbnail_available=bool(preview))
        if preview:
            import base64
            (base / 'verified-thumbnail.jpg').write_bytes(base64.b64decode(preview.split(',', 1)[1]))
    finally:
        restored = manager.LoadProject(previous.GetName()) if previous else None
        report['previous_project_restored'] = bool(restored)
        if restored:
            report['qa_project_deleted'] = manager.DeleteProject(name)
        else:
            manager.CloseProject(test)
            report['qa_project_deleted'] = manager.DeleteProject(name)
            if previous:
                report['empty_starting_project_recreated'] = bool(manager.CreateProject(previous.GetName()))
        (base / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report
