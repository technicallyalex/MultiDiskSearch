# Multi Disk Search
**A powerful alternative to DaVinci Resolve's built-in media relinking tool.**

Find missing footage across multiple drives and directories in one search. Multi Disk Search automatically searches your saved locations, finds matching files and lets you reconnect them to your project together—saving you from repeating the search for each disk or folder.

![Multi Disk Search with saved search locations and media results](docs/images/main-window.png)

*Interface shown with example media.*

## Go beyond folder-by-folder relinking

Resolve's built-in **Relink Selected Clips** workflow asks you to point it to a search location. When footage is scattered across separate drives and folders, that means more browsing, more searches and more manual work to bring a project back online.

**Multi Disk Search gives you a reusable search list spanning multiple drives and directories.** Add your media locations once, then search them together whenever you open a project with missing footage. Automatic matching, duplicate-source selection, thumbnails and status filters put the search and review process in one place.

| Your relinking workflow | With Multi Disk Search |
| --- | --- |
| Footage is spread across several disks | Search all configured disks and folders in one operation |
| You repeatedly browse to the same media locations | Save named locations and reuse them across projects |
| Several files have the same camera filename | Review the candidate paths and choose the correct source |
| You need to see what is ready to reconnect | Filter matches, duplicates and missing files in a dedicated results view |

Resolve also provides a deep disk search. Multi Disk Search's advantage is its saved, explicit set of search locations and unified review workflow. See Blackmagic Design's [relinking guide](https://documents.blackmagicdesign.com/UserManuals/DaVinci-Resolve-20-Beginners-Guide.pdf) for the built-in workflow.

## Features

- **Search multiple locations together.** Add entire media disks or individual folders and search their subfolders automatically.
- **Set up once, reuse across projects.** Saved locations retain recognizable disk labels and folder names, ready for your next relink.
- **Find matching footage automatically.** Search for the project's missing filenames together instead of locating each clip individually. Media that is already accessible is skipped.
- **Relink matches in a batch.** Reconnect found footage through Resolve's native media-pool relinking, with results checked after each relink and failed targets available for retry.
- **Choose between duplicate files.** Review candidate paths with **Sources** when several files share the same name.
- **Review media visually.** Thumbnails, original paths, source paths, text search and status filters help you inspect the results.
- **Track real progress.** See the active search location, clip counts and completed work. Folder discovery stays indeterminate until a meaningful total is available.
- **Keep searches focused on media.** Protected system folders, recycle bins and directory links are excluded automatically.
- **Work locally.** Your footage stays on your computer. No media uploads are required.
- **Use a dedicated Qt Quick interface.** Resizable panels give your search locations and missing media room to work alongside Resolve.

## Installation

### Requirements

- 64-bit Windows 10 or Windows 11.
- DaVinci Resolve **Studio 21.2** is the supported baseline.
- Connected, readable disks or folders containing the footage you want to find.

### Install and launch

1. Run **MultiDiskSearch-1.0.0-Setup.exe**.
2. Follow the setup wizard and approve the Windows administrator prompt when requested.
3. Restart DaVinci Resolve Studio.
4. Open your project, then choose **Workspace > Workflow Integrations > MultiDiskSearch**.

The installer includes the application runtime and registers the Workflow Integration. **No separate Python installation or package downloads are required.** You do not need to keep the source project folder after installation.

Launch Multi Disk Search from Resolve to connect it to your project. Opening it from the Windows Start menu displays launch instructions.

## Quick start

1. **Add your locations.** Choose the media disks and folders you want to search. Locations are saved automatically.
2. **Find missing media.** Click **Find missing media** to inspect your project's media and search all configured locations.
3. **Review the results.** Use thumbnails and filters to inspect found footage. Choose **Sources** to resolve duplicate filenames.
4. **Reconnect your footage.** Click **Relink matches**, check the results and save your project in Resolve.

## Matching and thumbnails

Matching uses the original **filename and extension**, ignoring case. It does not compare footage contents, duration or timecode. Review sources carefully when cameras reuse filenames.

If a location cannot be searched, source selection becomes manual because that location may contain additional duplicates. Reconnect the disk or correct its access permissions and search again for a complete result.

Thumbnails come from Resolve where available. An optional locally installed FFmpeg can also generate previews of found sources; FFmpeg is not bundled or required for relinking. Some media may display a placeholder when a preview is unavailable.

Automatic matching does not cover renamed footage, image-sequence patterns, spanned camera packages or advanced synced-media/subclip workflows.

## Troubleshooting and support

- **The integration is missing from Resolve's menu:** finish installation, restart Resolve Studio and check **Workspace > Workflow Integrations**.
- **The app asks you to open it through Resolve:** launch it from the Workflow Integrations menu with a project open.
- **Footage is not found:** check that the correct disks are connected, the folders are readable and the filenames still match the original media.
- **A preview is unavailable:** relinking can still work without a thumbnail. Optional FFmpeg support may provide previews for additional found files.

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
