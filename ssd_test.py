#!/usr/bin/env python3
"""
SSD Testing Script
Automates testing of used SSD drives via USB-SATA interface using smartctl.
Outputs results to CSV file for batch drive verification.
"""

import subprocess
import json
import csv
import sys
import os
import re
from datetime import datetime
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    # Check if stdout is a terminal and supports colors
    _is_tty = sys.stdout.isatty()

    # Color codes
    RED = '\033[91m' if _is_tty else ''
    GREEN = '\033[92m' if _is_tty else ''
    YELLOW = '\033[93m' if _is_tty else ''
    BLUE = '\033[94m' if _is_tty else ''
    MAGENTA = '\033[95m' if _is_tty else ''
    CYAN = '\033[96m' if _is_tty else ''
    WHITE = '\033[97m' if _is_tty else ''
    BOLD = '\033[1m' if _is_tty else ''
    RESET = '\033[0m' if _is_tty else ''

    @classmethod
    def success(cls, text):
        """Return text in green (success)"""
        return f"{cls.GREEN}{text}{cls.RESET}"

    @classmethod
    def error(cls, text):
        """Return text in red (error)"""
        return f"{cls.RED}{text}{cls.RESET}"

    @classmethod
    def warning(cls, text):
        """Return text in yellow (warning)"""
        return f"{cls.YELLOW}{text}{cls.RESET}"

    @classmethod
    def info(cls, text):
        """Return text in cyan (info)"""
        return f"{cls.CYAN}{text}{cls.RESET}"

    @classmethod
    def header(cls, text):
        """Return text in bold (header)"""
        return f"{cls.BOLD}{text}{cls.RESET}"


class SMARTAttribute:
    """Maps SMART attribute IDs to their purposes"""
    POWER_ON_HOURS = 9
    POWER_CYCLES = 12
    TEMPERATURE = 194
    REALLOCATED_SECTORS = 5
    PENDING_SECTORS = 197
    UNCORRECTABLE_SECTORS = 198
    RESERVED_SPACE = 170
    WEAR_LEVELING = 177
    SSD_LIFE_LEFT = 231
    MEDIA_WEAROUT = 233
    TOTAL_LBAS_WRITTEN = 241
    HOST_WRITES_32MIB = 246  # Crucial/Micron use this instead of 241


def check_dependencies():
    """Verify smartctl is installed and script has sudo privileges"""
    # Check for smartctl
    try:
        result = subprocess.run(['which', 'smartctl'],
                              capture_output=True,
                              text=True,
                              check=False)
        if result.returncode != 0:
            print(Colors.error("ERROR: smartctl not found. Please install smartmontools:"))
            print("  Ubuntu/Debian: sudo apt-get install smartmontools")
            print("  Fedora/RHEL: sudo dnf install smartmontools")
            return False
    except Exception as e:
        print(Colors.error(f"ERROR: Failed to check for smartctl: {e}"))
        return False

    # Check for root/sudo privileges
    if os.geteuid() != 0:
        print(Colors.error("ERROR: This script requires root privileges."))
        print("Please run with: sudo python3 ssd_test.py")
        return False

    return True


def list_block_devices():
    """List available block devices, filtering for likely USB-SATA drives"""
    try:
        result = subprocess.run(['lsblk', '-d', '-n', '-o', 'NAME,SIZE,TYPE'],
                              capture_output=True,
                              text=True,
                              check=True)

        devices = []
        for line in result.stdout.strip().split('\n'):
            parts = line.split()
            if len(parts) >= 3:
                name, size, dev_type = parts[0], parts[1], parts[2]
                # Filter for disk type devices (not partitions or loops)
                if dev_type == 'disk' and name.startswith('sd'):
                    devices.append((name, size))

        return devices
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to list block devices: {e}")
        return []


def validate_device_path(device_path):
    """Validate device path to prevent command injection"""
    # Must match /dev/sd[a-z] pattern
    pattern = r'^/dev/sd[a-z]$'
    if not re.match(pattern, device_path):
        return False

    # Verify device exists
    if not Path(device_path).exists():
        return False

    return True


def run_smartctl(device_path, options):
    """Execute smartctl command and return JSON output"""
    cmd = ['smartctl'] + options + ['-j', device_path]

    try:
        result = subprocess.run(cmd,
                              capture_output=True,
                              text=True,
                              check=False)

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
            return data, result.returncode
        except json.JSONDecodeError as e:
            print(f"ERROR: Failed to parse smartctl JSON output: {e}")
            return None, result.returncode

    except Exception as e:
        print(f"ERROR: Failed to execute smartctl: {e}")
        return None, -1


