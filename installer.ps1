# VEGAS Pro 22 (build 250) fix: instant splices/drags + capped VRAM use.
# Patches YOUR OWN copy of SfVstWrap.dll. It only applies if your file is the exact original build 250 file,
# and it only writes the result if it is byte-for-byte identical to the tested patched file. Backup + uninstall included.
param([switch]$Uninstall, [string]$TestInput, [string]$TestOutput)
$ErrorActionPreference = 'Stop'
$ORIG_DLL    = 'D1E6E50E7C826596B84C0D4938EAFBBA070101FF62C81CE831736DA00A65D9A4'
$PATCHED_DLL = '0C49259077098C476D45A19925AE9D41B6458B251414309A7FB555B2703AA80C'
$ORIG_EXE    = '46F0B64D9BEA16087596B78D4F2DD71DECEA762C03E599C989D9B717C7002ED3'
$CERT_OFFSET = 0x7E0200

$EDITS = @(
    ,@(0x146, '07')
    ,@(0x191, '90')
    ,@(0x1E9, '04')
    ,@(0x250, '6853')
    ,@(0x2A0, '44')
    ,@(0x338, '2e76666978')
    ,@(0x341, '02')
    ,@(0x345, '807e')
    ,@(0x349, '02')
    ,@(0x34D, '027e')
    ,@(0x35C, '20')
    ,@(0x35F, 'e0')
    ,@(0x51F036, 'e995660b')
    ,@(0x51F03B, '9090')
    ,@(0x51F0E9, 'e912660b00909090909090909090')
    ,@(0x51F1CD, 'e94b650b')
    ,@(0x51F1D2, '9090')
    ,@(0x51F27A, 'e9ce640b009090909090909090')
    ,@(0x5D56D0, '8b056a5b19')
    ,@(0x5D56D6, '85c07415ff159810')
    ,@(0x5D56E0, '3b055a5b19')
    ,@(0x5D56E6, '400f94c5e9399af4ffe80c1d21')
    ,@(0x5D56F4, '33d2b904')
    ,@(0x5D56FB, 'e93d99f4ff8b4424508905365b19')
    ,@(0x5D570A, 'ff156810')
    ,@(0x5D5710, '3b442450400f94c5e9da99f4ff8b051d5b19')
    ,@(0x5D5723, '85c07415ff154b10')
    ,@(0x5D572D, '3b050d5b19')
    ,@(0x5D5733, '410f94c6e97c9bf4ffe8bf1c21')
    ,@(0x5D5741, '33d2b904')
    ,@(0x5D5748, 'e9879af4ff8b45ff8905ea5a19')
    ,@(0x5D5756, 'ff151c10')
    ,@(0x5D575C, '3b45ff410f94c6e91f9bf4ff')
)
$SECTION_HEX = (@(
    '534883ec30b00186057301000084c00f85f6000000488d0dc4010000ff1526f3deff4885c00f84e00000004889c3488b833f84a50048b9488bf2488bf9488d48'
    '39c80f85c3000000488b834684a50048b98d590848895c24304839c80f85a9000000488d0d37010000ff15d9f2deff4885c00f84930000004889c1488d153e01'
    '0000ff15e8f2deff4885c00f847a000000488905f0000000488d8b3f84a500ba0f00000041b8400000004c8d4c2428ffd085c00f8452000000488d834e84a500'
    '488905c9000000488d05520000004889834584a500c6834d84a50090c7834184a5000000000066c7833f84a500ff25488d8b3f84a500ba0f000000448b442428'
    '4c8d4c242cff157d0000004883c4305bc3cccccccccccccccccccccccccccccc488bf2488bf948b80000004001000000483bf0480f47f0488d590848895c2430'
    'ff254a00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
    '00000000000000000000000000000000000000000000000000000000000000006b00650072006e0065006c00330032002e0064006c006c000000000000000000'
    '5669727475616c50726f74656374000000000000000000000000000000000000760065006700610073003200320030002e006500780065000000000000000000'
) -join '')

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Done($m, $ok) {
  if ($ok) { Say "`n[OK] $m" Green } else { Say "`n[X] $m" Red }
  if (-not $TestOutput) { Read-Host "`nPress Enter to close" | Out-Null }
  if ($ok) { exit 0 } else { exit 1 }
}
function Sha([byte[]]$b) { -join ([Security.Cryptography.SHA256]::Create().ComputeHash($b) | ForEach-Object { $_.ToString('X2') }) }
function HexToBytes([string]$h) { $r = New-Object byte[] ($h.Length / 2); for ($i = 0; $i -lt $r.Length; $i++) { $r[$i] = [Convert]::ToByte($h.Substring($i * 2, 2), 16) }; return ,$r }

