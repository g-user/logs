#!/usr/bin/env python

import sys
import serial
import time

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

    # the FTDI chip seems to buffer up a certain amount of outgoing bytes if there is no
    # listener to recieve them.  thus, when we first run this script, we will get an initial
    # flood of queued readings.  throw those away.
    then = time.time()
    line = arduino.readline()
    if line.startswith("debug:"):
        sys.stdout.write(line)
    now = time.time()
    while now - then < 0.2:
        then = time.time()
        line = arduino.readline()
        if line.startswith("debug:"):
            sys.stdout.write(line)
        now = time.time()

    then = time.time()
    hp34401a.readline()
    now = time.time()
    while now - then < 0.2:
        then = time.time()
        hp34401a.readline()
        now = time.time()

    oven_out = open("oven-controller.csv", "w")
    tempco_out = open("tempco.csv", "w")
    tempco_out.write("Timestamp,Resistance,PPM,Oven (C),Ambient (C)\n")
    tempco_out.flush()

    last_hp_value = None
    last_arduino_time = None
    last_ppm = None
    last_c = None

    # store up values to average as the base_r to calculate ppm.
    base_r = None
    base_r_skip = 33
    base_r_count = 33
    base_rs = []

    while True:
        if hp34401a.inWaiting():
            last_hp_value = float(hp34401a.readline().rstrip())
            if base_r is None:
                print("appending %f" % last_hp_value)
                base_rs.append(last_hp_value)
        elif arduino.inWaiting():
            line = arduino.readline()
            if line.startswith("debug:"):
                sys.stdout.write(line)
                if last_ppm and last_c and last_c > 25.5:
                    print "current tempco: %0.2f ppm/K" % (last_ppm / (last_c - 25))
                continue
            last_arduino_time = time.time()
            if base_r is None and len(base_rs) >= base_r_skip + base_r_count:
                base_rs = base_rs[-base_r_count:]
                base_r = sum(base_rs) / float(base_r_count)
                print "base_r:", base_r
            if last_hp_value and base_r:
                oven_out.write(line)
                oven_out.flush()

                c = float(line.rstrip().split(",")[1])
                ambient = float(line.rstrip().split(",")[3])
                ppm = (last_hp_value - base_r) / base_r * 1000000.0
                tempco_out.write("%s,%s,%0.2f,%s,%s\n" % (time.time(),last_hp_value, ppm, c, ambient))
                tempco_out.flush()
                last_ppm = ppm
                last_c = c
        else:
            # when the Arduino stops sptting out values, the run is over.
            if last_arduino_time is not None and time.time() - last_arduino_time > 10.0:
                oven_out.close()
                tempco_out.close()
                sys.exit(0)

            time.sleep(0.01)