def extract_device_info(smartctl_data):
    """Extract basic device information from smartctl output"""
    info = {
        'model': 'N/A',
        'serial': 'N/A',
        'firmware': 'N/A',
        'capacity_gb': 'N/A'
    }

    if not smartctl_data:
        return info

    try:
        # Extract model name
        if 'model_name' in smartctl_data:
            info['model'] = smartctl_data['model_name']
        elif 'model_family' in smartctl_data:
            info['model'] = smartctl_data['model_family']

        # Extract serial number
        if 'serial_number' in smartctl_data:
            info['serial'] = smartctl_data['serial_number']

        # Extract firmware version
        if 'firmware_version' in smartctl_data:
            info['firmware'] = smartctl_data['firmware_version']

        # Extract capacity (convert to GB)
        if 'user_capacity' in smartctl_data:
            capacity_bytes = smartctl_data['user_capacity'].get('bytes', 0)
            info['capacity_gb'] = round(capacity_bytes / (1024**3), 2)

    except Exception as e:
        print(f"WARNING: Error extracting device info: {e}")

    return info


def extract_smart_attributes(smartctl_data):
    """Extract SMART attributes from smartctl output"""
    attributes = {
        'power_on_hours': 'N/A',
        'power_cycles': 'N/A',
        'temperature_c': 'N/A',
        'reallocated_sectors': 'N/A',
        'pending_sectors': 'N/A',
        'uncorrectable_sectors': 'N/A',
        'reserved_space_pct': 'N/A',
        'wear_level_pct': 'N/A',
        'total_lbas_written': 'N/A',
        'total_tb_written': 'N/A'
    }

    if not smartctl_data:
        return attributes

    try:
        # Extract temperature from top-level JSON field (more reliable)
        if 'temperature' in smartctl_data and 'current' in smartctl_data['temperature']:
            attributes['temperature_c'] = smartctl_data['temperature']['current']

        # Extract SMART attributes if available
        if 'ata_smart_attributes' not in smartctl_data:
            return attributes

        smart_attrs = smartctl_data['ata_smart_attributes'].get('table', [])

        # Create lookup dictionary by attribute ID
        attr_lookup = {attr['id']: attr for attr in smart_attrs}

        # Extract each attribute by ID
        if SMARTAttribute.POWER_ON_HOURS in attr_lookup:
            attributes['power_on_hours'] = attr_lookup[SMARTAttribute.POWER_ON_HOURS]['raw']['value']

        if SMARTAttribute.POWER_CYCLES in attr_lookup:
            attributes['power_cycles'] = attr_lookup[SMARTAttribute.POWER_CYCLES]['raw']['value']

        # Temperature fallback: if not found at top level, try SMART attribute
        # Use raw string or extract from lowest byte of raw value
        if attributes['temperature_c'] == 'N/A' and SMARTAttribute.TEMPERATURE in attr_lookup:
            temp_attr = attr_lookup[SMARTAttribute.TEMPERATURE]
            # Try raw string first (often has format "36 (Min/Max 2/56)")
            if 'raw' in temp_attr and 'string' in temp_attr['raw']:
                temp_str = temp_attr['raw']['string']
                # Extract first number from string
                import re
                match = re.match(r'(\d+)', temp_str)
                if match:
                    attributes['temperature_c'] = int(match.group(1))
            # Fallback: use lowest byte of raw value (current temp usually in byte 0)
            elif 'raw' in temp_attr and 'value' in temp_attr['raw']:
                raw_val = temp_attr['raw']['value']
                attributes['temperature_c'] = raw_val & 0xFF  # Extract lowest byte

        if SMARTAttribute.REALLOCATED_SECTORS in attr_lookup:
            attributes['reallocated_sectors'] = attr_lookup[SMARTAttribute.REALLOCATED_SECTORS]['raw']['value']

        if SMARTAttribute.PENDING_SECTORS in attr_lookup:
            attributes['pending_sectors'] = attr_lookup[SMARTAttribute.PENDING_SECTORS]['raw']['value']

        if SMARTAttribute.UNCORRECTABLE_SECTORS in attr_lookup:
            attributes['uncorrectable_sectors'] = attr_lookup[SMARTAttribute.UNCORRECTABLE_SECTORS]['raw']['value']

        if SMARTAttribute.RESERVED_SPACE in attr_lookup:
            attributes['reserved_space_pct'] = attr_lookup[SMARTAttribute.RESERVED_SPACE]['value']

        # Wear level - try multiple vendor-specific attributes
        # All these attributes report "remaining life %" (100=new, 0=dead)
        # Convert to "wear consumed %" by inverting: wear = 100 - remaining
        if SMARTAttribute.WEAR_LEVELING in attr_lookup:
            # Attr 177: Samsung Wear_Leveling_Count (100=new, decreases with wear)
            remaining = attr_lookup[SMARTAttribute.WEAR_LEVELING]['value']
            attributes['wear_level_pct'] = 100 - remaining
        elif SMARTAttribute.SSD_LIFE_LEFT in attr_lookup:
            # Attr 231: SSD_Life_Left (100=new, decreases with wear)
            remaining = attr_lookup[SMARTAttribute.SSD_LIFE_LEFT]['value']
            attributes['wear_level_pct'] = 100 - remaining
        elif SMARTAttribute.MEDIA_WEAROUT in attr_lookup:
            # Attr 233: Intel Media_Wearout_Indicator (100=new, 0=worn)
            remaining = attr_lookup[SMARTAttribute.MEDIA_WEAROUT]['value']
            attributes['wear_level_pct'] = 100 - remaining

        # Total data written - handle vendor-specific differences
        # Samsung/Intel: Attribute 241 is raw LBA count (multiply by 512)
        # WD/Kingston/SanDisk: Attribute 241 is already in GB
        # Crucial/Micron: Attribute 246 in 32 MiB units

        tb_written = None
        data_written_raw = None

        if SMARTAttribute.TOTAL_LBAS_WRITTEN in attr_lookup:
            attr_241 = attr_lookup[SMARTAttribute.TOTAL_LBAS_WRITTEN]
            raw_value = attr_241['raw']['value']

            # Heuristic: If value > 100,000, likely LBAs (Samsung/Intel style)
            # If value < 100,000, likely already in GB (WD/Kingston style)
            if raw_value > 100000:
                # Treat as LBA count - multiply by 512 bytes
                data_written_raw = raw_value
                tb_written = round((raw_value * 512) / (1024**4), 2)
            else:
                # Treat as GB already - convert to TB
                data_written_raw = raw_value
                tb_written = round(raw_value / 1024, 2)

        # Crucial/Micron fallback: check attribute 246 (Host_Writes_32MiB)
        elif SMARTAttribute.HOST_WRITES_32MIB in attr_lookup:
            attr_246 = attr_lookup[SMARTAttribute.HOST_WRITES_32MIB]
            raw_value = attr_246['raw']['value']
            # Value is in 32 MiB units
            data_written_raw = raw_value
            tb_written = round((raw_value * 32) / (1024 * 1024), 2)

        if data_written_raw is not None:
            attributes['total_lbas_written'] = data_written_raw
        if tb_written is not None:
            attributes['total_tb_written'] = tb_written

    except Exception as e:
        print(f"WARNING: Error extracting SMART attributes: {e}")

    return attributes


