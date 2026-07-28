' JARVIS AI Assistant - Silent Backend Launcher
' ============================================
' This script launches the Python backend completely hidden.
' No console window, no PowerShell window, no CMD window.
'
' Derives paths relative to its own location so it works from any install path.
' Installed to Windows startup via:
'   HKCU\Software\Microsoft\Windows\CurrentVersion\Run

Dim fso, shell, scriptDir, pythonExe, scriptPath, command

' Get the directory where this script is located
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Determine paths relative to script location
' Script is in: <JarvisRoot>\scripts\start_backend_hidden.vbs
' Backend is in: <JarvisRoot>\backend\main.py
pythonExe = "python"
scriptPath = fso.BuildPath(fso.BuildPath(scriptDir, ".."), "backend\main.py")

' Build command
command = chr(34) & pythonExe & chr(34) & " " & chr(34) & scriptPath & chr(34)

' Create shell object and launch hidden
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = fso.GetParentFolderName(scriptPath)
shell.Run command, 0, False

' Clean up
Set shell = Nothing
Set fso = Nothing
