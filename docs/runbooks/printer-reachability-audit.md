# Printer Reachability Audit

## Purpose

`Test-PrinterReachability.ps1` compares a CSV's expected printer hostnames and IP addresses with DNS and checks one TCP port from the workstation running the script. It is a diagnostic snapshot, not a print-job test or a complete network-path diagnosis.

## Prerequisites and authorization

- Obtain authorization for the source workstation/VLAN and target printer range before probing. Confirm the permitted port and test window with the network and print-service owners.
- Use a sanitized copy of the printer inventory when possible. The results contain internal hostnames and IP addresses; store and share them according to workplace data-handling rules.
- Run with an account that can read the CSV and write the report. Elevated privileges are not normally required.
- Windows PowerShell 5.1 or PowerShell 7+ with `Resolve-DnsName` available.

## Input

The script detects common hostname headers (`FQDN`, `Hostname`, `Host Name`, `Printer Name`, `DNS Name`, `Name`) and IP headers (`IP Address`, `IP`, `Printer IP`, `IPv4 Address`, `Address`). Specify `-NameColumn` and `-IPColumn` if the inventory uses different headers. Each row should have a hostname and a valid IP address.

A DNS suffix is never assumed. Use `-DnsSuffix` only when the approved canonical suffix is known and short hostnames need qualification.

## Run

Start with a small, approved CSV subset and the expected headers:

```powershell
.\scripts\powershell\Test-PrinterReachability.ps1 `
    -CsvPath '.\examples\printers-test.csv' `
    -NameColumn 'Hostname' `
    -IPColumn 'IP Address' `
    -Port 9100
```

The example file is not included; use an authorized inventory file. Omit explicit column parameters when the headers match a supported name. Use `-DnsSuffix 'corp.example.com'` only if that is the correct DNS suffix. Results default to a timestamped `Printer_Audit_Results_yyyyMMdd_HHmmss.csv` beside the input; set `-OutputPath` to choose another location. `-TimeoutMilliseconds` and `-DelayMillisecondsBetweenTargets` adjust per-target wait and pacing.

The script performs DNS lookups and bounded TCP connection attempts; it does not change printer, DNS, firewall, or client configuration. It tests only the selected TCP port (9100 by default). It does not probe SMB/445 or IPP/631 unless explicitly run with that port.

Use `-WhatIf` to preview the target count, port, and report path without running DNS or TCP checks. Use `-Confirm` to approve the audit before it starts. Default report filenames include a timestamp; an existing explicit output path is never overwritten.

## Interpretation and verification

- `ForwardDNS` compares all returned address records to the inventory IP. A mismatch can indicate stale inventory, DNS, or address-family/alias differences; verify against authoritative DNS and the asset owner.
- `ReversePTR` reports whether a PTR name exactly matches the forward target. Missing or different PTR data is a finding to investigate, not proof that printing is unavailable.
- `TCPPortReachable` means a TCP handshake completed from this source to this address and port within the configured timeout. `False` can reflect filtering, routing, host availability, listener configuration, or a timeout; correlate with firewall/ACL logs and tests from the relevant client VLAN.
- An open port does not verify queue configuration, printer status, or successful job rendering. Confirm with the print-service owner and an approved end-to-end print test.

Review the CSV for unexpected or missing inventory data before drawing fleet-wide conclusions. Avoid broad reruns until the owner approves the scope and probe rate.

## Rollback

No configuration is changed, so there is nothing to roll back. Remove the generated report according to local retention and data-handling requirements when it is no longer needed.
