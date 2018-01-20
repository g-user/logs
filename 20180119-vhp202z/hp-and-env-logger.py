#!/usr/bin/env python

# Si7021-logger.py: read temperature / humidity data from an Arduino and log as CSV.
#
# linux usage examples:
# ./Si7021-logger.py /dev/ttyACM0
# ./Si7021-logger.py /dev/ttyUSB0
#
# mac usage examples:
# ./Si7021-logger.py /dev/tty.usbserial-DN02TIYO

import serial
import sys
import struct

# some useful notes on python dates and times:
# http://avilpage.com/2014/11/python-unix-timestamp-utc-and-their.html
import time


# CRC-8 implementation adapted from https://gist.github.com/hypebeast/3833758
class Crc8:
    def __init__(self):
        self.crcTable = (
            0x00, 0x07, 0x0e, 0x09, 0x1c, 0x1b, 0x12, 0x15, 0x38,
            0x3f, 0x36, 0x31, 0x24, 0x23, 0x2a, 0x2d, 0x70, 0x77,
            0x7e, 0x79, 0x6c, 0x6b, 0x62, 0x65, 0x48, 0x4f, 0x46, 
            0x41, 0x54, 0x53, 0x5a, 0x5d, 0xe0, 0xe7, 0xee, 0xe9, 
            0xfc, 0xfb, 0xf2, 0xf5, 0xd8, 0xdf, 0xd6, 0xd1, 0xc4, 
            0xc3, 0xca, 0xcd, 0x90, 0x97, 0x9e, 0x99, 0x8c, 0x8b, 
            0x82, 0x85, 0xa8, 0xaf, 0xa6, 0xa1, 0xb4, 0xb3, 0xba, 
            0xbd, 0xc7, 0xc0, 0xc9, 0xce, 0xdb, 0xdc, 0xd5, 0xd2,
            0xff, 0xf8, 0xf1, 0xf6, 0xe3, 0xe4, 0xed, 0xea, 0xb7, 
            0xb0, 0xb9, 0xbe, 0xab, 0xac, 0xa5, 0xa2, 0x8f, 0x88, 
            0x81, 0x86, 0x93, 0x94, 0x9d, 0x9a, 0x27, 0x20, 0x29, 
            0x2e, 0x3b, 0x3c, 0x35, 0x32, 0x1f, 0x18, 0x11, 0x16, 
            0x03, 0x04, 0x0d, 0x0a, 0x57, 0x50, 0x59, 0x5e, 0x4b, 
            0x4c, 0x45, 0x42, 0x6f, 0x68, 0x61, 0x66, 0x73, 0x74, 
            0x7d, 0x7a, 0x89, 0x8e, 0x87, 0x80, 0x95, 0x92, 0x9b,
            0x9c, 0xb1, 0xb6, 0xbf, 0xb8, 0xad, 0xaa, 0xa3, 0xa4,
            0xf9, 0xfe, 0xf7, 0xf0, 0xe5, 0xe2, 0xeb, 0xec, 0xc1, 
            0xc6, 0xcf, 0xc8, 0xdd, 0xda, 0xd3, 0xd4, 0x69, 0x6e, 
            0x67, 0x60, 0x75, 0x72, 0x7b, 0x7c, 0x51, 0x56, 0x5f, 
            0x58, 0x4d, 0x4a, 0x43, 0x44, 0x19, 0x1e, 0x17, 0x10, 
            0x05, 0x02, 0x0b, 0x0c, 0x21, 0x26, 0x2f, 0x28, 0x3d, 
            0x3a, 0x33, 0x34, 0x4e, 0x49, 0x40, 0x47, 0x52, 0x55, 
            0x5c, 0x5b, 0x76, 0x71, 0x78, 0x7f, 0x6a, 0x6d, 0x64, 
            0x63, 0x3e, 0x39, 0x30, 0x37, 0x22, 0x25, 0x2c, 0x2b, 
            0x06, 0x01, 0x08, 0x0f, 0x1a, 0x1d, 0x14, 0x13, 0xae, 
            0xa9, 0xa0, 0xa7, 0xb2, 0xb5, 0xbc, 0xbb, 0x96, 0x91,
            0x98, 0x9f, 0x8a, 0x8d, 0x84, 0x83, 0xde, 0xd9, 0xd0, 
            0xd7, 0xc2, 0xc5, 0xcc, 0xcb, 0xe6, 0xe1, 0xe8, 0xef,
            0xfa, 0xfd, 0xf4, 0xf3
        )
    
    def crc(self, msg):
        runningCRC = 0
        for c in msg:
            runningCRC = self.crcByte(runningCRC, c)
        return runningCRC

    def crcByte(self, oldCrc, byte):
        res = self.crcTable[oldCrc & 0xFF ^ byte & 0xFF];
        return res


# parse a packet of bytes from the arduino and log the values to stdout as CSV.
# if the CRC didn't match, return false.
def parse_and_send_bytes(bytes):
    # unpack those 9 bytes as two floats and an 8-bit CRC
    (temp_c, humidity, crc) = struct.unpack('ffB', bytes)

    # verify the CRC
    if crc != crc8.crc(bytes[:8]):
        return None

    now = time.time()

    # the FTDI chip seems to buffer up a certain amount of outgoing bytes if there is no
    # listener to recieve them.  thus, when we first run this script, we will get an initial
    # flood of queued readings.  throw those away.
    global last_sample_timestamp
    if now - last_sample_timestamp < 0.1:
        return None
    last_sample_timestamp = now

    return (now,temp_c,humidity)


# globals
last_sample_timestamp = time.time()


if __name__ == "__main__":
    # 9600, 8N1
    arduino = serial.Serial(
        port = sys.argv[1], # e.g. /dev/ttyACM0 or /dev/ttyUSB0
        baudrate = 9600,
        bytesize=serial.EIGHTBITS,
        stopbits = serial.STOPBITS_ONE,
        parity = serial.PARITY_NONE,
        timeout = 10
    )

    # 9600, 8N1
    hp34401a = serial.Serial(
        port = sys.argv[2], # e.g. /dev/ttyACM0 or /dev/ttyUSB0
        baudrate = 9600,
        bytesize=serial.EIGHTBITS,
        stopbits = serial.STOPBITS_ONE,
        parity = serial.PARITY_NONE,
        timeout = 10
    )

    crc8 = Crc8()
    bytes = bytearray([0,0,0,0,0,0,0,0,0])
    print "timestamp,r,humidity,temp_c"

    hp_value = None

    while True:
        if hp34401a.inWaiting():
            hp_value = float(hp34401a.readline().rstrip())

        # read in 9 bytes from the arduino and process the message
        for i in range(9):
            bytes[i] = arduino.read(1)
        ret = parse_and_send_bytes(bytes)
        
        # if CRC failed, try shifting in one byte at a time until we get a good result.
        # it is normal to see this error once during startup.
        while ret is None:
            for i in range(8):
                bytes[i] = bytes[i+1]
            bytes[8] = arduino.read(1)
            ret = parse_and_send_bytes(bytes)

        (now,temp_c,humidity) = ret

        if hp_value:
            print "%s,%0.3f,%0.3f,%0.3f" % (now, hp_value, humidity, temp_c)
            sys.stdout.flush()
            hp_value = None

