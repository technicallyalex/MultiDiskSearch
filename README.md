# Multi Disk Search
**A powerful alternative to DaVinci Resolve's built-in media relinking tool.**

Find and reconnect missing footage across multiple saved drives and folders in one search.

![Multi Disk Search with saved search locations and media results](docs/images/main-window.png)

*Interface shown with example media.*

## Go beyond folder-by-folder relinking

Resolve's built-in **Relink Selected Clips** workflow starts with a search location. When footage is scattered across separate disks and folders, searching location by location adds manual work. **Multi Disk Search searches a saved list of locations together**, then puts matches, duplicate candidates and missing files in one review window.

Resolve also offers a deep disk search; see Blackmagic Design's [relinking guide](https://documents.blackmagicdesign.com/UserManuals/DaVinci-Resolve-20-Beginners-Guide.pdf).

## Features

- Recursive searches across saved disks and folders, with recognizable location names.
- Automatic filename matching that skips media already accessible to Resolve.
- Batch relinking through Resolve's native media-pool API, with result checks and retries.
- Duplicate-source selection, thumbnails, path search and status filters.
- Progress indicators, clip counts and a resizable Qt Quick interface.
- Automatic exclusion of protected system folders, recycle bins and directory links.
- Local processing with no footage uploads.

## Installation

### Requirements

- 64-bit Windows 10 or Windows 11.
- DaVinci Resolve **Studio 21.2** is the supported baseline.
- Connected, readable disks or folders containing the footage you want to find.

### Install

1. Run **MultiDiskSearch-1.0.0-Setup.exe**.
2. Follow the setup wizard and approve the Windows administrator prompt when requested.
3. Restart DaVinci Resolve Studio.
The installer includes the runtime and registers the integration. **No separate Python installation or package downloads are required.**

## Using Multi Disk Search in Resolve

1. **Open your project** in DaVinci Resolve Studio.
2. **Launch the tool from Resolve's top menu:** **Workspace > Workflow Integrations > MultiDiskSearch**.
3. **Add search locations.** In **Search Locations**, click **+ Add disk or folder** for each media disk or folder. Your choices are saved for future sessions.
4. **Run the search.** Click **Find missing media**. The tool checks the project's media and searches your saved locations, including subfolders.
5. **Review the results.** In **Missing Media**, inspect the original and found paths. Use the text and status filters to narrow the list. For duplicate filenames, click **Sources**, select the correct file and click **Use selected source**.
6. **Relink and save.** Click the **Relink** button at the top right; its label shows how many matches are ready. Check the results, then save your project in Resolve.

Launch through Resolve, rather than the Windows Start menu, to connect the tool to your open project.

## Matching and thumbnails

Matching uses the original **filename and extension**, ignoring case. It does not compare footage contents, duration or timecode. Review sources carefully when cameras reuse filenames.

If a location cannot be searched, source selection becomes manual because that location may contain additional duplicates. Reconnect the disk or correct its access permissions and search again for a complete result.

Thumbnails come from Resolve where available. An optional locally installed FFmpeg can also generate previews of found sources; FFmpeg is not bundled or required for relinking. Some media may display a placeholder when a preview is unavailable.

Automatic matching does not cover renamed footage, image-sequence patterns, spanned camera packages or advanced synced-media/subclip workflows.

## Troubleshooting and support

- **The integration is missing from Resolve's menu:** finish installation, restart Resolve Studio and check **Workspace > Workflow Integrations**.
- **Footage is not found:** check that the correct disks are connected, the folders are readable and the filenames still match the original media.

Report bugs and request features through [GitHub Issues](https://github.com/technicallyalex/MultiDiskSearch/issues). Include the app version, Windows and Resolve versions, what happened and any relevant error message. Review logs for private paths before sharing them.

| File | Location |
| --- | --- |
| Saved search locations | `%APPDATA%\MultiDiskSearch\settings.json` |
| Startup log | `%APPDATA%\MultiDiskSearch\qt.log` |

## Uninstall

Open **Windows Settings > Apps > Installed apps > Multi Disk Search > Uninstall**. Saved search locations, Resolve projects and media are preserved.

## Documentation

- [User guide](docs/USER_GUIDE.txt)
- [Version 1.0.0 release notes](docs/RELEASE_NOTES.md)
- [Validation and compatibility scope](docs/QA_REPORT.md)
- [Building from source](docs/BUILD.md)
- [Third-party components and license notices](packaging/THIRD_PARTY_NOTICES.md)

Multi Disk Search is an independent application and is not affiliated with or endorsed by Blackmagic Design. DaVinci Resolve is a trademark of Blackmagic Design.
