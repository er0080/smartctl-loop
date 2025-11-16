# SSD Testing Script - Project Plan

## Overview
A Python script to automate the testing and verification of used SSD drives connected via USB-SATA interface. The script uses `smartctl` to gather SMART data and health metrics, then saves the results to a CSV file for easy analysis and record-keeping. My personal use for this software is printing labels/stickers for inventory tracking purposes. I use MS Word "mail merge" feature for this purpose.

## Objectives
- Automate drive detection and testing workflow
- Extract and analyze critical SMART parameters for SSD health assessment
- Provide clear pass/fail indicators and warnings
- Generate structured CSV output for batch drive testing
- Support iterative testing of multiple drives without script restart

## Technical Requirements

### Dependencies
- **Python 3.7+** (for subprocess, json, csv modules)
- **smartmontools** package (provides `smartctl` command)
- **Root/sudo privileges** (required for smartctl to access block devices)

### Platform Support
- Primary target: Linux (Ubuntu/Debian)
- Block device paths: `/dev/sdX` format

## Key SMART Parameters for SSD Health

The script will extract and analyze the following critical parameters:

### Basic Drive Information
- **Model Number**: Drive manufacturer and model
- **Serial Number**: Unique drive identifier
- **Firmware Version**: Firmware revision
- **Capacity**: Total drive capacity (GB/TB)

### Critical SMART Attributes
| Attribute ID | Name | Purpose |
|-------------|------|---------|
| 9 | Power_On_Hours | Total operating hours (drive age) |
| 12 | Power_Cycle_Count | Number of power-on cycles |
| 194 | Temperature_Celsius | Current drive temperature |
| 5 | Reallocated_Sector_Ct | Count of bad sectors remapped |
| 197 | Current_Pending_Sector | Sectors waiting for remapping |
| 198 | Offline_Uncorrectable | Uncorrectable sector count |
| 170 | Available_Reservd_Space | Remaining spare blocks (%) |
| 177 | Wear_Leveling_Count | SSD wear indicator (Samsung/various) |
| 231 | SSD_Life_Left | Remaining drive life percentage |
| 233 | Media_Wearout_Indicator | Intel wear metric |
| 241 | Total_LBAs_Written | Total logical blocks written |

### Health Indicators
- **Overall SMART Health**: PASSED/FAILED status
- **Self-Test Result**: Short self-test pass/fail
- **Wear Level**: Percentage of drive life consumed (0% = new, 100% = worn out)
  - Note: SMART attributes 177/231/233 report "remaining life" (100 = new)
  - Script converts to "consumed" by calculating: 100 - remaining_life_value
- **Critical Warnings**: Any parameters exceeding safe thresholds

## Script Workflow

### 1. Initialization Phase
```
- Check for smartctl installation
- Verify sudo/root privileges
- Initialize or open existing CSV output file
- Display welcome message and instructions
```

### 2. Main Testing Loop
```
For each drive to test:
  a. Prompt user to connect drive
  b. List available block devices (lsblk or /dev/sd*)
  c. User selects target drive (e.g., /dev/sdb)
  d. Validate drive selection
  e. Execute smartctl commands:
     - smartctl -i -j <device>    # Get device info
     - smartctl -H -j <device>    # Get health status
     - smartctl -A -j <device>    # Get SMART attributes
     - smartctl -l selftest -j <device>  # Get self-test log
  f. Parse JSON output
  g. Extract key parameters
  h. Calculate derived metrics (e.g., TB written)
  i. Display summary to user:
     - Drive model and serial
     - Health status (PASS/FAIL)
     - Key metrics (hours, wear, temperature)
     - Any warnings or failures
  j. Append results to CSV file
  k. Ask: "Test another drive? (y/n)"
  l. If yes, continue loop; if no, exit
```

### 3. Data Processing
- **JSON Parsing**: Use `json` module to parse smartctl JSON output
- **Attribute Extraction**: Map SMART attribute IDs to meaningful names
- **Unit Conversion**: Convert raw values (e.g., LBAs to TB)
- **Threshold Checking**: Flag values outside acceptable ranges
- **Error Handling**: Gracefully handle missing attributes or vendor variations

