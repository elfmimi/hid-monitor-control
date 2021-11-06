#!ruby
require 'hidapi'
# https://rubygems.org/gems/hidapi/

device_id_pairs = [
  [0x056D, 0x4027], # EV2456
  [0x056D, 0x4014], # EV2750
  [0x056D, 0x4059], # EV2760
  [0x056D, 0x4065], # EV3895
]

$input_source_table = {


  :EV2456 => { :D-SUB => 0x0100, :DVI => 0x200, :DisplayPort => 0x0300, :HDMI => 0x0400 },
  :EV2750 => { :DVI => 0x0200, :DisplayPort => 0x0300, :HDMI => 0x0400 },
  :EV2760 => { :DVI => 0x0200, :DisplayPort1 => 0x0300, :DisplayPort2 => 0x0301, :HDMI => 0x0400 },
  :EV3895 => { :DisplayPort => 0x0300, :'USB-C' => 0x0301, :HDMI1 => 0x0400, :HDMI2 => 0x0401 },
}

$alias_table = {
  :DP => :DisplayPort,
  :DP1 => :DisplayPort1,
  :DP2 => :DisplayPort2,
  :TypeC => :'USB-C',
  :'Type-C' => :'USB-C',
  :USB => :'USB-C',
  :USBC => :'USB-C',
  :DSUB => :'D-SUB',
}

def print_usage(input_source_table = nil)
  STDERR.printf("\nUsage: %s INPUT1 [INPUT2]\n", $0)
  if input_source_table then
    STDERR.printf("       INPUT = ")
    STDERR.puts (input_source_table.collect{ |k,v|
      k.to_s
    }.join(" | "))
  end
  STDERR.printf("\n")
  STDERR.printf("       %s switcher\n", $0)
end

def get_input_val(input_source_table, arg)
  return nil if not arg
  arg = (($alias_table.find{|k,v|
    k.to_s.downcase == arg.downcase
  } || [])[1] || arg).to_s
  val = input_source_table.find{|k,v|
    k.to_s.downcase == arg.downcase
  }
  val = val[1] if val
  return val
end

def set_val(dev, num, val)
  buf = Array.new(39, 0)
  buf[0] = 0x02
  buf[1] = 0x01
  buf[2] = 0xFF
  buf[3] = num & 255
  buf[4] = num >> 8
  buf[5] = 0x00
  buf[6] = 0x00
  buf[7] = val & 255
  buf[8] = val >> 8
  dev.send_feature_report(buf)
  tmp = dev.get_feature_report(7, buffer_size = 8)
  raise if tmp[0].ord != 0x07
  6.times {|i| raise if tmp[i+1].ord != buf[i+1] }
end

def get_val(dev, num)
  buf = Array.new(39, 0)
  buf[0] = 0x03
  buf[1] = 0x01
  buf[2] = 0xFF
  buf[3] = num & 255
  buf[4] = num >> 8
  buf[5] = 0x00
  buf[6] = 0x00
  buf[7] = 0x00
  buf[8] = 0x00
  dev.send_feature_report(buf)
  tmp = dev.get_feature_report(3, buffer_size = 39)
  7.times {|i| raise if buf[i] != tmp[i].ord }
  val = tmp[8].ord * 256 + tmp[7].ord
  tmp = dev.get_feature_report(7, buffer_size = 8)
  raise if tmp[0].ord != 0x07
  6.times {|i| raise if tmp[i+1].ord != buf[i+1] }
  return val
end

# HIDAPI.engine.enumerate().each { |dev|
#   printf("%04X:%04X\n", dev.vendor_id, dev.product_id)
# }

dev = HIDAPI.engine.enumerate().find { |dev|
  device_id_pairs.include? [dev.vendor_id, dev.product_id]
}

exit 1 if not dev

# dev = HIDAPI.engine.get_device(0x056D, 0x4059)

dev.open
serial_number, model_number = (
  tmp = dev.get_feature_report(8, buffer_size = 25)
  [tmp[1..8], tmp[9...25].strip]
)

input_source_table = $input_source_table[model_number.to_sym]
input_source_table ||= $input_source_table[:EV2760] # default to EV2760

if not ARGV[0] then
  printf("%s (S/N: %s)\n", model_number, serial_number)
  if get_val(dev, 0x40) != 0
    set_val(dev, 0xF9, 0)
    val = get_val(dev, 0x48)
    printf("Input1: %s\n", input_source_table.invert[val])
    set_val(dev, 0xF9, 1)
    val = get_val(dev, 0x48)
    printf("Input2: %s\n", input_source_table.invert[val])
  else
    val = get_val(dev, 0x48)
    printf("Input: %s\n", input_source_table.invert[val])
  end

  STDOUT.flush()
  print_usage(input_source_table)

elsif ARGV[0].downcase == 'switcher'
  STDOUT.flush()
  loop {
    dat = dev.read()
    puts(dat.unpack('C*').collect{|i| format("0x%02X", i)}.join(",")); STDOUT.flush()
    if (dat[0..4] == [0x03, 0x01, 0xFF, 0x3D, 0x00].pack('C*')) then
      btn = dat[8].ord * 256 + dat[7].ord
      sel = nil
      if btn == 0x20 then
        sel = if input_source_table[:DisplayPort1] then :DisplayPort1 else :DisplayPort end
      elsif btn == 0x10 then
        sel = if input_source_table[:DisplayPort2] then :DisplayPort2 else nil end
      elsif btn == 0x08 then
        sel = :HDMI
      elsif btn == 0x04 then
        sel = :DVI
      end
      if sel then
        set_val(dev, 0x48, input_source_table[sel])
      end
    end
  }
else
  val = get_input_val(input_source_table, ARGV[0])
  val2 = get_input_val(input_source_table, ARGV[1])

  exit if not val

  if val2
    if val == val2
      STDOUT.flush()
      STDERR.printf("Error: Input1 and Input2 must be different.\n")
      exit 1
    end
    set_val(dev, 0x40, 1)
    set_val(dev, 0xF9, 0)
    set_val(dev, 0x48, val)
    set_val(dev, 0xF9, 1)
    set_val(dev, 0x48, val2)
  else
    set_val(dev, 0x40, 0)
    set_val(dev, 0x48, val)
  end

  dev.close
end
