$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$game = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $here)))
$log = Join-Path $here '_out_crypt.txt'
"game = $game" | Out-File -LiteralPath $log -Encoding utf8
Set-Location -LiteralPath $game
& (Join-Path $here 'xjhost32.exe') crypt (Join-Path $game 'System\main.dll') `
    (Join-Path $game 'save.rvdata2') (Join-Path $here '_crypt_result.bin') *>&1 |
    Out-File -LiteralPath $log -Encoding utf8 -Append
"exit = $LASTEXITCODE" | Out-File -LiteralPath $log -Encoding utf8 -Append
