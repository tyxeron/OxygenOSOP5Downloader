import os
import re
import subprocess
import time
import requests
import sys
from datetime import datetime
import zipfile

import click
from progressbar import Bar, Percentage, ProgressBar
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def check_zip_file(filename):
    return zipfile.ZipFile(filename).testzip() is None


def reboot(mode):
    reboot_modes = ['recovery', 'system']
    if mode not in reboot_modes:
        sys.exit("Wrong mode for function reboot. Only 'recovery' and 'system' allowed")
    if not check_device_available():
        return False
    if subprocess.check_call(
            ['adb', 'reboot', mode]) == 0:
        # Wait for device to boot into right mode
        print("Waiting for device to boot into mode",mode)
        while check_device_available(False) != mode:
            time.sleep(1)
        print("Waiting for device to boot into mode", mode, "done.")
        return True
    else:
        return False


def push_firmware(firmware_name):
    if check_device_available() != "recovery":
        while not reboot("recovery"):
            pass
    if click.confirm('Enter the passcode on the phone to unlock. The confirm here by entering "y"', default=False):
        if subprocess.check_call(
                ['adb', 'push', firmware_name, '/storage/']) == 0:
            return True
        else:
            return False
    else:
        return False


def check_device_available(prompt=True):
    patterns = [("recovery", "recovery"), ("device", "system")]
    while True:
        output = subprocess.check_output(["adb", "devices"])
        output = output.decode('utf-8')
        matches = re.findall(".+?\n", output)  # extract second line of output
        if len(matches) == 1:  # No devices
            if prompt:
                if not click.confirm('Device not found, do you want to search again? Else Aborting.',
                                     default=False):
                    sys.exit('Closing program')
                else:
                    continue
            else:
                return None

        first_device = matches[1]
        for pattern, mode in patterns:
            is_available_in_mode = re.match(".*{0}.*\n".format(pattern), first_device)
            if not is_available_in_mode:
                continue
            else:
                return mode


def run_extractor(filename):
    if os.path.exists("firmware-{}".format(filename)):
        print("Found already extracted firmware. Checking for integrity")
        if check_zip_file("firmware-{}".format(filename)):
            return True  # File exists and is healthy

    if subprocess.check_call(
            ['generate-flashable-firmware-zip.sh', filename]) == 0:
        os.remove(filename)
        return True
    else:
        return False


def get_size_on_disk(filename):
    if os.path.isfile(filename):
        st = os.stat(filename)
        return int(st.st_size / 1000_000)
    else:
        return -1


def get_total_size(link, retry_time=3):
    response = requests.head(link)
    while response.status_code != 200:
        time.sleep(retry_time)
        response = requests.head(link)
    file_size = response.headers['content-length']
    return int(int(file_size) / 1000_000)


def is_downloaded(file_path, link_name):
    file_path_part = file_path + ".part"
    if os.path.exists(file_path) or os.path.exists(file_path_part):
        if get_size_on_disk(file_path) == get_total_size(link_name) and check_zip_file(file_path):
            return True
        else:
            if click.confirm('File is incomplete: Do you want to remove and download it again?', default=False):
                os.remove(file_path_part)
                os.remove(file_path)
            else:
                sys.exit('Closing program')
    return False


def backup_phone():
    if check_device_available() != "system":
        while not reboot("system"):
            pass
    backup_name = "OnePlus5_" + datetime.today().strftime('%d-%m-%Y-%H:%M:%S') + ".backup"
    command = ['adb', 'backup', '-apk', '-obb', '-shared', '-all', '-system', '-f',
               backup_name]
    backup_process = subprocess.Popen(command)
    return backup_process


def wait_backup(backup_process):
    while backup_process.poll() is None:
        time.sleep(1)
    return backup_process.returncode == 0


def flash_new_firmware(firmware_name):
    return push_firmware(firmware_name)


def wait_download(file_path, link_name):
    if get_size_on_disk(file_path) == get_total_size(link_name):
        return

    total_size = get_total_size(link_name)
    part_file_name = file_path + '.part'
    while not os.path.exists(file_path):
        time.sleep(1)
    if os.path.isfile(file_path):
        print("Download started!")
        pbar = ProgressBar(widgets=[Percentage(), Bar()], maxval=total_size).start()
        while os.path.exists(part_file_name):
            time.sleep(1)
            size_on_disk = get_size_on_disk(part_file_name)
            if size_on_disk != -1:
                pbar.update(size_on_disk)
        pbar.finish()
        print("Download done!")
        return
    else:
        raise ValueError("%s isn't a file!" % file_path)


def main():
    # Oxygen OS base URL
    url = 'https://www.oneplus.com/support/softwareupgrade/details?code=PM1574156143164'

    # Firefox Profile to auto download java archive
    profile = webdriver.FirefoxProfile()
    profile.set_preference('browser.download.folderList', 2)
    profile.set_preference('browser.download.manager.showWhenStarting', False)
    profile.set_preference('browser.download.dir', os.getcwd())
    profile.set_preference("browser.download.panel.shown", False)
    profile.set_preference("browser.helperApps.neverAsk.openFile", "application/java-archive")
    profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/java-archive")

    # Needed for headless operation
    options = Options()
    options.headless = True

    # Timeout for initial connection for webdriver
    timeout = 5

    # Background process to perform backup if needed
    backup_process = None

    # Firefox selenium webdriver
    driver = webdriver.Firefox(options=options, firefox_profile=profile)
    driver.get(url)

    try:
        # Get the download button and version number for Oxygen OS
        banner = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.CLASS_NAME, 'banner-desc')))
        download_button = banner.find_element_by_class_name("download-btn")
        link_name = download_button.get_attribute("href")
        file_name = re.sub('https://oxygenos.oneplus.net/', '', link_name)
        file_location = os.getcwd() + '/' + file_name
        version = banner.find_elements_by_class_name("info")[1].find_element_by_tag_name("p")

        # Ask if update should be downloaded
        if not is_downloaded(file_location, link_name):
            if click.confirm('Version ' + version.text + ' can be downloaded, do you want to continue?', default=False):
                download_button.click()
        else:
            print("Already downloaded the newest version")

        # Possibly backup phone via adb
        if click.confirm('Do you want to backup your phone? This will take awhile. (Note: does only backup apps and '
                         'settings)', default=False):
            backup_process = backup_phone()

        # Wait for download finished
        wait_download(file_location, link_name)

        # If doing backup wait for it to finish
        if backup_process is not None:
            while not wait_backup(backup_process):
                print("Backup unsuccessful")
                if not click.confirm('Do you want to retry the backup',
                                     default=False):
                    print("Backup aborted")
                    break
            else:
                print("Backup successful")

        print("Running Firmware Extraction tool")
        if run_extractor(file_name):
            print("Running Firmware Extraction tool done.")
        else:
            sys.exit("Firmware Extraction tool error")

        if click.confirm('Do you want to flash the newest version now?', default=False):
            if flash_new_firmware(firmware_name="firmware-" + file_name):
                print("You can now install the new firmware in TWRP. Go to 'Install', click on 'firmware-" + file_name + "' and swipe to confirm. After that reboot to System and your done.")
            else:
                sys.exit("Could not push firmware to phone.")

    except TimeoutException:
        print("Loading took too much time! Check your internet connection")

    driver.close()


if __name__ == "__main__":
    main()
