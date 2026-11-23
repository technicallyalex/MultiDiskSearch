param(
    [Parameter(Mandatory=$true)][ValidateSet('Install','Uninstall')][string]$Action,
    [Parameter(Mandatory=$true)][string]$ApplicationDirectory
)
$ErrorActionPreference = 'Stop'
$ApplicationDirectory = [IO.Path]::GetFullPath($ApplicationDirectory)
$destination = Join-Path $env:PROGRAMDATA 'Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins'
$launcherPath = Join-Path $destination 'MultiDiskSearch.py'
$configPath = Join-Path $destination 'MultiDiskSearch.json'
if ($Action -eq 'Uninstall') {
    if (Test-Path -LiteralPath $configPath) {
        $owner = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if ([IO.Path]::GetFullPath($owner.directory) -eq $ApplicationDirectory) {
            if (Test-Path -LiteralPath $launcherPath) { Remove-Item -LiteralPath $launcherPath }
            Remove-Item -LiteralPath $configPath
        }
    }
    exit 0
}
foreach ($name in @('MultiDiskSearch.exe','MultiDiskSearch.py','resolve_bridge.py','relink_core.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $ApplicationDirectory $name))) { throw "Required application file missing: $name" }
}
$source = Get-Content -LiteralPath (Join-Path $ApplicationDirectory 'MultiDiskSearch.py') -Raw
$marker = 'INSTALL_DIRECTORY = None  # Set by installer.'
if (-not $source.Contains($marker)) { throw 'Application launcher is invalid.' }
$source = $source.Replace($marker, ('INSTALL_DIRECTORY = ' + ($ApplicationDirectory | ConvertTo-Json -Compress)))
New-Item -ItemType Directory -Force -Path $destination | Out-Null
[IO.File]::WriteAllText($launcherPath, $source, (New-Object System.Text.UTF8Encoding($false)))
$version = Get-Content -LiteralPath (Join-Path $ApplicationDirectory 'VERSION.txt') -Raw
@{directory=$ApplicationDirectory;version=$version.Trim()} | ConvertTo-Json | Set-Content -LiteralPath $configPath -Encoding utf8
