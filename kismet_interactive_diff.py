import json
import argparse
import sys
import os
import subprocess
import shutil
from collections import defaultdict

# --- Style and Color constants ---
class Style:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'

def check_command_exists(command):
    """Check if a command-line utility is available in the system's PATH."""
    if not shutil.which(command):
        print(f"{Style.RED}{Style.BOLD}Error: Required command '{command}' not found in your PATH.{Style.RESET}")
        print("Please ensure the Kismet server tools are installed and accessible.")
        sys.exit(1)
    print(f"{Style.GREEN}[✓] Found required utility: {command}{Style.RESET}")

def run_conversion_prompt(kismet_file):
    """
    Handles the logic for converting a .kismet file to .json.
    Prompts the user before taking action.
    """
    if not kismet_file.endswith('.kismet'):
        print(f"{Style.RED}{Style.BOLD}Error: Input file must be a .kismet log file.{Style.RESET}")
        sys.exit(1)

    json_file = kismet_file.replace('.kismet', '.json')
    run_command = True

    if os.path.exists(json_file):
        overwrite = input(f"{Style.YELLOW}[?] Output file '{json_file}' already exists. Use it? (Y/n): {Style.RESET}").lower().strip()
        if overwrite == '' or overwrite == 'y':
            print(f"{Style.GREEN}[*] Using existing file: {json_file}{Style.RESET}")
            run_command = False

    if run_command:
        command = f"kismet_log_to_json --in \"{kismet_file}\" --out \"{json_file}\""
        
        print(f"\n{Style.BLUE}The script needs to run the following command:{Style.RESET}")
        print(f"  {Style.BOLD}{command}{Style.RESET}")
        confirm = input(f"{Style.YELLOW}[?] Do you want to proceed? (Y/n): {Style.RESET}").lower().strip()

        if confirm == '' or confirm == 'y':
            try:
                print(f"[*] Running conversion for '{kismet_file}'...")
                subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                print(f"{Style.GREEN}[✓] Successfully created '{json_file}'{Style.RESET}")
            except subprocess.CalledProcessError as e:
                print(f"{Style.RED}{Style.BOLD}Error during conversion!{Style.RESET}")
                print(f"  Return Code: {e.returncode}")
                print(f"  Stderr: {e.stderr.strip()}")
                sys.exit(1)
        else:
            print(f"{Style.RED}Conversion cancelled by user. Exiting.{Style.RESET}")
            sys.exit(0)
            
    return json_file

# --- Previous analysis functions (unchanged) ---
def _process_device(device, aps, clients, probed_ssid_map):
    mac = device.get('kismet_device_base_macaddr')
    dev_type = device.get('kismet_device_base_type')
    if not mac or not dev_type:
        return
    if dev_type == 'Wi-Fi AP':
        ssid = device.get('kismet_device_base_name', 'N/A')
        channel = device.get('kismet_common_channel', 'N/A')
        crypt_set = device.get('dot11_network_crypt_set', 'Unknown')
        aps[mac] = {'ssid': ssid, 'channel': channel, 'crypt': str(crypt_set)}
    elif 'Wi-Fi' in dev_type and dev_type != 'Wi-Fi AP':
        probes = set(device.get('dot11_client_probed_ssid_map', {}).keys())
        clients[mac] = {'probed_ssids': probes}
        for probe in probes:
            if probe:
                probed_ssid_map[probe].add(mac)

def parse_kismet_log(file_path):
    """
    Parses a Kismet JSONL file and returns structured data about the devices.
    """
    aps = {}
    clients = {}
    probed_ssid_map = defaultdict(set)
    try:
        with open(file_path, 'r') as f:
            for line in f:
                try:
                    device = json.loads(line)
                    _process_device(device, aps, clients, probed_ssid_map)
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        print(f"{Style.RED}Error: JSON file not found at '{file_path}'. Conversion might have failed.{Style.RESET}")
        sys.exit(1)
    return aps, clients, probed_ssid_map

