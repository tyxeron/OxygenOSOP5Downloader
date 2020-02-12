# OxygenOSOP5Downloader
A work in progress downloader/installer for Oxygen OS for the **Oneplus 5** (Possibly more in the future). This will download the newest Oxygen OS image from https://www.oneplus.com/, extract the firmware and push it to your Oneplus 5 for you to install.
Linux only.
# Usage
Required:
* `pip3 install click`
* `pip3 install progressbar`
* `pip3 install selenium`
* [adb](https://developer.android.com/studio/command-line/adb)
* [gecko driver](https://github.com/mozilla/geckodriver)  
* [Firmware Extraction tool](https://github.com/tyxeron/Oneplus5FirmwareExtractor)

Note: geckodriver, adb and extraction tool must be in the PATH environment variable.

Run `python3 downloader.py`. Make sure that you have internet connection and only **one** device connected via adb (run `adb devices` to confirm)
# TODO
* Add save point for extracted firmware
* Add more sanity checks
* Enable ADB sideload instead of push and manual install
* Add option to stop backup
* Resume download

# Disclaimer
Provided as is. No guarantee for correctness or liability for damage.
