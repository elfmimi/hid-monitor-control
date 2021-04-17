# from __future__ import print_function

import sys
import hid
import time
import ctypes
import struct

device_id_pairs = [
    [0x056D, 0x4014], # EV2750
    [0x056D, 0x4059], # EV2760
    [0x056D, 0x4065], # EV3895
]

def get_input_source_table(model):
    table = {
        'EV2750': {
            'DVI': 0x0200,
            'DisplayPort': 0x0300,
            'HDMI': 0x0400 },
        'EV2760': {
            'DVI': 0x0200,
            'DisplayPort1': 0x0300,
            'DisplayPort2': 0x0301,
            'HDMI': 0x0400 },
         'EV3895': {
            'DisplayPort': 0x0300,
            'USB-C': 0x0301,
            'HDMI1': 0x0400,
            'HDMI2': 0x0401 },
    }
    return table[model]

def lookup_input_source_alias(input):
    table = {
        'DP': 'DisplayPort',
        'DP1': 'DisplayPort1',
        'DP2': 'DisplayPort2',
        'TypeC': 'USB-C',
        'Type-C': 'USB-C',
        'USB': 'USB-C',
        'USBC': 'USB-C',
    }
    for k in table:
        if k.lower() == input.lower():
            return table[k]
    return input

# We are going to patch some methods of hid module for compatibility.
if 'Device' in dir(hid):
    # make send_feature_report accept a simple array of integers
    _orig_send_feature_report = hid.Device.send_feature_report
    def send_feature_report(self, buf):
        buf = bytes(bytearray(buf))
        _orig_send_feature_report(self, buf)
    hid.Device.send_feature_report = send_feature_report
    # get_feature_report of hid module has a bug when used with Python 2
    # _orig_get_feature_report = hid.Device.get_feature_report
    def get_feature_report(self, report_id, size):
        data = ctypes.create_string_buffer(size)

        # Pass the id of the report to be read.
        data[0] = bytes(bytearray((report_id,)))

        # access private member and private method
        __dev = self._Device__dev
        __hidcall = hid.Device._Device__hidcall

        size = __hidcall(self,
            hid.hidapi.hid_get_feature_report, __dev, data, size)
        tmp = data.raw[:size]

        # and convert the return value back into simple array of integers
        if type(tmp) == str:
            tmp = map(ord, tmp)
        return tmp
    hid.Device.get_feature_report = get_feature_report

def set_val(dev, num, val):
    buf = [0x02, 0x01, 0xFF, num & 255, num >> 8, 0x00, 0x00, val & 255, val >> 8]
    buf += [0] * (40 - len(buf)) # Windows need this stuffing
    dev.send_feature_report(buf)

    tmp = dev.get_feature_report(7, 8)
    if tmp[0] != 0x07:
        raise Exception
    for i in range(1,7):
        if tmp[i] != buf[i]:
            raise Exception

def get_val(dev, num):
    buf = [0x03, 0x01, 0xFF, num & 255, num >> 8]
    buf += [0] * (40 - len(buf)) # Windows need this stuffing
    dev.send_feature_report(buf)

    tmp = dev.get_feature_report(3, 40)
    for i in range(7):
        if tmp[i] != buf[i]:
            raise Exception
    val = tmp[8] * 256 + tmp[7]

    tmp = dev.get_feature_report(7, 8)
    if tmp[0] != 0x07:
        raise Exception
    for i in range(1,7):
        if tmp[i] != buf[i]:
            raise Exception

    return val

def print_usage(input_source_table=None):
    print("Usage: python hid-monitor-control.py <INPUT> [INPUT2]")
    if input_source_table:
        print("       INPUT = " + " | ".join(input_source_table.keys()))
    print("")
    print("       python hid-monitor-control.py switcher")

# enumerate USB devices

if False:
    for des in hid.enumerate():
        keys = list(des.keys())
        keys.sort()
        for key in keys:
            print("%s : %s" % (key, des[key]))
        print("")

# try opening a device, then perform write and read

