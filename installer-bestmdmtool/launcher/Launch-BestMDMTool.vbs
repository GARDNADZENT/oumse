Option Explicit

Dim fso, shell, launcherDir, appDir, ps1
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

launcherDir = fso.GetParentFolderName(WScript.ScriptFullName)
appDir = fso.GetParentFolderName(launcherDir)
ps1 = fso.BuildPath(launcherDir, "Start-BestMDMTool.ps1")

shell.CurrentDirectory = appDir
shell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File """ & ps1 & """", 0, False