def get_health_status(smartctl_data):
    """Extract overall health status"""
    if not smartctl_data:
        return 'N/A'

    try:
        if 'smart_status' in smartctl_data:
            passed = smartctl_data['smart_status'].get('passed', False)
            return 'PASSED' if passed else 'FAILED'
    except Exception:
        pass

    return 'N/A'


def get_self_test_result(smartctl_data):
    """Extract last self-test result"""
    if not smartctl_data:
        return 'N/A'

    try:
        if 'ata_smart_data' in smartctl_data:
            self_test = smartctl_data['ata_smart_data'].get('self_test', {})
            status = self_test.get('status', {})
            if 'passed' in status:
                return 'PASSED' if status['passed'] else 'FAILED'
    except Exception:
        pass

    return 'N/A'


def generate_warnings(device_info, attributes, health_status):
    """Generate warning messages based on drive health metrics"""
    warnings = []

    # Check health status
    if health_status == 'FAILED':
        warnings.append('SMART_HEALTH_FAILED')

    # Check for sector errors
    try:
        if attributes['reallocated_sectors'] != 'N/A' and int(attributes['reallocated_sectors']) > 0:
            warnings.append(f"REALLOCATED_SECTORS:{attributes['reallocated_sectors']}")

        if attributes['pending_sectors'] != 'N/A' and int(attributes['pending_sectors']) > 0:
            warnings.append(f"PENDING_SECTORS:{attributes['pending_sectors']}")

        if attributes['uncorrectable_sectors'] != 'N/A' and int(attributes['uncorrectable_sectors']) > 0:
            warnings.append(f"UNCORRECTABLE_SECTORS:{attributes['uncorrectable_sectors']}")
    except (ValueError, TypeError):
        pass

    # Check temperature
    try:
        if attributes['temperature_c'] != 'N/A':
            temp = int(attributes['temperature_c'])
            if temp > 70:
                warnings.append(f"HIGH_TEMP:{temp}C")
    except (ValueError, TypeError):
        pass

    # Check wear level
    try:
        if attributes['wear_level_pct'] != 'N/A':
            wear = int(attributes['wear_level_pct'])
            if wear > 80:
                warnings.append(f"HIGH_WEAR:{wear}%")
    except (ValueError, TypeError):
        pass

    return ', '.join(warnings) if warnings else 'None'


