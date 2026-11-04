<#
.SYNOPSIS
    Audits printer DNS records and TCP port reachability from the current workstation.
.DESCRIPTION
    Reads a printer CSV, compares forward DNS records with the expected IP, checks PTR,
    and attempts a bounded TCP connection to the selected port. This does not verify that
    a printer can render or complete a print job.
.PARAMETER CsvPath
    Path to the input CSV file.
.PARAMETER OutputPath
    Path for the results CSV. Defaults to Printer_Audit_Results.csv beside the input.
.PARAMETER NameColumn
    CSV column containing the printer hostname. If omitted, common names are detected.
.PARAMETER IPColumn
    CSV column containing the expected printer IP. If omitted, common names are detected.
.PARAMETER DnsSuffix
    Optional suffix appended only to short hostnames, for example corp.example.com.
.PARAMETER Port
    TCP destination port to test. Defaults to RAW printing port 9100.
.PARAMETER TimeoutMilliseconds
    Maximum wait for each TCP connection attempt.
.PARAMETER DelayMillisecondsBetweenTargets
    Delay between target checks to limit probe rate.
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$CsvPath,

    [string]$OutputPath,

    [string]$NameColumn,

    [string]$IPColumn,

    [string]$DnsSuffix,

    [ValidateRange(1, 65535)]
    [int]$Port = 9100,

    [ValidateRange(100, 60000)]
    [int]$TimeoutMilliseconds = 2000,

    [ValidateRange(0, 60000)]
    [int]$DelayMillisecondsBetweenTargets = 100
)

function Resolve-CsvColumn {
    param(
        [Parameter(Mandatory = $true)] [string[]]$Headers,
        [string]$RequestedColumn,
        [Parameter(Mandatory = $true)] [string[]]$Candidates,
        [Parameter(Mandatory = $true)] [string]$Description
    )

    if ($RequestedColumn) {
        $match = $Headers | Where-Object { $_ -ieq $RequestedColumn } | Select-Object -First 1
        if (-not $match) {
            throw "CSV column '$RequestedColumn' for $Description was not found. Available columns: $($Headers -join ', ')"
        }
        return $match
    }

    foreach ($candidate in $Candidates) {
        $match = $Headers | Where-Object { $_ -ieq $candidate } | Select-Object -First 1
        if ($match) { return $match }
    }

    throw "Could not identify the $Description column. Specify it with the corresponding column parameter. Available columns: $($Headers -join ', ')"
}

function Test-TcpPort {
    param(
        [Parameter(Mandatory = $true)] [string]$ComputerName,
        [Parameter(Mandatory = $true)] [int]$Port,
        [Parameter(Mandatory = $true)] [int]$TimeoutMilliseconds
    )

    $client = New-Object System.Net.Sockets.TcpClient
    $asyncResult = $null
    try {
        $asyncResult = $client.BeginConnect($ComputerName, $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMilliseconds, $false)) {
            return $false
        }

        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($asyncResult -and $asyncResult.AsyncWaitHandle) {
            $asyncResult.AsyncWaitHandle.Close()
        }
        $client.Close()
    }
}

$resolvedCsvPath = (Resolve-Path -LiteralPath $CsvPath -ErrorAction Stop).Path
$printers = @(Import-Csv -LiteralPath $resolvedCsvPath -ErrorAction Stop)
if ($printers.Count -eq 0) {
    throw "The CSV contains no data rows: $resolvedCsvPath"
}

$headers = @($printers[0].PSObject.Properties.Name)
$nameColumnResolved = Resolve-CsvColumn -Headers $headers -RequestedColumn $NameColumn -Candidates @('FQDN', 'Hostname', 'Host Name', 'Printer Name', 'DNS Name', 'Name') -Description 'hostname'
$ipColumnResolved = Resolve-CsvColumn -Headers $headers -RequestedColumn $IPColumn -Candidates @('IP Address', 'IP', 'Printer IP', 'IPv4 Address', 'Address') -Description 'IP address'

if (-not $OutputPath) {
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $OutputPath = Join-Path -Path (Split-Path -Parent $resolvedCsvPath) -ChildPath "Printer_Audit_Results_$timestamp.csv"
}
$outputFullPath = [System.IO.Path]::GetFullPath($OutputPath)
if ($outputFullPath -eq $resolvedCsvPath) {
    throw 'OutputPath must not overwrite the input CSV.'
}
if (Test-Path -LiteralPath $outputFullPath) {
    throw "OutputPath already exists: $outputFullPath. Choose a different path to preserve the existing report."
}

