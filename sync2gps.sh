#!/bin/bash

# --- Color definitions ---
SCRIPT_DIR=$(dirname $(readlink -f "$0"))
COLOR_SOURCE="$SCRIPT_DIR/colors.sh"
source $COLOR_SOURCE

# --- ensure we’re running as root ---
if [[ $EUID -ne 0 ]]; then
    echo -e "${YELLOW}Not running as root—relaunching with sudo...${NOCOLOR}"
    exec sudo "$0" "$@"
fi

# --- find all USB serial ports ---
devices=(/dev/ttyUSB*)
if [ ${#devices[@]} -eq 0 ]; then
    echo -e "${RED}No /dev/ttyUSB* devices found.${NOCOLOR}"
    exit 1
fi

echo -e "${CYAN}Scanning for a GPS fix on available ports (4800 baud only)...${NOCOLOR}"

found_line=""
for dev in "${devices[@]}"; do
    [ -e "$dev" ] || continue

    echo -ne "${BLUE}  Testing $dev at 4800… ${NOCOLOR}"
    stty -F "$dev" raw speed 4800 -echo

    # read up to 10 lines, looking for GPRMC with field-3 == "A"
    for i in {1..100}; do
        if read -r -t 2 line < "$dev"; then
            if [[ $line == \$GPRMC* ]]; then
                IFS=',' read -ra F <<< "$line"
                if [[ "${F[2]}" == "A" ]]; then
                    echo -e "${GREEN}valid fix${NOCOLOR}"
                    selected_dev="$dev"
                    found_line="$line"
                    break 2
                else
                    echo -ne "${ORANGE}no fix… ${NOCOLOR}"
                fi
            fi
        fi
    done
    echo -e "${ORANGE}none${NOCOLOR}"
done

if [ -z "$found_line" ]; then
    echo -e "${RED}No valid GPS fix found on any port.${NOCOLOR}"
    exit 1
fi

echo -e "${GREEN}Got fix on $selected_dev.${NOCOLOR}"
echo -e "${LIGHTBLUE}Sentence: $found_line${NOCOLOR}"

# --- parse that one good sentence and update the clock ---
IFS=',' read -ra F <<< "$found_line"
t="${F[1]%%.*}"    # time hhmmss(.sss)
d="${F[9]}"        # date ddmmyy

# sanity check
if [[ ${#t} -ne 6 || ${#d} -ne 6 ]]; then
    echo -e "${RED}Malformed time/date fields; aborting.${NOCOLOR}"
    exit 1
fi

hh="${t:0:2}" mm="${t:2:2}" ss="${t:4:2}"
dd="${d:0:2}" mo="${d:2:2}" yy="${d:4:2}"
year="20$yy"

ts="${year}-${mo}-${dd} ${hh}:${mm}:${ss}"
echo -e "${BLUE}Updating system time to UTC $ts${NOCOLOR}"
if date -u -s "$ts"; then
    echo -e "${GREEN}Clock set.${NOCOLOR}"
else
    echo -e "${RED}Failed to set clock.${NOCOLOR}"
fi
