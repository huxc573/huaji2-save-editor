$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $dir
$csc = 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe'
$log = Join-Path $dir '_build_log.txt'
"csc = $csc" | Out-File -LiteralPath $log -Encoding utf8
& $csc /nologo /platform:x86 /optimize+ /out:"$dir\xjprobe32.exe" "$dir\xjprobe32.cs" *>&1 |
    Out-File -LiteralPath $log -Encoding utf8 -Append
"exit = $LASTEXITCODE" | Out-File -LiteralPath $log -Encoding utf8 -Append
"exists = $(Test-Path -LiteralPath "$dir\xjprobe32.exe")" | Out-File -LiteralPath $log -Encoding utf8 -Append
