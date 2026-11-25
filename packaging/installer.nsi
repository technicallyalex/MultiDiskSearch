Unicode true
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!include "FileFunc.nsh"

!ifndef APP_VERSION
!define APP_VERSION "1.1.0"
!endif
!ifndef PAYLOAD
!error "PAYLOAD must point to the bundled application"
!endif
!ifndef OUTPUT
!error "OUTPUT must name the setup executable"
!endif

Name "MultiDiskSearch"
OutFile "${OUTPUT}"
InstallDir "$PROGRAMFILES64\MultiDiskSearch"
InstallDirRegKey HKLM "Software\MultiDiskSearch" "InstallDir"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey "ProductName" "MultiDiskSearch"
VIAddVersionKey "ProductVersion" "${APP_VERSION}"
VIAddVersionKey "FileVersion" "${APP_VERSION}"
VIAddVersionKey "FileDescription" "MultiDiskSearch Setup"
VIAddVersionKey "LegalCopyright" "MultiDiskSearch"
!define MUI_ICON "${PAYLOAD}\app.ico"
!define MUI_UNICON "${PAYLOAD}\app.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "MultiDiskSearch ${APP_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT "Install MultiDiskSearch for DaVinci Resolve Studio.$\r$\n$\r$\nClose the plugin window before continuing. Restart Resolve after setup to refresh its Workflow Integrations menu."
!define MUI_FINISHPAGE_TEXT "MultiDiskSearch is installed.$\r$\n$\r$\nRestart Resolve Studio, open a project, and choose Workspace > Workflow Integrations > MultiDiskSearch."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
    ${IfNot} ${AtLeastWin10}
        MessageBox MB_ICONSTOP "MultiDiskSearch requires Windows 10 or later."
        Abort
    ${EndIf}
    ${IfNot} ${RunningX64}
        MessageBox MB_ICONSTOP "MultiDiskSearch requires 64-bit Windows."
        Abort
    ${EndIf}
    SetRegView 64
    SetShellVarContext all
    ${GetParameters} $0
    ClearErrors
    ${GetOptions} $0 "/UPDATEPID=" $2
    ${IfNot} ${Errors}
        Call WaitForUpdateExit
    ${EndIf}
FunctionEnd

Function WaitForUpdateExit
    ReadRegStr $INSTDIR HKLM "Software\MultiDiskSearch" "InstallDir"
    IfFileExists "$INSTDIR\MultiDiskSearch.exe" +3
        MessageBox MB_ICONSTOP "Setup could not find the existing MultiDiskSearch installation."
        Abort
    ${If} $2 <= 0
        SetErrorLevel 1
        Abort
    ${EndIf}
    System::Call 'kernel32::OpenProcess(i 0x00100000, i 0, i r2) p.r3 ?e'
    Pop $4
    ${If} $3 P<> 0
        System::Call 'kernel32::WaitForSingleObject(p r3, i 60000) i.r4'
        System::Call 'kernel32::CloseHandle(p r3)'
    ${ElseIf} $4 == 87
        ; The frontend may have exited before setup initialized.
        StrCpy $4 0
    ${EndIf}
    ${If} $4 == 0
        ; A second running frontend must not cause a partly overwritten install.
        StrCpy $5 "$INSTDIR\MultiDiskSearch.exe"
        System::Call 'kernel32::CreateFileW(w r5, i 0x40000000, i 0, p 0, i 3, i 0x80, p 0) p.r3'
        ${If} $3 P<> -1
            System::Call 'kernel32::CloseHandle(p r3)'
            Return
        ${EndIf}
    ${EndIf}
    MessageBox MB_ICONSTOP "MultiDiskSearch is still open or setup could not access it. Close all MultiDiskSearch windows and try again."
    SetErrorLevel 1
    Abort
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

Section "MultiDiskSearch" Main
    SetOutPath "$INSTDIR"
    File /r "${PAYLOAD}\*"
    DetailPrint "Registering MultiDiskSearch with Resolve Studio..."
    ClearErrors
    ExecWait '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\Register-Plugin.ps1" -Action Install -ApplicationDirectory "$INSTDIR"' $0
    ${If} ${Errors}
    ${OrIf} $0 != 0
        MessageBox MB_ICONSTOP "Resolve registration failed. Setup requires permission to write the Workflow Integration folder."
        SetErrorLevel 1
        Abort
    ${EndIf}
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    CreateDirectory "$SMPROGRAMS\MultiDiskSearch"
    CreateShortcut "$SMPROGRAMS\MultiDiskSearch\MultiDiskSearch.lnk" "$INSTDIR\MultiDiskSearch.exe"
    CreateShortcut "$SMPROGRAMS\MultiDiskSearch\User Guide.lnk" "$INSTDIR\USER_GUIDE.txt"
    CreateShortcut "$SMPROGRAMS\MultiDiskSearch\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    ; Remove the previous installer-created shortcuts when upgrading in place.
    Delete "$SMPROGRAMS\Multi Disk Search\Multi Disk Search.lnk"
    Delete "$SMPROGRAMS\Multi Disk Search\User Guide.lnk"
    Delete "$SMPROGRAMS\Multi Disk Search\Uninstall.lnk"
    RMDir "$SMPROGRAMS\Multi Disk Search"
    WriteRegStr HKLM "Software\MultiDiskSearch" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch" "DisplayName" "MultiDiskSearch"
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
        MessageBox MB_ICONSTOP "Could not unregister MultiDiskSearch from Resolve."
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
    Delete "$SMPROGRAMS\MultiDiskSearch\MultiDiskSearch.lnk"
    Delete "$SMPROGRAMS\MultiDiskSearch\User Guide.lnk"
    Delete "$SMPROGRAMS\MultiDiskSearch\Uninstall.lnk"
    RMDir "$SMPROGRAMS\MultiDiskSearch"
    DeleteRegKey HKLM "Software\MultiDiskSearch"
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\MultiDiskSearch"
SectionEnd