def test_drive(device_path):
    """Test a single drive and return results dictionary"""
    print(f"\n{Colors.info('Testing drive:')} {Colors.header(device_path)}")
    print(Colors.info("Running smartctl commands..."))

    # Run smartctl with comprehensive options
    data, returncode = run_smartctl(device_path, ['-x'])

    if data is None:
        print(Colors.error("ERROR: Failed to get smartctl data"))
        return None

    # Extract all information
    device_info = extract_device_info(data)
    attributes = extract_smart_attributes(data)
    health_status = get_health_status(data)
    self_test_result = get_self_test_result(data)
    warnings = generate_warnings(device_info, attributes, health_status)

    # Compile results
    results = {
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'model': device_info['model'],
        'serial': device_info['serial'],
        'firmware': device_info['firmware'],
        'capacity_gb': device_info['capacity_gb'],
        'health_status': health_status,
        'power_on_hours': attributes['power_on_hours'],
        'power_cycles': attributes['power_cycles'],
        'temperature_c': attributes['temperature_c'],
        'total_lbas_written': attributes['total_lbas_written'],
        'total_tb_written': attributes['total_tb_written'],
        'wear_level_pct': attributes['wear_level_pct'],
        'reserved_space_pct': attributes['reserved_space_pct'],
        'reallocated_sectors': attributes['reallocated_sectors'],
        'pending_sectors': attributes['pending_sectors'],
        'uncorrectable_sectors': attributes['uncorrectable_sectors'],
        'self_test_result': self_test_result,
        'warnings': warnings
    }

    return results


def display_results(results):
    """Display test results to user with color coding"""
    if not results:
        return

    # Determine health status color
    health = results['health_status']
    if health == 'PASSED':
        health_colored = Colors.success(health)
    elif health == 'FAILED':
        health_colored = Colors.error(health)
    else:
        health_colored = health

    # Color temperature based on value
    temp = results['temperature_c']
    if temp != 'N/A':
        try:
            temp_val = int(temp)
            if temp_val > 70:
                temp_colored = Colors.error(f"{temp}°C")
            elif temp_val > 60:
                temp_colored = Colors.warning(f"{temp}°C")
            else:
                temp_colored = f"{temp}°C"
        except (ValueError, TypeError):
            temp_colored = f"{temp}°C"
    else:
        temp_colored = temp

    # Color wear level
    wear = results['wear_level_pct']
    if wear != 'N/A':
        try:
            wear_val = int(wear)
            if wear_val > 80:
                wear_colored = Colors.error(f"{wear}%")
            elif wear_val > 50:
                wear_colored = Colors.warning(f"{wear}%")
            else:
                wear_colored = Colors.success(f"{wear}%")
        except (ValueError, TypeError):
            wear_colored = f"{wear}%"
    else:
        wear_colored = wear

    # Color sector errors
    def color_sectors(value):
        if value != 'N/A':
            try:
                if int(value) > 0:
                    return Colors.error(str(value))
                else:
                    return Colors.success(str(value))
            except (ValueError, TypeError):
                pass
        return str(value)

    # Color warnings
    warnings = results['warnings']
    if warnings == 'None':
        warnings_colored = Colors.success(warnings)
    else:
        warnings_colored = Colors.error(warnings)

    print("\n" + Colors.header("="*60))
    print(Colors.header("DRIVE TEST RESULTS"))
    print(Colors.header("="*60))
    print(f"Model:           {Colors.info(results['model'])}")
    print(f"Serial:          {results['serial']}")
    print(f"Firmware:        {results['firmware']}")
    print(f"Capacity:        {results['capacity_gb']} GB")
    print(f"Health Status:   {health_colored}")
    print("-"*60)
    print(f"Power-On Hours:  {results['power_on_hours']}")
    print(f"Power Cycles:    {results['power_cycles']}")
    print(f"Temperature:     {temp_colored}")
    print(f"Total Written:   {results['total_tb_written']} TB")
    print(f"Wear Level:      {wear_colored}")
    print("-"*60)
    print(f"Reallocated:     {color_sectors(results['reallocated_sectors'])}")
    print(f"Pending:         {color_sectors(results['pending_sectors'])}")
    print(f"Uncorrectable:   {color_sectors(results['uncorrectable_sectors'])}")
    print("-"*60)
    print(f"Warnings:        {warnings_colored}")
    print(Colors.header("="*60))


