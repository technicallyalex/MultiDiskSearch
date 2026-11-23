param([ValidateSet('Scripts', 'WorkflowIntegration')][string]$Target = 'WorkflowIntegration')
$ErrorActionPreference = 'Stop'
$destination = if ($Target -eq 'WorkflowIntegration') {
    Join-Path $env:PROGRAMDATA 'Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins'
} else {
    Join-Path $env:APPDATA 'Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility'
}
$config = Join-Path $destination 'MultiDiskSearch.json'
if (-not (Test-Path -LiteralPath $config)) { throw 'No MultiDiskSearch installation was found here.' }
$installed = Get-Content -LiteralPath $config -Raw | ConvertFrom-Json
if ([IO.Path]::GetFullPath($installed.directory) -ne [IO.Path]::GetFullPath($PSScriptRoot)) {
    throw 'This launcher belongs to another installation. Run its own uninstaller.'
}
Remove-Item -LiteralPath (Join-Path $destination 'MultiDiskSearch.py') -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $config
Write-Host 'Removed the launcher. Saved locations and project media were kept.'
