# v1.0.0 — current build baseline

- Established the current Windows Workflow Integration build as version 1.0.0.
- Includes the Qt Quick interface, approved rounded MDS identity, saved search locations, recursive media search, source review, thumbnails, filters and native relinking.
- Included clearly labeled UI preview screenshots. Real running-plugin capture remains pending after Computer Use was stopped.
- Replaced the approximate logo redraw with transparent SVG outlines traced from the approved rounded mark and wordmark, with the shadow-S gradient. No cropped presentation background is used.
- Source package installation requires Python and a first-time PySide6 download. See QA_REPORT.md for tested coverage and remaining limits; the version number does not imply untested platforms or workflows are supported.

# 0.2.1-preview — installation and project cleanup

- Workflow Integration is the single default installation; owned obsolete Scripts-menu launchers are removed during installation.
- Kept the approved logo, gradient-shadow S, window icon and blue interface.
- Organized regression tests, QA tooling, documentation and design explorations into dedicated folders.
- Removed generated caches, raw test footage and the obsolete 0.2.0 preview archive after verification.
- Saved search locations and the private runtime are preserved.
- 18 automated checks pass. Live UI interaction was stopped with Escape; no new live startup/menu verification is claimed.

# 0.2.0 preview — Windows internal review

Not a public release or standalone binary. Requires Python 3.10+ and an internet connection for the first PySide6 installation. Extract to a stable folder, run Install.ps1, and keep that folder in place.

- Refreshed Qt Quick interface with shared theme tokens and reusable buttons.
- Applied the rounded blue MDS mark with gradient-shadow S to the header and window icon; included scalable brand assets and matching blue accents.
- Added clip/path search, status filters, summary counts, and clearer empty states.
- Kept the resizable full-height disk and media panels and thumbnail rows.
- Prevented progress updates from resetting the list models.
- Incomplete disk coverage now requires explicit source review; a lone result is not automatically considered unique when search errors occurred.
- Failed relinks retain their target for retry.
- Improved cancellation counts, settings recovery, root-junction handling, and file-link exclusions.
- Added an opt-in Workflow Integration script installation target and an ownership-checked launcher uninstaller.

Validated: automated tests, offscreen Windows QML renders at 1480×900 and 1000×620, plus a live generated-footage relink and thumbnail check in Resolve Studio 21.2.0.6.

Not yet validated: clean-machine install, native Workflow Integrations menu registration, DPI scaling, large production projects, network disconnect/reconnect, macOS, or Linux. See QA_REPORT.md for release gates and PLUGIN_PLAN.md for architecture options.