def parse_args():
    parser = argparse.ArgumentParser(
        description="Interactively compare two Kismet logs, with prompts for file conversion.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('baseline_file', help="Path to the baseline .kismet log file.")
    parser.add_argument('comparison_file', help="Path to the comparison .kismet log file.")
    return parser.parse_args()

def report_new_and_missing(baseline_aps, comp_aps, baseline_clients, comp_clients):
    new_aps = comp_aps.keys() - baseline_aps.keys()
    missing_aps = baseline_aps.keys() - comp_aps.keys()
    new_clients = comp_clients.keys() - baseline_clients.keys()
    missing_clients = baseline_clients.keys() - comp_clients.keys()

    print("\n--- 🛰️ New and Missing Access Points ---")
    print(f"[+] New APs: {len(new_aps)}")
    for mac in sorted(new_aps):
        print(f"  - {mac} (SSID: {comp_aps[mac]['ssid']})")
    print(f"[-] Missing APs: {len(missing_aps)}")
    for mac in sorted(missing_aps):
        print(f"  - {mac} (SSID: {baseline_aps[mac]['ssid']})")

    print("\n--- 💻 New and Missing Clients ---")
    print(f"[+] New Clients: {len(new_clients)}")
    for mac in sorted(new_clients):
        print(f"  - {mac}")
    print(f"[-] Missing Clients: {len(missing_clients)}")
    for mac in sorted(missing_clients):
        print(f"  - {mac}")

def report_environmental_changes(baseline_aps, comp_aps, baseline_clients, comp_clients):
    print("\n" + "="*50 + "\n")
    print("--- 🔄 Environmental Changes for Common Devices ---")
    _report_ap_changes(baseline_aps, comp_aps)
    _report_client_changes(baseline_clients, comp_clients)

def _report_ap_changes(baseline_aps, comp_aps):
    common_aps = baseline_aps.keys() & comp_aps.keys()
    print(f"\n[*] Analyzing {len(common_aps)} common Access Points for changes...")
    for mac in sorted(common_aps):
        base_ap = baseline_aps[mac]
        comp_ap = comp_aps[mac]
        changes = _get_ap_changes(base_ap, comp_ap)
        if changes:
            print(f"  - AP: {mac} (SSID: {base_ap['ssid']})")
            for change in changes:
                print(f"    - {change}")

def _get_ap_changes(base_ap, comp_ap):
    changes = []
    if base_ap['ssid'] != comp_ap['ssid']:
        changes.append(f"SSID changed: '{base_ap['ssid']}' -> '{comp_ap['ssid']}'")
    if base_ap['channel'] != comp_ap['channel']:
        changes.append(f"Channel changed: {base_ap['channel']} -> {comp_ap['channel']}")
    if base_ap['crypt'] != comp_ap['crypt']:
        changes.append(f"Encryption changed: {base_ap['crypt']} -> {comp_ap['crypt']}")
    return changes

def _report_client_changes(baseline_clients, comp_clients):
    common_clients = baseline_clients.keys() & comp_clients.keys()
    print(f"\n[*] Analyzing {len(common_clients)} common Clients for changes...")
    for mac in sorted(common_clients):
        base_client, comp_client = baseline_clients[mac], comp_clients[mac]
        added_probes, removed_probes = _get_client_probe_changes(base_client, comp_client)
        if added_probes or removed_probes:
            print(f"  - Client: {mac}")
            if added_probes:
                print(f"    - Started probing for: {', '.join(sorted(added_probes))}")
            if removed_probes:
                print(f"    - Stopped probing for: {', '.join(sorted(removed_probes))}")

def _get_client_probe_changes(base_client, comp_client):
    added_probes = comp_client['probed_ssids'] - base_client['probed_ssids']
    removed_probes = base_client['probed_ssids'] - comp_client['probed_ssids']
    return added_probes, removed_probes

def report_probed_ssid_analysis(baseline_probes, comp_probes):
    print("\n" + "="*50 + "\n")
    print("--- 📡 Probed SSID Analysis ---")
    newly_probed_ssids = comp_probes.keys() - baseline_probes.keys()
    no_longer_probed_ssids = baseline_probes.keys() - comp_probes.keys()

    print(f"\n[+] New SSIDs being probed for: {len(newly_probed_ssids)}")
    for ssid in sorted(newly_probed_ssids):
        clients_probing = ', '.join(sorted(comp_probes[ssid]))
        print(f"  - '{ssid}' (by: {clients_probing})")
    print(f"\n[-] SSIDs no longer being probed for: {len(no_longer_probed_ssids)}")
    for ssid in sorted(no_longer_probed_ssids):
        print(f"  - '{ssid}'")

def main():
    args = parse_args()
    check_command_exists('kismet_log_to_json')
    baseline_json_path = run_conversion_prompt(args.baseline_file)
    comparison_json_path = run_conversion_prompt(args.comparison_file)

    print("\n--- 🔍 Processing Kismet Logs ---")
    baseline_aps, baseline_clients, baseline_probes = parse_kismet_log(baseline_json_path)
    comp_aps, comp_clients, comp_probes = parse_kismet_log(comparison_json_path)

    report_new_and_missing(baseline_aps, comp_aps, baseline_clients, comp_clients)
    report_environmental_changes(baseline_aps, comp_aps, baseline_clients, comp_clients)
    report_probed_ssid_analysis(baseline_probes, comp_probes)

if __name__ == "__main__":
    main()