### 4. Error Handling
- **smartctl not found**: Prompt to install smartmontools
- **Permission denied**: Remind user to run with sudo
- **Device not found**: Validate device path, re-prompt user
- **JSON parse error**: Log error, skip drive, continue
- **Attribute not present**: Use "N/A" placeholder in CSV

## CSV Output Format

### Filename Convention
`ssd_test_results_YYYYMMDD_HHMMSS.csv`

### Column Structure
| Column | Description | Example |
|--------|-------------|---------|
| Timestamp | Test date/time | 2025-11-08 14:23:10 |
| Model | Drive model | Samsung SSD 860 EVO 500GB |
| Serial | Serial number | S3Z5NB0K123456A |
| Firmware | Firmware version | RVT01B6Q |
| Capacity_GB | Drive capacity | 500 |
| Health_Status | PASSED/FAILED | PASSED |
| Power_On_Hours | Total hours | 5234 |
| Power_Cycles | Power-on count | 1052 |
| Temperature_C | Current temp | 35 |
| Total_LBAs_Written | Raw LBA count | 12453627392 |
| Total_TB_Written | Calculated TB | 6.4 |
| Wear_Level_Pct | Wear percentage | 15 |
| Reserved_Space_Pct | Available spare | 100 |
| Reallocated_Sectors | Bad sectors | 0 |
| Pending_Sectors | Pending remap | 0 |
| Uncorrectable_Sectors | Uncorrectable | 0 |
| Self_Test_Result | Test result | PASSED |
| Warnings | Issues found | None |

### CSV Format Details
- **Delimiter**: Comma (`,`)
- **Header Row**: Yes (column names)
- **Encoding**: UTF-8
- **Quoting**: Quote fields containing commas or newlines
- **Append Mode**: Add new rows without overwriting existing data

## Implementation Considerations

### Drive Detection
Use `lsblk` or scan `/dev/` to list available drives. Filter for likely targets (sdX devices, exclude mounted system drives).

### Vendor Variations
Different SSD manufacturers use different SMART attribute IDs. The script should:
- Check for multiple possible attribute IDs for the same metric
- Gracefully handle missing attributes
- Note vendor-specific attributes in output

### Performance
- Use `smartctl -x -j` for comprehensive data in a single call (more efficient)
- Avoid running long self-tests during quick screening (time-consuming)
- Consider optional short self-test with user confirmation

### User Experience
- Clear prompts and instructions
- Real-time feedback during testing
- Color-coded output (optional: green=pass, red=fail, yellow=warning)
- Summary statistics at end (total drives tested, pass/fail counts)

### Security
- Validate user input (device paths)
- Prevent command injection
- Run with minimum required privileges

## Future Enhancements (Optional)
- GUI interface using tkinter or PyQt
- Automatic drive detection (monitor USB insertion)
- Historical tracking (compare current test to previous tests)
- Email/notification when testing complete
- Generate PDF reports with graphs
- Support for NVMe drives
- Batch mode (test all connected drives automatically)
- Database storage instead of/in addition to CSV

## Testing Strategy
- Test with multiple SSD models (Samsung, Crucial, Intel, etc.)
- Test with drives of various health states (new, used, failing)
- Verify CSV format and data accuracy
- Test error handling (disconnected drive, permission errors)
- Validate on different Linux distributions

## Success Criteria
- Script successfully detects and tests USB-connected SSDs
- All critical SMART parameters are captured
- CSV output is correctly formatted and readable
- User can test multiple drives in sequence without restarting
- Clear pass/fail indicators for drive health
- Handles errors gracefully without crashing

## Project Structure
```
smartctl-loop/
├── README.md              # This file (project plan)
├── ssd_test.py           # Main script
├── requirements.txt      # Python dependencies (if any external libs)
├── example_output.csv    # Sample CSV output
└── tests/               # Optional: unit tests
    └── test_ssd_test.py
```

## Next Steps
1. Implement core script with basic smartctl integration
2. Add JSON parsing and data extraction
3. Implement CSV output functionality
4. Add user interaction loop
5. Implement error handling and validation
6. Test with real SSD drives
7. Refine output format based on testing
8. Add documentation and usage examples
