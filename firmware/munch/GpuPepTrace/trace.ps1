#Requires -RunAsAdministrator
param([ValidateSet('prepare','status','rollback')][string]$Phase='prepare')
$ErrorActionPreference='Stop'
if((Get-CimInstance Win32_ComputerSystem).Model.Trim() -ne 'POCO F4'){throw 'Only POCO F4'}
$Name='MunchPepBoot'
$Guid='{B516137F-7211-4A26-986F-C4BA51B7656C}'
$Root='HKLM:\SYSTEM\CurrentControlSet\Control\WMI\Autologger\'+$Name
$Store='C:\munch-gpu-pep-trace'
if(-not(Test-Path $Store)){New-Item -ItemType Directory $Store | Out-Null}
$LogDir=Join-Path $env:SystemRoot 'System32\LogFiles\WMI'
if(-not(Test-Path $LogDir)){New-Item -ItemType Directory $LogDir | Out-Null}
$StateFile=Join-Path $Store 'state.json'
function Value($key,$name){
 if(-not(Test-Path -LiteralPath $key)){return $null}
 $row=Get-ItemProperty -LiteralPath $key
 $prop=$row.PSObject.Properties[$name]
 if($null -ne $prop){return $prop.Value}
 return $null
}
function Set-Value($key,$name,$type,$value){
 if(-not(Test-Path -LiteralPath $key)){New-Item -Path $key -Force | Out-Null}
 New-ItemProperty -LiteralPath $key -Name $name -PropertyType $type -Value $value -Force | Out-Null
 $readback=Value $key $name
 if($type -eq 'DWord'){
  # Windows providers can return the same DWORD as Int32 or UInt32.
  $matches=($null -ne $readback -and (([int64]$readback -band 4294967295) -eq ([int64]$value -band 4294967295)))
 }else{$matches=($null -ne $readback -and $readback -eq $value)}
 if(-not $matches){throw "Registry readback failed: $name (expected $value; actual $readback)"}
}
function Logged($exe,[string[]]$arguments,$file){
 $text=& $exe @arguments 2>&1;$code=$LASTEXITCODE
 $text | Out-File -Encoding UTF8 (Join-Path $Store $file)
 $text | ForEach-Object {Write-Host $_}
 return $code
}
function Check-Owned {
 if(-not(Test-Path $StateFile)){throw 'No saved trace ownership record'}
 $s=Get-Content -Raw $StateFile | ConvertFrom-Json
 if($s.guid -ne $Guid -or $s.name -ne $Name -or (Value $Root 'Guid') -ne $Guid){throw 'Trace configuration is not owned by this package'}
}
if($Phase -eq 'status'){
 Write-Host ('PEP Start: '+(Value 'HKLM:\SYSTEM\CurrentControlSet\Services\qcpep' 'Start')+' (4 = disabled)')
 Write-Host ('Boot trace Start: '+(Value $Root 'Start'))
 $code=Logged 'logman.exe' @('query',$Name,'-ets') 'boot-session-status.txt'
 Write-Host ('Boot trace query exit: '+$code)
 Get-ChildItem -LiteralPath $LogDir -File | Where-Object {$_.Name -like 'MunchPepBoot.etl*'} | Select-Object Name,Length
 exit 0
}
if($Phase -eq 'rollback'){
 Check-Owned
 $code=Logged 'logman.exe' @('query',$Name,'-ets') 'rollback-query.txt'
 if($code -eq 0){
  $code=Logged 'logman.exe' @('stop',$Name,'-ets') 'rollback-stop.txt'
  if($code -ne 0){throw 'Cannot stop the diagnostic trace; configuration retained'}
 }
 Remove-Item -LiteralPath $Root -Recurse
 Write-Host 'Own boot trace removed. Existing ETL files and PEP settings retained.'
 exit 0
}
# Preparing tracing never changes the driver's Start value or enables the device.
if((Value 'HKLM:\SYSTEM\CurrentControlSet\Services\qcpep' 'Start') -ne 4){throw 'Keep qcpep disabled (Start=4) while preparing tracing'}
if(Test-Path $Root){Check-Owned}
else{
 if(Test-Path $StateFile){throw 'Saved trace state exists but its registry key is missing; inspect before reconfiguration'}
 [ordered]@{name=$Name;guid=$Guid;purpose='PEP boot diagnostics only';file=(Join-Path $LogDir 'MunchPepBoot.etl')} | ConvertTo-Json | Set-Content -Encoding UTF8 $StateFile
}
Set-Value $Root 'Guid' String $Guid
Set-Value $Root 'Start' DWord 1
Set-Value $Root 'LogFileMode' DWord 1
Set-Value $Root 'FileName' String (Join-Path $LogDir 'MunchPepBoot.etl')
Set-Value $Root 'FileMax' DWord 4
Set-Value $Root 'MaxFileSize' DWord 16
Set-Value $Root 'FlushTimer' DWord 1
Set-Value $Root 'BufferSize' DWord 64
Set-Value $Root 'MinimumBuffers' DWord 4
Set-Value $Root 'MaximumBuffers' DWord 32
Set-Value $Root 'ClockType' DWord 1
$Providers=@(
 [pscustomobject]@{name='Kernel-Pep';guid='{5412704E-B2E1-4624-8FFD-55777B8F7373}';stack=4},
 [pscustomobject]@{name='Kernel-PnP';guid='{9C205A39-1250-487D-ABD7-E831C6290539}';stack=4},
 [pscustomobject]@{name='Kona RPMH';guid='{2C89C855-6301-41F9-BF56-63416DFE9CA9}';stack=0}
)
foreach($provider in $Providers){
 $key=Join-Path $Root $provider.guid
 Set-Value $key 'Enabled' DWord 1
 Set-Value $key 'EnableLevel' DWord 5
 Set-Value $key 'EnableFlags' DWord -1
 Set-Value $key 'EnableProperty' DWord $provider.stack
 Set-Value $key 'MatchAnyKeyword' QWord 0
 Set-Value $key 'MatchAllKeyword' QWord 0
}
# Exercise file tracing now, with PEP still disabled. No DCS is persisted (-ets).
$Id=[guid]::NewGuid().ToString('N').Substring(0,8)
$CheckName='MunchPepCheck-'+$Id
$CheckFile=Join-Path $LogDir ($CheckName+'.etl')
$ProviderFile=Join-Path $Store ('providers-'+$Id+'.txt')
$Providers | ForEach-Object {$_.guid+' 0xFFFFFFFFFFFFFFFF 5'} | Set-Content -Encoding ASCII $ProviderFile
$active=$false
try{
 $code=Logged 'logman.exe' @('create','trace',$CheckName,'-o',$CheckFile,'-pf',$ProviderFile,'-f','bin','-max','16','-bs','64','-nb','4','32','-ft','00:00:01','-ets') 'check-start.txt'
 if($code -ne 0){throw 'File trace test failed to start; PEP remains disabled'}
 $active=$true
 $code=Logged 'logman.exe' @('query',$CheckName,'-ets') 'check-query.txt'
 if($code -ne 0){throw 'File trace session could not be queried'}
}finally{
 if($active){
  $stop=Logged 'logman.exe' @('stop',$CheckName,'-ets') 'check-stop.txt'
  if($stop -ne 0){throw 'File trace could not be stopped; inspect check-stop.txt'}
 }
}
if(-not(Test-Path -LiteralPath $CheckFile) -or (Get-Item -LiteralPath $CheckFile).Length -eq 0){throw 'Test ETL file missing or empty'}
if((Value 'HKLM:\SYSTEM\CurrentControlSet\Services\qcpep' 'Start') -ne 4){throw 'Unexpected PEP startup change; tracing setup stopped'}
[ordered]@{time=(Get-Date).ToString('o');test_file=$CheckFile;test_bytes=(Get-Item $CheckFile).Length;boot_session=$Name;driver_start=4;note='Boot AutoLogger still requires verification after a reboot; a flushed ETL tail cannot be guaranteed during a hard hang.'} | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Store 'prepared.json')
Write-Host 'Trace setup OK. File tracing checked. PEP remains disabled.'
Write-Host 'Boot tracing will activate on the next Windows boot.'
