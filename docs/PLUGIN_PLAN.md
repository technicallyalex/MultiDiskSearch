> Historical architecture investigation. The current installer now defaults to Workflow Integration; see README.md and QA_REPORT.md for current behavior.

# Multi Disk Search: supported plugin path

Decision brief, 23 November 2026. Current shipping code remains a Windows Qt Quick tool with a Python launcher. No Electron implementation is included in this preview.

## What Resolve supports

Blackmagic's installed Resolve 21.2 developer package documents two Workflow Integration forms: an Electron plugin with a manifest and JavaScript API, and a Python/Lua integration script that may use a third-party GUI. Both launch from Workspace > Workflow Integrations. The documented Electron UI is a separate window; docking into Resolve is not promised. OpenFX is for image effects and is not an appropriate relinking integration.

Primary references inspected:

- Local SDK: `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Workflow Integrations\README.txt`, especially Overview, Loading Workflow Integration Plugin, Supported platforms, and Sample Workflow Integration Script.
- Bundled `Examples/SamplePlugin` and `Examples/SamplePromisePlugin`: manifests, sandboxed main/preload process separation, native bridge, and promise APIs.
- [Blackmagic's Studio feature page](https://www.blackmagicdesign.com/products/davinciresolve/studio) confirms Workflow Integration support for asset-management and automation tools.

The local README has an older header date despite being shipped with 21.2. Verify each intended Resolve/platform combination live before advertising compatibility. It documents Electron plugins on Windows and macOS, and scripts on Windows/macOS/Linux. This application itself is Windows-only today.

## Options

| Route | UI and packaging | Effort / tradeoff |
| --- | --- | --- |
| Workflow Integration script + Qt Quick | Keep our QML styling, components, and backend. Package a private GUI executable/runtime and a small integration launcher. | Recommended next step: preserves the requested Qt Quick interface and most tested code. Retains a local host/GUI bridge. |
| Electron Workflow Integration | Native manifest, Resolve's JavaScript bridge, HTML/CSS component system, isolated renderer and preload APIs. | Appropriate if we choose a full UI rewrite. Removes the Python GUI dependency, but needs a JS scanner, matching tests, thumbnail strategy, lifecycle handling, and native-module/platform validation. |
| Existing Scripts menu tool | Current Qt Quick interface, developer Python runtime. | Useful internal preview, but not a self-contained public plugin installer. |

## Recommended release sequence

1. Keep this preview internal while testing the corrected relink behavior and UI.
2. Validate the supplied `Install.ps1 -Target WorkflowIntegration` option on Resolve Studio. It installs the supported Python integration-script form into the documented machine-wide plugin directory. This requires write access to ProgramData and a Resolve restart. Menu registration is not yet validated in this QA pass.
3. Package the Qt Quick frontend as a self-contained Windows application (evaluate `pyside6-deploy` or PyInstaller in a separate packaging change). Resolve should provide its API object to the launcher; users should not have to enable external scripting or install Python packages manually.
4. Install application files into a stable application directory, add an uninstaller, sign the installer, and test clean install/update/uninstall under a standard Windows account. Preserve saved locations across updates.
5. Choose the product license and prepare PySide6/Qt and any bundled codec notices. Do not redistribute Blackmagic's SDK binaries without checking its distribution terms. FFmpeg is optional and currently discovered locally, not bundled.
6. Approve a Windows beta only after the release gates in QA_REPORT.md pass. Add macOS only after an actual macOS build and QA pass.

If we choose Electron later, load Resolve's native bridge in the main process, keep context isolation and sandboxing enabled in the renderer, expose only narrow validated commands through preload, deny navigation/remote content, and perform disk enumeration away from the UI thread. Port the same match ambiguity and incomplete-search rules. Follow the current SDK samples rather than legacy `nodeIntegration` examples.

## Boundaries

This pass investigates the supported architecture and adds an opt-in integration-script installer target. It does not claim an Electron plugin exists, that the new menu entry was tested, or that the source ZIP is a ready public release. The theme and reusable QML controls are owned by the application; they do not depend on modifying Resolve's own UI.
