$ErrorActionPreference = 'Continue'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $dir
$csc = 'C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe'
$log = Join-Path $dir '_build_host_log.txt'
"csc = $csc" | Out-File -LiteralPath $log -Encoding utf8
& $csc /nologo /platform:x86 /optimize+ /out:"$dir\xjhost32.exe" "$dir\xjhost32.cs" *>&1 |
    Out-File -LiteralPath $log -Encoding utf8 -Append
"exit = $LASTEXITCODE" | Out-File -LiteralPath $log -Encoding utf8 -Append
"exists = $(Test-Path -LiteralPath "$dir\xjhost32.exe")" | Out-File -LiteralPath $log -Encoding utf8 -Append
