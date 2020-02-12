import os
import re
import subprocess
import time
import requests
from datetime import datetime


import click
from progressbar import Bar, Percentage, ProgressBar

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def reboot(flag=0):
    # flag determines reboot variant:
    # 0: Recovery
    # 1: Bootloader
    # 2: System
    if not check_device_available():
        return
    reboot_modes = ['recovery', 'bootloader', 'system']
    reboot_mode = reboot_modes[flag]
    if subprocess.check_call(
            ['adb', 'reboot', reboot_mode]) == 0:
        return True
    else:
        return False


def push_firmware(firmware_name):
    if not check_device_available():
        return
    if subprocess.check_call(
            ['adb', 'push', firmware_name, '/storage/']) == 0:
        return True
    else:
        return False


def check_device_available():
    output = subprocess.check_output(["adb", "devices"])
    output = output.decode("utf-8")
    print(output)
    while not click.confirm('Is your device listed?', default=False):
        if click.confirm('Abort? If not make sure the phone is powered on and reconnect it. Then and enter "N"',
                         default=False):
            return False
    else:
        print("Do not disconnect your device. ADB command imminent")
        return True


def run_extractor(filename):
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
        if get_size_on_disk(file_path) == get_total_size(link_name):
            return True
        else:
            if click.confirm('File is incomplete: Do you want to remove and download it again?', default=False):
                os.remove(file_path_part)
                os.remove(file_path)
            else:
                print('Closing program')
                exit(0)
    return False


def backup_phone():
    #TODO add save point for extracted firmware
    if not check_device_available():
        return None
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
    if reboot():
        return push_firmware(firmware_name)

    return False


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
            pbar.update(get_size_on_disk(part_file_name))
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
        if click.confirm('Do you want to backup your phone? (Note: does only backup apps and settings)',
                         default=False):
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
            print("Firmware Extraction tool error. Aborting")
            exit(-1)

        if click.confirm('Do you want to flash the newest version now?', default=False):
            if flash_new_firmware(firmware_name=file_name):
                print("You can now install the new firmware in TWRP. After that reboot to System and your done.")
            else:
                print("Could not push firmware to phone. Aborting")
                exit(-1)

    except TimeoutException:
        print("Loading took too much time! Check your internet connection")

    driver.close()


if __name__ == "__main__":
    main()
