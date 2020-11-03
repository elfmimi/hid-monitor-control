hid-monitor-control.py
======================

* requires hidapi package: https://pypi.org/project/hidapi/

* or alternatively hid package: https://pypi.org/project/hid/

* Python 2 + hidapi does not work on Windows ?

* hidapi may require installing libusb-1.0 package on Linux .

* hid on Windows requires hidapi.dll .
  https://github.com/libusb/hidapi/releases/

* hid on MSYS2 MinGW64 requires libhidapi-0.dll
  https://packages.msys2.org/package/mingw-w64-x86_64-hidapi

* hid may require installing libhidapi-libusb0 package on Linux .

* requires root privilege or adjustment to udev/rules on Linux .

* try:> python hid-monitor-control.py switcher

  This will achieve direct switching with a single press of touch buttons.
