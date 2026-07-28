' JARVIS AI Assistant - Silent Startup Launcher
'
' Launches the Electron desktop app with NO visible console window.
' The Electron app handles spawning and managing the Python backend.
'
' Architecture:
'   Windows Boot → VBScript (hidden) → Electron → spawns Python Backend
'
' This avoids duplicate backend processes on port 8000.
'
' ============================================================================

Option Explicit

Dim shell, electronExe, desktopDir, projectRoot, fso

' Get filesystem object for path resolution
Set fso = CreateObject("Scripting.FileSystemObject")

' Determine project root (where this script is located)
projectRoot = fso.GetParentFolderName(WScript.ScriptFullName)
projectRoot = fso.GetParentFolderName(projectRoot) ' Go up from scripts/ to root

Set shell = CreateObject("WScript.Shell")

' ── Find Electron Executable ───────────────────────────────────────────────

desktopDir = projectRoot & "\desktop"

' Try common locations for Electron binary
Dim electronPaths, i, electronExePath
electronPaths = Array( _
    desktopDir & "\node_modules\electron\dist\electron.exe", _
    desktopDir & "\node_modules\.bin\electron.cmd", _
    projectRoot & "\node_modules\.bin\electron.cmd", _
    "npx electron " & desktopDir _
)

electronExePath = ""
For i = 0 To UBound(electronPaths)
    If fso.FileExists(electronPaths(i)) Then
        electronExePath = electronPaths(i)
        Exit For
    End If
Next

' ── Launch Electron (Hidden, no console window) ────────────────────────────
' Window style: 0 = Hidden, False = don't wait for process to exit

If electronExePath <> "" Then
    shell.Run chr(34) & electronExePath & chr(34) & " " & chr(34) & desktopDir & chr(34), 0, False
Else
    ' Fallback: try via npx which will use the package.json electron dependency
    ' The cmd /c prefix ensures no window stays open after execution
    shell.Run "cmd /c cd /d " & chr(34) & desktopDir & chr(34) & " && npx electron .", 0, False
End If

Set shell = Nothing
Set fso = Nothing
