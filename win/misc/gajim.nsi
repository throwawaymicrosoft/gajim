﻿; File encoding 'UTF-8 with BOM'

Unicode true
!include "MUI2.nsh"

Name "Gajim"
OutFile "Gajim.exe"
SetCompressor /final /solid lzma
SetCompressorDictSize 32

!define myAppName "Gajim"

InstallDir "$PROGRAMFILES\Gajim"
InstallDirRegKey HKCU "Software\Gajim" ""
RequestExecutionLevel admin

Var StartMenuFolder

!define MUI_ICON "${NSISDIR}\Contrib\Graphics\Icons\orange-install.ico"
!define MUI_UNICON "${NSISDIR}\Contrib\Graphics\Icons\orange-uninstall.ico"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_BITMAP "..\misc\nsis_header.bmp"
!define MUI_WELCOMEFINISHPAGE_BITMAP "..\misc\nsis_wizard.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "..\misc\nsis_wizard.bmp"
;!define MUI_COMPONENTSPAGE_CHECKBITMAP "${NSISDIR}\Contrib\Graphics\Checks\colorful.bmp"
!define MUI_COMPONENTSPAGE_SMALLDESC
!define MUI_ABORTWARNING

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\COPYING"
!insertmacro MUI_PAGE_COMPONENTS
!insertmacro MUI_PAGE_DIRECTORY
!define MUI_STARTMENUPAGE_REGISTRY_ROOT "HKCU"
!define MUI_STARTMENUPAGE_REGISTRY_KEY "Software\Gajim"
!define MUI_STARTMENUPAGE_REGISTRY_VALUENAME "Start Menu Folder"
!insertmacro MUI_PAGE_STARTMENU Application $StartMenuFolder
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\bin\Gajim.exe"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;Show all languages, despite user's codepage
!define MUI_LANGDLL_ALLLANGUAGES

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "French"
!insertmacro MUI_LANGUAGE "German"
!insertmacro MUI_LANGUAGE "Italian"
!insertmacro MUI_LANGUAGE "Russian"
!insertmacro MUI_LANGUAGE "Hebrew"
!insertmacro MUI_RESERVEFILE_LANGDLL

; English
LangString NAME_Emoticons ${LANG_ENGLISH} "Emoticons"
LangString NAME_Iconsets ${LANG_ENGLISH} "Iconsets"
LangString NAME_Languages ${LANG_ENGLISH} "Languages"
LangString NAME_SecLanguagesOther ${LANG_ENGLISH} "Other"
LangString NAME_Themes ${LANG_ENGLISH} "Themes"
LangString NAME_SecDesktopIcon ${LANG_ENGLISH} "Create icon on desktop"
LangString NAME_SecAutostart ${LANG_ENGLISH} "Start Gajim when Windows starts"
LangString DESC_SecGajim ${LANG_ENGLISH} "Installs the main Gajim files."
LangString DESC_SecDesktopIcon ${LANG_ENGLISH} "If set, a shortcut for Gajim will be created on the desktop."
LangString DESC_SecAutostart ${LANG_ENGLISH} "If set, Gajim will be automatically started when Windows starts."
LangString STR_Installed ${LANG_ENGLISH} "Apparently, Gajim is already installed. Uninstall it?"
LangString STR_Running ${LANG_ENGLISH} "It appears that Gajim is currently running.$\n\
		Please quit Gajim and restart the uninstaller."

; French
LangString NAME_Emoticons ${LANG_FRENCH} "Emoticônes"
LangString NAME_Iconsets ${LANG_FRENCH} "Bibliothèque d'icônes"
LangString NAME_Languages ${LANG_FRENCH} "Langues"
LangString NAME_SecLanguagesOther ${LANG_FRENCH} "Autre"
LangString NAME_Themes ${LANG_FRENCH} "Thèmes"
LangString NAME_SecDesktopIcon ${LANG_FRENCH} "Créer une icône sur le bureau"
LangString NAME_SecAutostart ${LANG_FRENCH} "Lancer Gajim au démarrage de Windows"
LangString DESC_SecGajim ${LANG_FRENCH} "Installer les fichiers principaux de Gajim."
LangString DESC_SecDesktopIcon ${LANG_FRENCH} "Si selectionné, un raccourci pour Gajim sera créé sur le bureau."
LangString DESC_SecAutostart ${LANG_FRENCH} "Si activé, Gajim sera automatiquement lancé au démarrage de Windows."
LangString STR_Installed ${LANG_FRENCH} "Gajim est apparement déjà installé. Lancer la désinstallation ?"
LangString STR_Running ${LANG_FRENCH} "Gajim est apparament lancé.$\n\
		Fermez-le et redémarrez le désinstallateur."

