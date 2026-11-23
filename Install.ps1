param([ValidateSet('WorkflowIntegration')][string]$Target = 'WorkflowIntegration')
$ErrorActionPreference = 'Stop'
$runtime = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtime)) {
    python -m venv (Join-Path $PSScriptRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the private Python runtime.' }
}
& $runtime -c 'import PySide6.QtQuick'
if ($LASTEXITCODE -ne 0) {
    & $runtime -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Could not install Qt Quick.' }
}
$destination = Join-Path $env:PROGRAMDATA 'Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins'
New-Item -ItemType Directory -Path $destination -Force | Out-Null
$launcher = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'MultiDiskSearch.py') -Raw
$marker = 'INSTALL_DIRECTORY = None  # Set by installer.'
if (-not $launcher.Contains($marker)) { throw 'Launcher install marker is missing.' }
$launcher = $launcher.Replace($marker, ('INSTALL_DIRECTORY = ' + ($PSScriptRoot | ConvertTo-Json -Compress)))
[IO.File]::WriteAllText((Join-Path $destination 'MultiDiskSearch.py'), $launcher, (New-Object System.Text.UTF8Encoding($false)))
@{ directory = $PSScriptRoot } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'MultiDiskSearch.json') -Encoding utf8
$legacyLocations = @(
    (Join-Path $env:APPDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility'),
    (Join-Path $env:PROGRAMDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility')
)
foreach ($legacy in $legacyLocations) {
    $legacyConfig = Join-Path $legacy 'MultiDiskSearch.json'
    if (Test-Path -LiteralPath $legacyConfig) {
        $owner = Get-Content -LiteralPath $legacyConfig -Raw | ConvertFrom-Json
        if ([IO.Path]::GetFullPath($owner.directory) -eq [IO.Path]::GetFullPath($PSScriptRoot)) {
            $oldLauncher = Join-Path $legacy 'MultiDiskSearch.py'
            if (Test-Path -LiteralPath $oldLauncher) { Remove-Item -LiteralPath $oldLauncher }
            Remove-Item -LiteralPath $legacyConfig
            Write-Host 'Removed obsolete Scripts-menu launcher.'
        } else {
            Write-Warning "An older launcher belongs to another folder: $legacyConfig"
        }
    }
}
Write-Host 'Installed MultiDiskSearch. Use Workspace > Workflow Integrations > MultiDiskSearch. Restart Resolve to refresh menu entries.'
