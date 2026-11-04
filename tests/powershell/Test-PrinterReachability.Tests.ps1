Describe 'Test-PrinterReachability.ps1' {
    BeforeAll {
        $scriptPath = Join-Path $PSScriptRoot '..\..\scripts\powershell\Test-PrinterReachability.ps1'
        $testRoot = Join-Path $TestDrive 'printer-audit'
        $csvPath = Join-Path $testRoot 'printers.csv'

        New-Item -Path $testRoot -ItemType Directory -Force | Out-Null
        @'
Hostname,IP Address
printer-01,192.0.2.10
'@ | Set-Content -LiteralPath $csvPath -Encoding utf8
    }

    It 'does not perform network checks or create a report with WhatIf' {
        $outputPath = Join-Path $testRoot 'whatif.csv'

        & $scriptPath -CsvPath $csvPath -OutputPath $outputPath -WhatIf

        Test-Path -LiteralPath $outputPath | Should Be $false
    }

    It 'does not overwrite an existing report' {
        $outputPath = Join-Path $testRoot 'existing.csv'
        'existing report' | Set-Content -LiteralPath $outputPath -Encoding utf8

        $caughtError = $null
        try {
            & $scriptPath -CsvPath $csvPath -OutputPath $outputPath -WhatIf -ErrorAction Stop
        }
        catch {
            $caughtError = $_
        }

        ($caughtError.Exception.Message -like '*OutputPath already exists*') | Should Be $true
    }
}