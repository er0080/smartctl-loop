# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python script for automated SSD drive testing using smartctl. The script tests used SSDs connected via USB-SATA interface, extracts SMART health data, and outputs results to CSV format for batch drive verification workflows.

## Running the Script

The script requires root privileges to access block devices:

```bash
sudo python3 ssd_test.py
```

## Key Architecture Concepts

### SMART Data Extraction Strategy

The script uses `smartctl -j` (JSON output mode) to programmatically extract drive data. All smartctl calls should use the `-j` flag for reliable parsing. The critical command pattern is:

```bash
smartctl -x -j /dev/sdX  # Comprehensive data in single call
```

### SMART Attribute Mapping

Different SSD vendors use different SMART attribute IDs for the same metrics. The script must handle vendor variations:

- **Wear indicators**: Check ID 177 (Samsung Wear_Leveling_Count), ID 231 (SSD_Life_Left), and ID 233 (Intel Media_Wearout_Indicator)
  - **Critical**: All wear attributes report "remaining life %" (100 = new, 0 = worn)
  - Must invert to "wear consumed %": `wear_pct = 100 - remaining_life_value`
  - Example: SMART value of 99 means 99% life remaining → 1% wear consumed

- **Temperature (ID 194)**:
  - **Issue**: raw['value'] is a packed integer containing min/max/current temps in different bytes
  - **Solution**: Use top-level JSON field `temperature.current` (most reliable)
  - **Fallback**: Parse raw['string'] or extract lowest byte (raw_value & 0xFF)
  - Samsung drives may not report temperature via SMART attribute

- **Write endurance**: Vendor differences are critical!
  - **Samsung/Intel**: ID 241 (Total_LBAs_Written) = actual LBA count, multiply by 512 to get bytes
  - **WD/Kingston/SanDisk**: ID 241 = already in GB units, NOT LBAs!
  - **Crucial/Micron**: Use ID 246 (Host_Writes_32MiB) in 32 MiB units, not ID 241
  - **Heuristic**: If raw value > 100,000 → treat as LBAs; if < 100,000 → treat as GB

- **Reserved space**: ID 170 (Available_Reservd_Space) - note vendor-specific naming

Critical attributes for health assessment:
- IDs 5, 197, 198: Sector errors (reallocated, pending, uncorrectable)
- ID 9: Power_On_Hours (drive age)
- ID 194: Temperature_Celsius
- ID 12: Power_Cycle_Count

### CSV Output Format

The output CSV uses append mode to accumulate results across multiple test sessions. Filename format: `ssd_test_results_YYYYMMDD_HHMMSS.csv`

18 columns capture: timestamp, drive identification (model/serial/firmware/capacity), health status, usage metrics (hours, cycles, temperature), wear indicators, error counts, and test results.

### Error Handling Requirements

The script must gracefully handle:
1. Missing SMART attributes (use "N/A" placeholders)
2. smartctl command failures (check exit codes)
3. Invalid device paths (validate before calling smartctl)
4. Permission errors (detect and prompt for sudo)
5. JSON parsing failures (log and continue to next drive)

### Testing Loop Structure

The main workflow is iterative:
1. Check dependencies (smartctl presence, sudo privileges)
2. User connects drive
3. List available block devices (filter for /dev/sd* pattern)
4. User selects target device
5. Execute smartctl → Parse JSON → Display summary → Save to CSV
6. Prompt "Test another drive?" → repeat or exit

### Security Considerations

- Validate device path input to prevent command injection (regex: `/dev/sd[a-z]`)
- Never pass user input directly to shell without validation
- Use subprocess with list arguments, not shell=True

## Dependencies

- Python 3.7+ (stdlib only: subprocess, json, csv, datetime)
- smartmontools package (provides smartctl binary)
- Linux platform (block device access via /dev/sdX paths)
