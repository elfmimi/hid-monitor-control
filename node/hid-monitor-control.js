#!/usr/bin/env node

// export NODE_PATH=`npm root -g`

const { strict } = require('assert');
const util = require('util');

// const { HID } = require('node-hid');

const assert = require('assert').strict;

HID = require('node-hid');
HID.setDriverType('libusb');

device_id_pairs = [
    (0x056D, 0x4059) // EV2760
]

function get_input_source_table(model) {
    table = {
        'EV2760': {
            'DVI': 0x0200,
            'DisplayPort1': 0x0300,
            'DisplayPort2': 0x0301,
            'HDMI': 0x0400 }
    }
	return table[model]
}

function lookup_input_source_alias(input) {
	table = {
        'DP1': 'DisplayPort1',
        'DP2': 'DisplayPort2',
	}
	
	key = Object.keys(table).find(k => k.toLowerCase() == input.toLowerCase())
	if (key) {
		return table[key]
	}
	return input
}

function set_val(dev, num, val) {
	buf = [0x02, 0x01, 0xFF, num & 255, num >> 8, 0x00, 0x00, val & 255, val >> 8]
	buf = buf.concat(Array(39 - buf.length).fill(0))
	dev.sendFeatureReport(buf)

	tmp = dev.getFeatureReport(7, 8).slice(0, 8)
	assert.strictEqual(tmp[0], 7)
	assert.deepStrictEqual(tmp.slice(1,7), buf.slice(1, 7))
}

function get_val(dev, num) {
	buf = [ 0x03, 0x01, 0xFF, num & 255, num >> 8]
	buf = buf.concat(Array(39 - buf.length).fill(0))
	dev.sendFeatureReport(buf)

	tmp = dev.getFeatureReport(3, 40)
	assert.deepStrictEqual(tmp.slice(0, 7), buf.slice(0, 7))
	val = tmp[8] * 256 + tmp[7]

	tmp = dev.getFeatureReport(7, 8).slice(0, 8)
	assert.strictEqual(tmp[0], 7)
	assert.deepStrictEqual(tmp.slice(1,7), buf.slice(1, 7))
	return val
}

function print_usage(input_source_table=None) {
    console.log("Usage: python hid-monitor-control.py <INPUT> [INPUT2]")
    if (input_source_table) {
		console.log("       INPUT = " + Object.keys(input_source_table).join(' | '))
	}
    console.log("")
	console.log("       python hid-monitor-control.py switcher")
}

des = HID.devices().find(d => device_id_pairs.includes((d.vendorId, d.productId)))
// console.log(des)

hid = new HID.HID(des.vendorId, des.productId)

sn_pn = hid.getFeatureReport(8, 25);
sn_pn = sn_pn.map(c => String.fromCharCode(c)).join('')
serial_number = sn_pn.substring(1,9)
product_name = sn_pn.substring(9, 25).replace(/ +$/, '')
// console.log(serial_number, product_name)

// console.log('0x' + get_val(hid, 0x48).toString(16))

input_source_table = get_input_source_table(product_name)
// default to EV2760 because that is the only one known for now
if (!input_source_table) {
	input_source_table = get_input_source_table('EV2760')
}


if (process.argv.length > 4) {
	print_usage(input_source_table)
	process.exit(1)
}

if (process.argv.length == 2) {
	// console.log('0x' + get_val(hid, 0x48).toString(16))
	num = 1
	if (get_val(hid, 0x40) != 0) {
		num = 2
	}
	sels = Array(num).fill(undefined)
	for (var i = 0; i < num; i++) {
		if (num > 1) {
			set_val(hid, 0xF9, i)
		}
		val = get_val(hid, 0x48)
		val = Object.keys(input_source_table).find(k => input_source_table[k] == val)
		if (val instanceof Number) {
			val = "Unknown(" + val + ")"
		}
		sels[i] = val
	}
	console.log("Input: %s", sels.join(' '))
	print_usage(input_source_table)
	process.exit(0)
}

if (process.argv.length == 3 && process.argv[2].toLowerCase() != 'switcher') {
	sel = process.argv[2]
	sel = lookup_input_source_alias(sel)
	sel = Object.keys(input_source_table).find(k => k.toLowerCase() == sel.toLowerCase() )
	set_val(hid, 0x40, 0)
	set_val(hid, 0x48, input_source_table[sel])
	process.exit(0)
}

if (process.argv.length == 4) {
	num = process.argv.length - 2
	sels = process.argv.slice(2,4)
	for (var i = 0; i < num; i++) {
		sel = sels[i]
		sel = lookup_input_source_alias(sel)
		sel = Object.keys(input_source_table).find(k => k.toLowerCase() == sel.toLowerCase() )
		sels[i] = sel
	}
	set_val(hid, 0x40, 1)
	for (var i = 0; i < num; i++) {
		set_val(hid, 0xF9, i)
		set_val(hid, 0x48, input_source_table[sels[i]])
	}
	process.exit(0)
}

// switcher event loog
function data_handler(data) {
	console.log(data)
}

// hid.newListener('data', data_handler)

function data_handler(dat) {
	console.log(dat)
	if (dat.slice(0,5).equals(Buffer.of(0x03, 0x01, 0xFF, 0x3D, 0x00))) {
		sel = undefined
		btn = dat[8] * 256 + dat[7]
		switch (btn) {
			case 0x20: sel = 'DisplayPort1'; break
			case 0x10: sel = 'DisplayPort2'; break
			case 0x08: sel = 'HDMI'; break
			case 0x04: sel = 'DVI'; break
		}
		if (sel)  {
			set_val(hid, 0x48, input_source_table[sel])
		}
	}
}
hid.on('data', data_handler)

// hid.resume()

// node will keep running