function Build-Patched([byte[]]$src) {
  $b = [byte[]]$src.Clone()
  foreach ($e in $EDITS) { $bytes = HexToBytes $e[1]; [Array]::Copy($bytes, 0, $b, [int]$e[0], $bytes.Length) }
  $sect = HexToBytes $SECTION_HEX
  $out = New-Object byte[] ($b.Length + $sect.Length)
  [Array]::Copy($b, 0, $out, 0, $CERT_OFFSET)
  [Array]::Copy($sect, 0, $out, $CERT_OFFSET, $sect.Length)
  [Array]::Copy($b, $CERT_OFFSET, $out, $CERT_OFFSET + $sect.Length, $b.Length - $CERT_OFFSET)
  return ,$out
}

Say "VEGAS Pro 22 fix (instant splices + VRAM cap)`n" Cyan

# --- self-test mode (no admin, no Program Files): build from a copy and compare
if ($TestInput) {
  $out = Build-Patched ([IO.File]::ReadAllBytes($TestInput))
  [IO.File]::WriteAllBytes($TestOutput, $out)
  if ((Sha $out) -eq $PATCHED_DLL) { Done 'Test build matches the tested patched file.' $true } else { Done 'Test build does NOT match.' $false }
}

$dir = $null
try { $dir = (Get-ItemProperty 'HKLM:\SOFTWARE\VEGAS Creative Software\VEGAS Pro\22.0' -ErrorAction Stop).InstallPath } catch {}
if (-not $dir) { $dir = 'C:\Program Files\VEGAS\VEGAS Pro 22.0\' }
$dll = Join-Path $dir 'SfVstWrap.dll'
$exe = Join-Path $dir 'vegas220.exe'
$bak = Join-Path $dir 'SfVstWrap.dll.original-backup'
Say "VEGAS Pro 22 folder: $dir"
if (-not (Test-Path $dll)) { Done "Couldn't find VEGAS Pro 22 (looked for $dll)." $false }
if (Get-Process vegas220 -ErrorAction SilentlyContinue) { Done 'VEGAS Pro 22 is open. Close it and run this again.' $false }
$cur = Sha ([IO.File]::ReadAllBytes($dll))

if ($Uninstall) {
  if ($cur -eq $ORIG_DLL) { Done 'The fix is not installed (your file is already the original).' $true }
  if (-not (Test-Path $bak)) { Done "Backup not found ($bak). Reinstalling/repairing VEGAS Pro 22 will restore the original file." $false }
  if ((Sha ([IO.File]::ReadAllBytes($bak))) -ne $ORIG_DLL) { Done 'The backup file is not the original - not restoring it.' $false }
  Copy-Item $bak $dll -Force
  Done 'Removed. VEGAS Pro 22 is back to its original file.' $true
}

if ($cur -eq $PATCHED_DLL) { Done 'The fix is already installed. Nothing to do.' $true }
if ($cur -ne $ORIG_DLL) { Done "Your SfVstWrap.dll isn't the VEGAS Pro 22 build 250 original, so this fix can't be applied safely. Nothing was changed." $false }
if ((Sha ([IO.File]::ReadAllBytes($exe))) -ne $ORIG_EXE) { Done "Your vegas220.exe isn't VEGAS Pro 22 build 250, so this fix can't be applied safely. Nothing was changed." $false }

$out = Build-Patched ([IO.File]::ReadAllBytes($dll))
if ((Sha $out) -ne $PATCHED_DLL) { Done 'Self-check failed (the patched result did not match). Nothing was changed.' $false }
if (-not (Test-Path $bak)) { Copy-Item $dll $bak }
[IO.File]::WriteAllBytes($dll, $out)
if ((Sha ([IO.File]::ReadAllBytes($dll))) -ne $PATCHED_DLL) { Copy-Item $bak $dll -Force; Done 'Writing the file failed, original restored. Nothing was changed.' $false }
Done 'Installed! Open VEGAS Pro 22 and edit as usual. To undo, run Uninstall.bat.' $true