; German
LangString NAME_Emoticons ${LANG_GERMAN} "Emoticons"
LangString NAME_Iconsets ${LANG_GERMAN} "Symbolsets"
LangString NAME_Languages ${LANG_GERMAN} "Sprachen"
LangString NAME_SecLanguagesOther ${LANG_GERMAN} "Sonstige"
LangString NAME_Themes ${LANG_GERMAN} "Designs"
LangString NAME_SecDesktopIcon ${LANG_GERMAN} "Desktop-Icon erstellen"
LangString NAME_SecAutostart ${LANG_GERMAN} "Gajim mit Windows starten"
LangString DESC_SecGajim ${LANG_GERMAN} "Installiert die Hauptdateien von Gajim."
LangString DESC_SecDesktopIcon ${LANG_GERMAN} "Wenn dies aktiviert wird, wird ein Icon für Gajim auf dem Desktop erstellt."
LangString DESC_SecAutostart ${LANG_GERMAN} "Gajim wird automatisch gestartet, sowie Windows startet, wenn dies aktivier wird."
LangString STR_Installed ${LANG_GERMAN} "Gajim is apparently already installed. Uninstall it?"
LangString STR_Running ${LANG_GERMAN} "Es scheint, dass Gajim bereits läuft.$\n\
		Bitte beenden Sie es und starten Sie den Installer erneut.."

; Italian
LangString NAME_Emoticons ${LANG_ITALIAN} "Emoticons"
LangString NAME_Iconsets ${LANG_ITALIAN} "Set di icone"
LangString NAME_Languages ${LANG_ITALIAN} "Lingue"
LangString NAME_SecLanguagesOther ${LANG_ITALIAN} "Altre"
LangString NAME_Themes ${LANG_ITALIAN} "Temi"
LangString NAME_SecDesktopIcon ${LANG_ITALIAN} "Crea un'icona sul desktop"
LangString NAME_SecAutostart ${LANG_ITALIAN} "Lancia Gajim quando parte Windows"
LangString DESC_SecGajim ${LANG_ITALIAN} "Installa i file principali di Gajim."
LangString DESC_SecDesktopIcon ${LANG_ITALIAN} "Se selezionato, un'icona verrà creata sul desktop."
LangString DESC_SecAutostart ${LANG_ITALIAN} "Se selezionato, Gajim sarà eseguito all'avvio di Windows."
LangString STR_Installed ${LANG_ITALIAN} "Gajim is apparently already installed. Uninstall it?"
LangString STR_Running ${LANG_ITALIAN} "It appears that Gajim is currently running.$\n\
		Close it and restart uninstaller."

; Russian
LangString NAME_Emoticons ${LANG_RUSSIAN} "Смайлики"
LangString NAME_Iconsets ${LANG_RUSSIAN} "Темы иконок"
LangString NAME_Languages ${LANG_RUSSIAN} "Языки"
LangString NAME_SecLanguagesOther ${LANG_RUSSIAN} "Другое"
LangString NAME_Themes ${LANG_RUSSIAN} "Темы"
LangString NAME_SecDesktopIcon ${LANG_RUSSIAN} "Создать я лык на абочем столе"
LangString NAME_SecAutostart ${LANG_RUSSIAN} "Запускать Gajim при загрузке Windows"
LangString DESC_SecGajim ${LANG_RUSSIAN} "Установка основных файлов Gajim."
LangString DESC_SecDesktopIcon ${LANG_RUSSIAN} "Если отмечено, на рабочем столе будет создан ярлык Gajim."
LangString DESC_SecAutostart ${LANG_RUSSIAN} "Если отмечено, Gajim будет автоматически запускаться при загрузке Windows."
LangString STR_Installed ${LANG_RUSSIAN} "Похоже, Gajim уже установлен. Деинсталлировать установленную версию?"
LangString STR_Running ${LANG_RUSSIAN} "Похоже, Gajim уже запущен.$\n\
		Закройте его и запустите деинсталлятор снова."

; Hebrew
LangString NAME_Emoticons ${LANG_HEBREW} "רגשונים"
LangString NAME_Iconsets ${LANG_HEBREW} "מערכי צלמית"
LangString NAME_Languages ${LANG_HEBREW} "שפות"
LangString NAME_SecLanguagesOther ${LANG_HEBREW} "אחרות"
LangString NAME_Themes ${LANG_HEBREW} "ערכאות נושא"
LangString NAME_SecDesktopIcon ${LANG_HEBREW} "צור סמל בשולחן עבודה"
LangString NAME_SecAutostart ${LANG_HEBREW} "הפעל את Gajim כאשר Windows מתחיל"
LangString DESC_SecGajim ${LANG_HEBREW} "מתקין קבצי Gajim עיקריים."
LangString DESC_SecDesktopIcon ${LANG_HEBREW} "במידה ונקבעת, קיצור דרך עבור Gajim יושם על שולחן העבודה."
LangString DESC_SecAutostart ${LANG_HEBREW} "במידה ונקבעת, Gajim יופעל אוטומטית כאשר Windows מתחיל."
LangString STR_Installed ${LANG_HEBREW} "כפי הנראה, Gajim כבר מותקן. להסיר אותו?"
LangString STR_Running ${LANG_HEBREW} "נראה שהתוכנית Gajim מורצת כעת.$\n\
        אנא צא מן Gajim ואתחל את מסיר ההתקנה."

