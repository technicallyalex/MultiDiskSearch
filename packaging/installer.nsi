Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"

!ifndef APP_VERSION
!define APP_VERSION "1.0.0"
!endif
!ifndef PAYLOAD
!error "PAYLOAD must point to the bundled application"
!endif
!ifndef OUTPUT
!error "OUTPUT must name the setup executable"
!endif

Name "Multi Disk Search"
OutFile "${OUTPUT}"
InstallDir "$PROGRAMFILES64\Multi Disk Search"
InstallDirRegKey HKLM "Software\MultiDiskSearch" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "Multi Disk Search"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "FileDescription" "Multi Disk Search Setup"
VIAddVersionKey "LegalCopyright" "Multi Disk Search"
!define MUI_ICON "${PAYLOAD}\app.ico"
!define MUI_UNICON "${PAYLOAD}\app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Multi Disk Search ${APP_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT "Install Multi Disk Search for DaVinci Resolve Studio.$\r$\n$\r$\nClose the plugin window before continuing. Restart Resolve after setup to refresh its Workflow Integrations menu."
!define MUI_FINISHPAGE_TEXT "Multi Disk Search is installed.$\r$\n$\r$\nRestart Resolve Studio, open a project, and choose Workspace > Workflow Integrations > MultiDiskSearch."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
    ${IfNot} ${AtLeastWin10}
        MessageBox MB_ICONSTOP "Multi Disk Search requires Windows 10 or later."
        Abort
    ${EndIf}
    ${IfNot} ${RunningX64}
        MessageBox MB_ICONSTOP "Multi Disk Search requires 64-bit Windows."
        Abort
    ${EndIf}
    SetRegView 64
    SetShellVarContext all
FunctionEnd

Function un.onInit
    SetRegView 64
    ReadRegStr $1 HKLM "Software\MultiDiskSearch" "InstallDir"
    GetFullPathName $0 "$INSTDIR"
    GetFullPathName $1 "$1"
    ${If} $0 != $1
        MessageBox MB_ICONSTOP "The installation folder could not be verified."
        Abort
    ${EndIf}
    IfFileExists "$INSTDIR\payload-manifest.json" +3
        MessageBox MB_ICONSTOP "The application manifest is missing."
        Abort
FunctionEnd

Section "Multi Disk Search" Main
    SetOutPath "$INSTDIR"
    File /r "${PAYLOAD}\*"
    DetailPrint "Registering Multi Disk Search with Resolve Studio..."
    ClearErrors
    ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\Register-Plugin.ps1" -Action Install -ApplicationDirectory "$INSTDIR"' $0
    ${If} ${Errors}
    ${OrIf} $0 != 0
        MessageBox MB_ICONSTOP "Resolve registration failed. Setup requires permission to write the Workflow Integration folder."
        SetErrorLevel 1
        Abort
    ${EndIf}
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateDirectory "$SMPROGRAMS\Multi Disk Search"
    CreateShortcut "$SMPROGRAMS\Multi Disk Search\Multi Disk Search.lnk" "$INSTDIR\MultiDiskSearch.exe"
    CreateShortcut "$SMPROGRAMS\Multi Disk Search\User Guide.lnk" "$INSTDIR\USER_GUIDE.txt"
    CreateShortcut "$SMPROGRAMS\Multi Disk Search\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    WriteRegStr HKLM "Software\MultiDiskSearch" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "DisplayName" "Multi Disk Search"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "DisplayVersion" "${APP_VERSION}"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "Publisher" "technicallyalex"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "DisplayIcon" "$INSTDIR\MultiDiskSearch.exe"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "UninstallString" '"$INSTDIR\Uninstall.exe"'
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "NoModify" 1
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "NoRepair" 1
SectionEnd

Section "Uninstall"
    SetRegView 64
    SetShellVarContext all
    ClearErrors
    ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\Register-Plugin.ps1" -Action Uninstall -ApplicationDirectory "$INSTDIR"' $0
    ${If} ${Errors}
    ${OrIf} $0 != 0
        MessageBox MB_ICONSTOP "Could not unregister Multi Disk Search from Resolve."
        Abort
    ${EndIf}
    ; Remove only the installed application's own tree, never user settings/media.
    RMDir /r "$INSTDIR\_internal"
    Delete "$INSTDIR\MultiDiskSearch.exe"
    Delete "$INSTDIR\MultiDiskSearch.py"
    Delete "$INSTDIR\resolve_bridge.py"
    Delete "$INSTDIR\relink_core.py"
    Delete "$INSTDIR\Register-Plugin.ps1"
    Delete "$INSTDIR\VERSION.txt"
    Delete "$INSTDIR\USER_GUIDE.txt"
    Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
    Delete "$INSTDIR\app.ico"
    Delete "$INSTDIR\payload-manifest.json"
    RMDir /r "$INSTDIR\licenses"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
    Delete "$SMPROGRAMS\Multi Disk Search\Multi Disk Search.lnk"
    Delete "$SMPROGRAMS\Multi Disk Search\User Guide.lnk"
    Delete "$SMPROGRAMS\Multi Disk Search\Uninstall.lnk"
    RMDir "$SMPROGRAMS\Multi Disk Search"
    DeleteRegKey HKLM "Software\MultiDiskSearch"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch"
SectionEnd
