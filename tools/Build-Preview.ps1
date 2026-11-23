$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$versionText = Get-Content -LiteralPath (Join-Path $projectRoot 'version.py') -Raw
$packageVersion = [regex]::Match($versionText, '"([^"]+)"').Groups[1].Value
if (-not $packageVersion) { throw 'Package version missing.' }
$files = @('MultiDiskSearch.py', 'relink_core.py', 'resolve_bridge.py', 'qt_app.py', 'Main.qml', 'Theme.qml', 'ActionButton.qml', 'qmldir', 'requirements.txt', 'Install.ps1', 'Uninstall.ps1', 'README.md', 'version.py', 'docs', 'assets')
foreach ($file in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $file))) { throw "Missing package file: $file" }
}
$destination = Join-Path $projectRoot 'dist'
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$archive = Join-Path $destination "MultiDiskSearch-$packageVersion-windows-source.zip"
Compress-Archive -LiteralPath ($files | ForEach-Object { Join-Path $projectRoot $_ }) -DestinationPath $archive -Force
Get-FileHash -LiteralPath $archive -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $([IO.Path]::GetFileName($archive))" } | Set-Content -LiteralPath "$archive.sha256" -Encoding ascii
Write-Host "Created source package: $archive"