Section "Gajim" SecGajim
	SectionIn RO
	
    Var /GLOBAL arch_name
    StrCpy $arch_name "(64-Bit)"
    StrCmp ${ARCH} "mingw64" cont
    StrCpy $arch_name "(32-Bit)"
    cont:
	
	SetOutPath "$INSTDIR"
	File /r "${ARCH}\*.*"

	WriteRegStr HKCU "Software\Gajim" "" $INSTDIR
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "DisplayName" "Gajim ${VERSION} $arch_name"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "UninstallString" "$INSTDIR\Uninstall.exe"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "DisplayIcon" "$INSTDIR\bin\Gajim.exe"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "DisplayVersion" "${VERSION}"
	WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "URLInfoAbout" "https://www.gajim.org/"
	WriteUninstaller "$INSTDIR\Uninstall.exe"

	SetOutPath "$INSTDIR\bin"
	!insertmacro MUI_STARTMENU_WRITE_BEGIN Application
		SetShellVarContext current
		CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
		SetShellVarContext all
		CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
		CreateShortCut "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
	!insertmacro MUI_STARTMENU_WRITE_END

SectionEnd

Section $(NAME_SecDesktopIcon) SecDesktopIcon
	SetShellVarContext current
	SetOutPath "$INSTDIR\bin"
	CreateShortCut "$DESKTOP\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
SectionEnd

Section $(NAME_SecAutostart) SecAutostart
	SetShellVarContext current
	SetOutPath "$INSTDIR\bin"
	CreateShortCut "$SMSTARTUP\Gajim.lnk" "$INSTDIR\bin\Gajim.exe"
SectionEnd

Section "Uninstall"
	RMDir /r "$INSTDIR"

	!insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder

	SetShellVarContext current
	Delete "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk"
	Delete "$SMPROGRAMS\$StartMenuFolder\Change Theme.lnk"
	RMDir "$SMPROGRAMS\$StartMenuFolder"
	Delete "$DESKTOP\Gajim.lnk"
	Delete "$SMSTARTUP\Gajim.lnk"
	SetShellVarContext all
	Delete "$SMPROGRAMS\$StartMenuFolder\Gajim.lnk"
	Delete "$SMPROGRAMS\$StartMenuFolder\Change Theme.lnk"
	RMDir "$SMPROGRAMS\$StartMenuFolder"

	DeleteRegKey /ifempty HKCU "Software\Gajim"
	DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Gajim"
SectionEnd

!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
	!insertmacro MUI_DESCRIPTION_TEXT ${SecGajim} $(DESC_SecGajim)
	!insertmacro MUI_DESCRIPTION_TEXT ${SecDesktopIcon} $(DESC_SecDesktopIcon)
	!insertmacro MUI_DESCRIPTION_TEXT ${SecAutostart} $(DESC_SecAutostart)
!insertmacro MUI_FUNCTION_DESCRIPTION_END

Function un.onInit
;	Check that Gajim is not running before uninstalling
	FindWindow $0 "gdkWindowToplevel" "Gajim"
	StrCmp $0 0 Remove
	MessageBox MB_ICONSTOP|MB_OK $(STR_Running)
	Quit
Remove:
	!insertmacro MUI_UNGETLANGUAGE
FunctionEnd

Function .onInit
	BringToFront
;	Check if already running
;	If so don't open another but bring to front
	System::Call "kernel32::CreateMutexA(i 0, i 0, t '$(^Name)') i .r0 ?e"
	Pop $0
	StrCmp $0 0 launch
	StrLen $0 "$(^Name)"
	IntOp $0 $0 + 1
	FindWindow $1 '#32770' '' 0 $1
	IntCmp $1 0 +3
	System::Call "user32::ShowWindow(i r1,i 9) i."         ; If minimized then maximize
	System::Call "user32::SetForegroundWindow(i r1) i."    ; Bring to front
	Abort

launch:
;	Check to see if old install (inno setup) is already installed
	ReadRegStr $R0 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Gajim_is1" "UninstallString"
;	remove first and last " char
	StrLen $0 $R0
	IntOp $0 $0 - 2
	strcpy $1 $R0 $0 1
	IfFileExists $1 +1 NotInstalled
	MessageBox MB_YESNO|MB_DEFBUTTON2|MB_TOPMOST $(STR_Installed) IDNO Quit
	StrCmp $R1 2 Quit +1
	ExecWait '$R0 _?=$INSTDIR' $R2
	StrCmp $R2 0 +1 Quit

NotInstalled:	
;	Check to see if new installer (NSIS)already installed
	ReadRegStr $R3 HKLM "SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Gajim" "UninstallString"
	IfFileExists $R3 +1 ReallyNotInstalled
	MessageBox MB_YESNO|MB_DEFBUTTON2|MB_TOPMOST $(STR_Installed) IDNO Quit
	StrCmp $R4 2 Quit +1
	ExecWait '$R3 _?=$INSTDIR' $R5
	StrCmp $R5 0 ReallyNotInstalled Quit
Quit:
	Quit
 
ReallyNotInstalled:
	!insertmacro MUI_LANGDLL_DISPLAY
FunctionEnd