des = None
for d in hid.enumerate():
    if [d['vendor_id'], d['product_id']] in device_id_pairs:
        des = d
        break

# des = { 'vendor_id': 0x056D, 'product_id': 0x4059 }

if not des:
    print("No Monitor device found.")
    exit(1) 

# print(des)

try:
    # print("Opening the device")

    if 'device' in dir(hid):
        dev = hid.device()
        # dev.open(0x056d, 0x4059)
        dev.open(des['vendor_id'], des['product_id'])
        dev.set_nonblocking(1)
        # print("Manufacturer: %s" % dev.get_manufacturer_string())
        # print("Product: %s" % dev.get_product_string())
        # print("Serial No: %s" % dev.get_serial_number_string())

    if 'Device' in dir(hid):
        # dev = hid.Device(0x056d, 0x4059)
        dev = hid.Device(des['vendor_id'], des['product_id'])
        dev.nonblocking = True
        # print("Manufacturer: %s" % dev.manufacturer)
        # print("Product: %s" % dev.product)
        # print("Serial No: %s" % dev.serial)

    tmp = dev.get_feature_report(0x08, 25)
    if tmp[0] != 0x08 or len(tmp) < 25:
        raise Exception
    serial_number = struct.pack('B' * 8, *tmp[1:9]).decode('ascii')
    model_number = struct.pack('B' * 16, *tmp[9:25]).decode('ascii').strip()
    # print(serial_number)
    # print(product_number)

    input_source_table = get_input_source_table(model_number)
    # default to EV2760
    if not input_source_table:
        input_source_table = get_input_source_table('EV2760')

    if len(sys.argv) == 1:
        print("%s (S/N: %s)"%(model_number, serial_number))
        num = 1
        if get_val(dev, 0x40) != 0:
            num = 2
        sels = [None] * num
        for i in range(num):
            if num > 1:
                set_val(dev, 0xF9, i)
            val = get_val(dev, 0x48)
            for k in input_source_table:
                if input_source_table[k] == val:
                    val = k
                    break
            if type(val) is int:
                val = "Unknown(%04X)" % val
            sels[i] = val
        print("Input: %s" % ' '.join(sels))
        print("")
        print_usage(input_source_table)
        exit(0)
    
    if len(sys.argv) > 3:
        print_usage(input_source_table)
        exit(1)

    if len(sys.argv) > 1 and sys.argv[1].lower() != 'switcher':
        num = len(sys.argv) - 1
        if num == 1:
            set_val(dev, 0x40, 0)
        elif num == 2:
            set_val(dev, 0x40, 1)
        sels = [None] * num
        for i in range(num):
            sel = sys.argv[i+1]
            sel = lookup_input_source_alias(sel)
            for key in input_source_table:
                if key.lower() == sel.lower():
                    sel = input_source_table[key]
                    break
            if type(sel) is int:
                sels[i] = sel
            else:
                print_usage(input_source_table)
                exit(1)
        for i in range(num):
            if num > 1:
                set_val(dev, 0xF9, i)
            set_val(dev, 0x48, sels[i])
        exit(0)

    # wait
    # time.sleep(0.05)

# event loop
    while True:
        dat = dev.read(64)
        if dat:
            if type(dat) == str:
                dat = map(ord, dat)
            print(','.join(map(lambda x: '0x%02X' % x, dat)))
            if bytearray(dat[0:5]) == b'\x03\x01\xFF\x3D\x00':
                sel = None
                btn = dat[8] * 256 + dat[7]
                if btn == 0x20:
                    sel = 'DisplayPort1' if 'DisplayPort1' in input_source_table else 'DisplayPort'
                elif btn == 0x10:
                    sel = 'DisplayPort2' if 'DisplayPort2' in input_source_table else None
                elif btn == 0x08:
                    sel = 'HDMI'
                elif btn == 0x04:
                    sel = 'DVI'
                if sel:
                    set_val(dev, 0x48, input_source_table[sel])

    # print("Closing the device")
    dev.close()

except IOError as ex:
    print(ex)
    print("Exit")
    exit(1)

print("Done")
