# Version 1.0.0 validation

Platform: Windows x64. Resolve API baseline: DaVinci Resolve Studio 21.2.0.6.

## Automated coverage

20 passing regression checks cover launcher execution in Resolve's integration context, bundled-runtime selection, recursive scanning, duplicates, unavailable locations, protected folders, cancellation counts, project-switch protection, target verification, retries, saved-settings validation, filtering, progress, logo rendering and QML loading at normal and compact sizes.

The packaged executable is checked independently for QML/plugin loading, window-icon rendering and startup without an external Python installation. Installer registration is checked for a valid absolute application path and ownership-safe removal. Saved settings and media are outside the uninstall targets.

## Compatibility scope

Windows x64 is the launch platform. Automatic matching is filename/extension based. Image sequences, renamed footage, spanned camera packages and advanced synced-media/subclip workflows are not covered. Production-scale NAS behavior, high-DPI/multi-monitor layouts and broad camera-format compatibility require additional testing. Interface preview images are not presented as evidence of a live relink.

## Package results

- Windows setup executable compiled successfully with no compiler warnings.
- Bundled executable starts, loads its QML interface and SVG icon, and renders without QML warnings.
- The same check passes after relocation into a folder containing spaces, with Python removed from PATH.
- Resolve registration and version/path metadata pass. Removal protects registrations belonging to another application directory.
- Original Resolve registration and saved search settings were preserved during validation.
- Payload hashes, setup SHA-256 and executable version resources are verified.
- The elevated setup wizard itself has not been run end-to-end under an administrator account here. Full interactive installed-plugin and clean-machine checks remain separate from the payload checks above.
