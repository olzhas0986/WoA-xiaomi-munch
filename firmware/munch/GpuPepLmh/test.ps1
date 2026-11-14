#Requires -RunAsAdministrator
param([ValidateSet('prepare','start','status','rollback')][string]$Phase='status')
$ErrorActionPreference='Stop'
$Id='ACPI\QCOM2519\0'
$Key='HKLM:\SYSTEM\CurrentControlSet\Services\qcpep'
$Store='C:\munch-gpu-pep-lmh'
$StateFile=Join-Path $Store 'state.json'
$Image='\SystemRoot\System32\drivers\munch-qcpep-lmh-test.sys'
$Dest=Join-Path $env:SystemRoot 'System32\drivers\munch-qcpep-lmh-test.sys'
$Expected='39fafcd60536c7d36dd95187dc9f51bfc4af661b614bce4a5e9ec0729fe24e01'
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
function Value($k,$n){$o=Get-ItemProperty -LiteralPath $k;$p=$o.PSObject.Properties[$n];if($null -ne $p){return $p.Value}}
function Problem{[int](Get-PnpDeviceProperty -InstanceId $Id -KeyName DEVPKEY_Device_ProblemCode).Data}
function Native($exe,[string[]]$arguments){& $exe @arguments | Out-Host;if($LASTEXITCODE -notin @(0,3010)){throw "$exe failed: $LASTEXITCODE"};return $LASTEXITCODE}
function Snapshot{
 Write-Host ('Start: '+(Value $Key 'Start')+'; problem: '+(Problem))
 Write-Host ('ImagePath: '+(Value $Key 'ImagePath'))
 Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'" | Format-Table Name,State,StartMode
}
function Stopped{
 if((Value $Key 'Start') -ne 4){throw 'Set qcpep startup disabled before continuing'}
 $d=Get-CimInstance Win32_SystemDriver -Filter "Name='qcpep'"
 if($d.State -ne 'Stopped'){throw 'Driver still loaded: boot Windows31 with qcpep disabled first'}
}
function Save($s){
 $bytes=[Text.Encoding]::UTF8.GetBytes(($s | ConvertTo-Json -Depth 8))
 $tmp=$StateFile+'.tmp'
 $f=New-Object IO.FileStream($tmp,[IO.FileMode]::Create,[IO.FileAccess]::Write,[IO.FileShare]::None,4096,[IO.FileOptions]::WriteThrough)
 try{$f.Write($bytes,0,$bytes.Length);$f.Flush($true)}finally{$f.Dispose()}
 if(Test-Path $StateFile){[IO.File]::Replace($tmp,$StateFile,($StateFile+'.bak'))}else{[IO.File]::Move($tmp,$StateFile)}
}
if($Phase -eq 'status'){Snapshot;exit 0}
if(-not(Test-Path $Store)){New-Item -ItemType Directory $Store | Out-Null}
if($Phase -eq 'prepare'){
 if(Test-Path $StateFile){
  $previous=Get-Content -Raw $StateFile | ConvertFrom-Json
  if($previous.phase -ne 'rolled-back' -or (Value $Key 'ImagePath') -ine $previous.original_image_path -or (Value $Key 'Start') -ne 4){throw 'Previous diagnostic state exists; run rollback.cmd before preparing a new attempt'}
  $archive=Join-Path $Store ('state-archived-'+[guid]::NewGuid().ToString('N')+'.json')
  Move-Item -LiteralPath $StateFile -Destination $archive
 }
 if((Value $Key 'Start') -ne 4){throw 'Set qcpep startup disabled first'}
 $path=[string](Value $Key 'ImagePath')
 if(-not $path.StartsWith('\SystemRoot\System32\DriverStore\FileRepository\qcpep.wd8250.inf_arm64_',[StringComparison]::OrdinalIgnoreCase) -or -not $path.EndsWith('\qcpep8250.sys',[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected original ImagePath'}
 $original=Join-Path $env:SystemRoot $path.Substring(12)
 if((Get-FileHash -Algorithm SHA256 -LiteralPath $original).Hash.ToLowerInvariant() -ne $Expected){throw 'Original driver hash differs'}
 $state=[ordered]@{original_image_path=$path;original_start=4;original_sha256=$Expected;phase='prepared-disabled';test_image_path=$Image}
 Save $state
 if((Problem) -ne 22){$null=Native 'pnputil.exe' @('/disable-device',$Id,'/force')}
 Snapshot
 Write-Host 'Prepared. Boot Windows31 with qcpep startup disabled. Then run start.cmd.'
 exit 0
}
if(-not(Test-Path $StateFile)){throw 'Run prepare.cmd first'}
$s=Get-Content -Raw $StateFile | ConvertFrom-Json
if($Phase -eq 'rollback'){
 $current=[string](Value $Key 'ImagePath')
 if($current -ine $Image -and $current -ine $s.original_image_path){throw 'ImagePath changed externally; refusing to overwrite it'}
 $null=Native 'sc.exe' @('config','qcpep','start=','disabled')
 if((Problem) -ne 22){$null=Native 'pnputil.exe' @('/disable-device',$Id,'/force')}
 Set-ItemProperty -LiteralPath $Key -Name ImagePath -Value ([string]$s.original_image_path)
 if((Value $Key 'ImagePath') -ine $s.original_image_path -or (Value $Key 'Start') -ne 4){throw 'Rollback readback failed'}
 $s.phase='rolled-back';Save $s
 Write-Host 'Original driver path restored. PEP remains disabled. Reboot before further tests.'
 exit 0
}
Stopped
if((Problem) -ne 22){throw 'Device must be disabled (22); run prepare then reboot Windows31'}
if($s.phase -ne 'prepared-disabled'){throw 'Attempt already exists; collect logs, then rollback. Do not repeat automatically'}
if((Value $Key 'ImagePath') -ine $s.original_image_path){throw 'Original ImagePath changed'}
# Read runtime code-integrity flags (TESTSIGN=0x2), not merely pending BCD settings.
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class MunchLmhChecks {
 [DllImport("ntdll.dll")] public static extern int NtQuerySystemInformation(int c,ref CI i,int n,out int r);
 [StructLayout(LayoutKind.Sequential)] public struct CI {public uint Length;public uint Options;}
 [DllImport("kernel32.dll")] static extern uint GetSystemFirmwareTable(uint p,uint id,[Out]byte[] b,uint n);
 public static byte[] Dsdt(){uint n=GetSystemFirmwareTable(0x41435049,0x54445344,null,0);if(n<36||n>65536)throw new Exception("Cannot read DSDT");byte[] b=new byte[n];if(GetSystemFirmwareTable(0x41435049,0x54445344,b,n)!=n)throw new Exception("Cannot read DSDT");return b;}
 public static byte[] Ssdt(){uint n=GetSystemFirmwareTable(0x41435049,0x54445353,null,0);if(n<36||n>65536)throw new Exception("Cannot read SSDT");byte[] b=new byte[n];if(GetSystemFirmwareTable(0x41435049,0x54445353,b,n)!=n)throw new Exception("Cannot read SSDT");return b;}
}
'@
$ci=New-Object MunchLmhChecks+CI;$ci.Length=8;$ret=0
if([MunchLmhChecks]::NtQuerySystemInformation(103,[ref]$ci,8,[ref]$ret) -ne 0 -or ($ci.Options -band 2) -eq 0){throw 'Runtime test signing is not active'}
$ssdt=[Text.Encoding]::ASCII.GetString([MunchLmhChecks]::Ssdt())
if(-not $ssdt.Contains('CTPM') -or -not $ssdt.Contains('CORE_TOPOLOGY')){throw 'Boot Windows31 with the CTPM resource before retrying'}
$dsdt=[MunchLmhChecks]::Dsdt();$found=0
for($i=36;$i+14 -le $dsdt.Length;$i++){
 if($dsdt[$i] -eq 8 -and [Text.Encoding]::ASCII.GetString($dsdt,$i+1,4) -eq 'SOSI' -and $dsdt[$i+5] -eq 14){
  $addr=[BitConverter]::ToUInt64($dsdt,$i+6)
  if($addr -lt [uint64]2156920832 -or $addr -ge [uint64]2159017984){throw 'SOSI was not patched correctly'}
  $found++
 }
}
if($found -ne 1){throw 'Boot Windows31 with its patched SOSI first'}
[IO.File]::WriteAllBytes((Join-Path $Store 'DSDT.aml'),$dsdt)
$manifest=Get-Content -Raw (Join-Path $PSScriptRoot 'patch.json') | ConvertFrom-Json
$unsigned=Join-Path $PSScriptRoot 'qcpep-lmh-unsigned.sys'
if($manifest.original_sha256 -ne $Expected -or (Get-FileHash -Algorithm SHA256 $unsigned).Hash.ToLowerInvariant() -ne $manifest.unsigned_sha256){throw 'Diagnostic driver hash mismatch'}
Copy-Item -LiteralPath $unsigned -Destination $Dest
# A new private test key stays on this phone; no vendor identity is impersonated.
$cert=New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=Munch PEP LMH Diagnostic' -CertStoreLocation Cert:\LocalMachine\My -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -KeyExportPolicy NonExportable -NotAfter (Get-Date).AddYears(1)
$s | Add-Member -NotePropertyName certificate_thumbprint -NotePropertyValue $cert.Thumbprint -Force
Save $s
$cer=Join-Path $Store 'diagnostic.cer'
Export-Certificate -Cert $cert -FilePath $cer | Out-Null
$null=Native 'certutil.exe' @('-f','-addstore','Root',$cer)
$signature=Set-AuthenticodeSignature -FilePath $Dest -Certificate $cert -HashAlgorithm SHA256 -IncludeChain All
if($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $cert.Thumbprint){throw ('Embedded test signature failed: '+$signature.Status+' '+$signature.StatusMessage)}
$s | Add-Member -NotePropertyName signed_sha256 -NotePropertyValue ((Get-FileHash -Algorithm SHA256 $Dest).Hash.ToLowerInvariant()) -Force
$s.phase='signed-before-path-change';Save $s
Set-ItemProperty -LiteralPath $Key -Name ImagePath -Value $Image
if((Value $Key 'ImagePath') -ine $Image -or (Value $Key 'Start') -ne 4){throw 'ImagePath/start readback failed; run rollback.cmd'}
$s.phase='late-activation-attempt';Save $s
Write-Host 'Signed diagnostic copy selected. Starting one traced late-activation attempt.'
& (Join-Path $PSScriptRoot 'late.ps1') -Phase start
Snapshot
Write-Host 'Collect logs with collect.cmd; use rollback.cmd to restore the native path.'
