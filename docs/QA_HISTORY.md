# Multi Disk Search QA — 23 November 2026

Status: improved internal Windows preview; **not approved for public release**.

## Evidence

- 18 automated tests pass under the private Python/PySide6 runtime. Coverage includes multi-root scanning, duplicates, protected directories, unavailable disks, cancellation counts, project-switch rejection, native relink verification, malformed settings, filter row identity, retry targets, incomplete coverage, asynchronous preview/relink progress, and QML loading without warnings.
- Offscreen UI renders reviewed at 1480×900 and the 1000×620 minimum. Screenshots: `gui-preview.png` and `qa-artifacts/ui-minimum.png`. The screenshots use representative test rows, not an inventory of the user's project.
- Live Resolve Studio **21.2.0.6**: generated a one-second DNxHR clip, imported it into a temporary project and timeline, moved it into a new folder, searched and relinked through Session, then checked the original media ID and timeline reference. All passed. Resolve thumbnail export also passed.
- Temporary QA project deleted. Starting project was an empty Untitled Project; Resolve could not reload that unsaved project by name, so an empty Untitled Project was reopened afterward. No working project was edited.
- Generated QA media, thumbnail, and machine-readable live report remain under `qa-artifacts/live/`. The live report records the initial restore attempt; this document records the subsequent empty-project restoration.

## Defects corrected

| Finding | Fix |
| --- | --- |
| Failed relink discarded its source target | Keep the target available for retry. |
| Unreadable/offline search roots could hide duplicates | Suppress automatic targets when any search error exists; require source review. |
| Progress refreshed entire list models | Separate result/location notifications from progress/state notifications. Thumbnail updates still refresh result snapshots; a targeted list model remains a scale improvement. |
| Root junctions and linked files could escape configured folders | Exclude explicit linked roots and file symlinks; recheck directory links before scanning. |
| Cancellation could show stale counts below 25 folders | Emit actual completed count on stop. |
| Malformed saved configuration could crash or partly load | Validate shape and paths, show recoverable error. |
| Result filtering could use the wrong source row | Carry original row index through filtered results. |
| One preview API failure could abort later previews | Fall back to placeholders and continue remaining previews. |

## Release gates still open

1. **Distribution:** build a self-contained installer instead of creating a development virtual environment on the user's machine. Test standard-user install, update, and uninstall. Optional integration installer target and new uninstaller are source-reviewed, not install/remove-tested here.
2. **Workflow Integration:** install into the documented directory, restart Studio, verify menu discovery, startup, shutdown, Resolve exit, reconnect, repeated open/close, and project switching. Current live test covers the relink backend, not the full Scripts-menu/Qt-process lifecycle.
3. **Scale and storage:** large production project, long/Unicode/UNC paths, unavailable NAS, mid-search disconnect, access denied, mounted removable volumes, and thumbnail caching/memory limits. Full media lists still refresh for individual thumbnail changes.
4. **GUI:** real desktop keyboard/focus navigation, duplicate picker and filter dropdown, 125–200% DPI, and multi-monitor placement. Offscreen renders do not establish these results.
5. **Media:** duplicates with different footage, subclips, synced audio, multicam, image sequences and spanned RAW packages. Current auto matching uses filename/extension only; it does not verify duration/timecode/content. No claim of broad camera-package support.
6. **Licensing:** choose project license, review PySide6/Qt obligations, and decide whether any optional FFmpeg binary will be bundled. No third-party binaries are included in the source ZIP.
7. **Publication:** review version, product identity, install instructions, screenshots and download checksum before authorizing a public release. No publication was performed in this pass.

## Reproduce

Run `.venv\Scripts\python.exe -m unittest -v` from the project directory. If Windows' temporary folder is restricted, point TEMP/TMP to a writable test directory first. The opt-in `qa_live_check.run(resolve)` requires generated fixture footage and an empty current Resolve project; it deliberately refuses a populated project. It is not run by unit tests or included in the preview ZIP.

## Startup correction after integration install

Resolve executed the Workflow Integration launcher without `__file__`, causing the reported startup error. The installer now embeds the application directory, and the launcher accepts Resolve-injected globals without requiring `__name__`. Both installed launchers passed exec-based checks with neither special global present, and two startup regression tests bring the suite to 18. Full visible launch remains to be confirmed in Resolve.
