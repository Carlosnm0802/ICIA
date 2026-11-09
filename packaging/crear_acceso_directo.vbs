Option Explicit

Dim fso, shell, base, iniciar, icono

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

base = fso.GetParentFolderName(WScript.ScriptFullName)
iniciar = base & "\iniciar_icia.vbs"
icono = base & "\ICIA.exe"

If Not fso.FileExists(iniciar) Then
  MsgBox "No se encontro iniciar_icia.vbs en " & base, 16, "ICIA"
  WScript.Quit 1
End If

If Not fso.FileExists(icono) Then
  icono = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
End If

CrearAcceso shell.SpecialFolders("Desktop") & "\ICIA.lnk"
CrearAcceso shell.SpecialFolders("Programs") & "\ICIA.lnk"

MsgBox "Acceso directo de ICIA creado en el Escritorio y el Menu Inicio.", 64, "ICIA"
WScript.Quit 0

Sub CrearAcceso(destino)
  Dim acceso
  Set acceso = shell.CreateShortcut(destino)
  acceso.TargetPath = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\wscript.exe"
  acceso.Arguments = "//nologo """ & iniciar & """"
  acceso.WorkingDirectory = base
  acceso.IconLocation = icono & ",0"
  acceso.Description = "ICIA - Sistema de gestion para escuela de Robotica e Ingles"
  acceso.WindowStyle = 1
  acceso.Save
End Sub
