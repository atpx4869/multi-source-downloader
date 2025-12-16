!include "MUI2.nsh"

Name "Standard Downloader"
OutFile "dist\Installer.exe"
InstallDir "$PROGRAMFILES\StandardDownloader"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "English"

Section "Install"
    SetOutPath "$INSTDIR"
    File /oname=app.exe "dist\app.exe"
    
    CreateDirectory "$SMPROGRAMS\Standard Downloader"
    CreateShortcut "$SMPROGRAMS\Standard Downloader\Standard Downloader.lnk" "$INSTDIR\app.exe"
    CreateShortcut "$SMPROGRAMS\Standard Downloader\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
    CreateShortcut "$DESKTOP\Standard Downloader.lnk" "$INSTDIR\app.exe"
    
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\StandardDownloader" "DisplayName" "Standard Downloader"
    WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\StandardDownloader" "UninstallString" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
    Delete "$SMPROGRAMS\Standard Downloader\Standard Downloader.lnk"
    Delete "$SMPROGRAMS\Standard Downloader\Uninstall.lnk"
    RMDir "$SMPROGRAMS\Standard Downloader"
    Delete "$DESKTOP\Standard Downloader.lnk"
    Delete "$INSTDIR\app.exe"
    Delete "$INSTDIR\Uninstall.exe"
    RMDir "$INSTDIR"
    DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\StandardDownloader"
SectionEnd
