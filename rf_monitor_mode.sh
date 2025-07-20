#!/bin/bash


##### Sets Color variables #####
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
COLOR_SOURCE="$SCRIPT_DIR/colors.sh"
source $COLOR_SOURCE
################################

##### Make sure user is root #####
if [[ $EUID -ne 0 ]]; then
    echo -e "${YELLOW}Not running as root—relaunching with sudo...${NOCOLOR}"
    exec sudo "$0" "$@"
fi
################################

##### Unblocking / enabling all RF transmitters #####
sudo rfkill unblock all 
#####################################################



##### Stopping services that interfere with wifi capture #####

#Function to stop services safely 
stop_service() {
    local service_name=$1
    if systemctl is-active --quiet "$service_name"; then
        sudo systemctl stop "$service_name"
        echo -e "${GREEN}$service_name stopped.${NOCOLOR}"
    else
        echo -e "${YELLOW}$service_name is not running.${NOCOLOR}"
    fi
}

# Stop NetworkManager
stop_service "NetworkManager"

# Stop wpa_supplicant gracefully
if systemctl list-units --type=service | grep -q "wpa_supplicant"; then
    sudo systemctl stop wpa_supplicant
    echo -e "${GREEN}wpa_supplicant stopped.${NOCOLOR}"
else
    if pgrep -x "wpa_supplicant" > /dev/null; then
        sudo killall wpa_supplicant
        echo -e "${GREEN}wpa_supplicant killed.${NOCOLOR}"
    else
        echo -e "${YELLOW}wpa_supplicant is not running.${NOCOLOR}"
    fi
fi

# Stop avahi-daemon
stop_service "avahi-daemon"

###############################################################



##### Setting wifi interfaces to monitor mode #####

# Function that sets all (802.11) interfaces to monitor
set_monitor_mode() {
    local interface=$1
    echo -e "${YELLOW}Setting $interface to monitor mode...${NOCOLOR}"

    sudo ip link set $interface down &> /dev/null || { echo -e "${RED}Failed to bring $interface down.${NOCOLOR}"; return 1; }
    sudo iw $interface set monitor none &> /dev/null || { echo -e "${RED}Failed to set $interface to monitor mode.${NOCOLOR}"; return 1; }
    sudo ip link set $interface up &> /dev/null || { echo -e "${RED}Failed to bring $interface up.${NOCOLOR}"; return 1; }

    local mode=$(iw dev $interface info | grep type | awk '{print $2}')
    if [ "$mode" == "monitor" ]; then
        echo -e "${GREEN}$interface is now in monitor mode.${NOCOLOR}"
        return 0
    else
        echo -e "${RED}Failed to set $interface to monitor mode.${NOCOLOR}"
        return 1
    fi
}

# Check if NetworkManager is running and stop it if active
if pgrep -xcho -e  "NetworkManager" > /dev/null; then
    sudo systemctl stop NetworkManager
    echo -e "${GREEN}NetworkManager stopped.${NOCOLOR}"
else
    echo -e "${YELLOW}NetworkManager is not running.${NOCOLOR}"
fi

# Check if wpa_supplicant is running and kill it if active
if pgrep -x "wpa_supplicant" > /dev/null; then
    sudo killall wpa_supplicant
    echo -e "${GREEN}wpa_supplicant killed.${NOCOLOR}"
else
    echo -e "${YELLOW}wpa_supplicant is not running.${NOCOLOR}"
fi

# Check if avahi-daemon is running and kill it if active
if pgrep -x "avahi-daemon" > /dev/null; then
    sudo systemctl stop avahi-daemon
    if ! pgrep -x "avahi-daemon" > /dev/null; then
        echo -e "${GREEN}avahi-daemon has been stopped successfully.${NOCOLOR}"
    else
        echo -e "${RED}Failed to stop avahi-daemon.${NOCOLOR}"
    fi
else
    echo -e "${GREEN}avahi-daemon is not running.${NOCOLOR}"
fi

# Get the names of wireless interfaces and execute set_monitor_mode
interfaces=($(ip a 2>/dev/null | awk '/^[0-9]*: wlp[0-9a-zA-Z]*/ {sub(/:$/, "", $2); print $2}'))

if [ ${#interfaces[@]} -eq 0 ]; then
    echo -e "${RED}No wireless interfaces found.${NOCOLOR}"
    exit 1
fi

for interface in "${interfaces[@]}"; do
    set_monitor_mode $interface
done

exit 0
