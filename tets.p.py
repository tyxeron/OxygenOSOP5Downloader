import subprocess
import re
import click
import sys


def reboot(mode):
    if not check_device_available():
        return
    reboot_modes = ['recovery', 'system']
    if mode not in reboot_modes:
        sys.exit("Wrong mode for function reboot. Only 'recovery' and 'system' allowed")
    if subprocess.check_call(
            ['adb', 'reboot', mode]) == 0:
        return True
    else:
        return False



def check_device_available():
    patterns = [("recovery", "recovery"), ("device", "system")]
    while True:
        output = subprocess.check_output(["adb", "devices"])
        output = output.decode('utf-8')
        matches = re.findall(".+?\n", output)  # extract second line of output
        if len(matches) == 1:  # No devices
            if not click.confirm('Device not found, do you want to search again? Else Aborting.',
                                 default=False):
                exit(-1)
            else:
                continue

        first_device = matches[1]
        for pattern, mode in patterns:
            is_available_in_mode = re.match(".*{0}.*\n".format(pattern), first_device)
            if not is_available_in_mode:
                continue
            else:
                return mode


print(check_device_available())
reboot("system")