if (-not $PSCmdlet.ShouldProcess("$($printers.Count) printer(s), TCP port $Port, report '$outputFullPath'", 'Run reachability audit')) {
    return
}

if ($DnsSuffix) {
    $DnsSuffix = $DnsSuffix.Trim().Trim('.')
}

$results = @(
    for ($index = 0; $index -lt $printers.Count; $index++) {
        $printer = $printers[$index]
        $expectedName = [string]$printer.$nameColumnResolved
        $expectedName = $expectedName.Trim().TrimEnd('.')
        $expectedIPText = [string]$printer.$ipColumnResolved
        $expectedIPText = $expectedIPText.Trim()
        $parsedExpectedIP = $null
        $validIP = [System.Net.IPAddress]::TryParse($expectedIPText, [ref]$parsedExpectedIP)

        $targetName = $expectedName
        if ($targetName -and $DnsSuffix -and $targetName -notmatch '\.') {
            $targetName = "$targetName.$DnsSuffix"
        }

        $forwardStatus = 'Not checked: hostname missing'
        $resolvedAddresses = @()
        if ($targetName) {
            try {
                $dnsRecords = @(Resolve-DnsName -Name $targetName -ErrorAction Stop)
                $resolvedAddresses = @($dnsRecords | Where-Object { $_.IPAddress } | Select-Object -ExpandProperty IPAddress -Unique)
                if ($resolvedAddresses.Count -eq 0) {
                    $forwardStatus = 'No address records'
                } elseif (-not $validIP) {
                    $forwardStatus = 'Resolved; expected IP invalid or missing'
                } else {
                    $addressMatches = $false
                    foreach ($resolvedAddress in $resolvedAddresses) {
                        $parsedResolvedAddress = $null
                        if ([System.Net.IPAddress]::TryParse([string]$resolvedAddress, [ref]$parsedResolvedAddress) -and $parsedResolvedAddress.Equals($parsedExpectedIP)) {
                            $addressMatches = $true
                            break
                        }
                    }
                    if ($addressMatches) {
                        $forwardStatus = 'Match'
                    } else {
                        $forwardStatus = "IP mismatch ($($resolvedAddresses -join ', '))"
                    }
                }
            }
            catch {
                $forwardStatus = "Lookup failed: $($_.Exception.Message)"
            }
        }

        $reverseName = ''
        $reverseStatus = if ($validIP) { 'No PTR record' } else { 'Not checked: invalid or missing IP' }
        if ($validIP) {
            try {
                $ptrRecords = @(Resolve-DnsName -Name $parsedExpectedIP.ToString() -Type PTR -ErrorAction Stop)
                $reverseNames = @($ptrRecords | Where-Object { $_.NameHost } | Select-Object -ExpandProperty NameHost -Unique)
                if ($reverseNames.Count -gt 0) {
                    $reverseName = $reverseNames -join ', '
                    $normalizedReverseNames = @($reverseNames | ForEach-Object { ([string]$_).Trim().TrimEnd('.') })
                    if (-not $targetName) {
                        $reverseStatus = 'PTR found; hostname unavailable for comparison'
                    } elseif ($normalizedReverseNames -icontains $targetName) {
                        $reverseStatus = 'Match'
                    } else {
                        $reverseStatus = "Mismatch ($reverseName)"
                    }
                }
            }
            catch {
                $reverseStatus = 'No PTR record'
            }
        }

        $portStatus = 'Not checked: invalid or missing IP'
        if ($validIP) {
            $portStatus = Test-TcpPort -ComputerName $parsedExpectedIP.ToString() -Port $Port -TimeoutMilliseconds $TimeoutMilliseconds
        }

        [PSCustomObject]@{
            ExpectedHostname = $targetName
            ExpectedIP = $expectedIPText
            ForwardDNS = $forwardStatus
            ReversePTR = $reverseStatus
            ReverseHostname = $reverseName
            TestedTCPPort = $Port
            TCPPortReachable = $portStatus
        }

        if ($DelayMillisecondsBetweenTargets -gt 0 -and $index -lt ($printers.Count - 1)) {
            Start-Sleep -Milliseconds $DelayMillisecondsBetweenTargets
        }
    }
)

$results | Format-Table -AutoSize
$results | Export-Csv -LiteralPath $outputFullPath -NoTypeInformation -Encoding UTF8 -ErrorAction Stop
Write-Host "Audit complete. Results saved to $outputFullPath"