def save_to_csv(results, csv_filename):
    """Save test results to CSV file"""
    # Define CSV columns
    fieldnames = [
        'timestamp', 'model', 'serial', 'firmware', 'capacity_gb',
        'health_status', 'power_on_hours', 'power_cycles', 'temperature_c',
        'total_lbas_written', 'total_tb_written', 'wear_level_pct',
        'reserved_space_pct', 'reallocated_sectors', 'pending_sectors',
        'uncorrectable_sectors', 'self_test_result', 'warnings'
    ]

    # Check if file exists to determine if we need to write header
    file_exists = Path(csv_filename).exists()

    try:
        with open(csv_filename, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write header if new file
            if not file_exists:
                writer.writeheader()

            # Write results row
            writer.writerow(results)

        print(f"\n{Colors.success('Results saved to:')} {csv_filename}")
        return True

    except Exception as e:
        print(Colors.error(f"ERROR: Failed to save to CSV: {e}"))
        return False


def main():
    """Main script execution"""
    print(Colors.header("="*60))
    print(Colors.header("SSD TESTING SCRIPT"))
    print(Colors.header("="*60))

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Generate CSV filename with timestamp
    csv_filename = f"ssd_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Main testing loop
    drives_tested = 0
    last_device = None  # Remember last device used

    while True:
        print("\n" + Colors.header("="*60))
        print(Colors.header("AVAILABLE BLOCK DEVICES"))
        print(Colors.header("="*60))

        # List available devices
        devices = list_block_devices()
        if not devices:
            print(Colors.warning("No suitable block devices found."))
            response = input("\nRefresh device list? (y/n): ").strip().lower()
            if response == 'y':
                continue
            else:
                break

        # Build list of device paths
        device_paths = [f"/dev/{name}" for name, _ in devices]

        # Check if last device is still available
        last_device_available = last_device and last_device in device_paths

        for name, size in devices:
            device_path = f"/dev/{name}"
            if last_device_available and device_path == last_device:
                print(f"  {Colors.info(device_path)} ({size}) {Colors.success('[LAST USED]')}")
            else:
                print(f"  {device_path} ({size})")

        # Get user device selection
        print()
        if last_device_available:
            print(f"Enter the device to test (or press Enter for {Colors.info(last_device)})")
        else:
            print("Enter the device to test (e.g., /dev/sdb)")
        print("Or type 'quit' to exit")

        device_input = input("Device: ").strip()

        # If empty input and last device available, use last device
        if not device_input and last_device_available:
            device_input = last_device
            print(f"Using: {Colors.info(device_input)}")

        if device_input.lower() in ['quit', 'exit', 'q']:
            break

        # Validate device path
        if not validate_device_path(device_input):
            print(Colors.error(f"ERROR: Invalid device path: {device_input}"))
            print("Expected format: /dev/sd[a-z]")
            continue

        # Test the drive
        results = test_drive(device_input)

        if results:
            # Display results
            display_results(results)

            # Save to CSV
            save_to_csv(results, csv_filename)

            drives_tested += 1
            last_device = device_input  # Remember this device

        # Ask to test another drive
        print("\n" + "="*60)
        response = input("Test another drive? (y/n): ").strip().lower()
        if response != 'y':
            break

    # Summary
    print("\n" + Colors.header("="*60))
    print(Colors.header("TESTING COMPLETE"))
    print(Colors.header("="*60))
    print(f"Total drives tested: {Colors.success(str(drives_tested))}")
    if drives_tested > 0:
        print(f"Results saved to: {Colors.info(csv_filename)}")
    print("\nThank you for using SSD Testing Script!")


if __name__ == '__main__':
    main()
