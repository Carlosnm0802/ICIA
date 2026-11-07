Option Explicit
Dim fso, shell, base, pythonw, exe
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
base = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = base
pythonw = base & "\.venv\Scripts\pythonw.exe"
exe = base & "\ICIA.exe"
If fso.FileExists(pythonw) Then
  shell.Run """" & pythonw & """ -m app.launcher", 0, False
ElseIf fso.FileExists(exe) Then
  shell.Run """" & exe & """", 0, False
Else
  MsgBox "No se encontro ICIA. Verifica que la carpeta este completa.", 16, "ICIA"
End If
