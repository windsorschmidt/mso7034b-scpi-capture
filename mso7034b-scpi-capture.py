#!/usr/bin/env python3

# About:
#
# Remotely configure MSO7034B oscilloscope and capture one-shot pulse data.
# Requires Python VISA packages to access scope using socket/SCPI interface.
#
# Connection parameters are read from environment variables set with, e.g.:
#
#   export MSO7034B_HOST=192.168.0.243
#   export MSO7034B_PORT=5025
#
# Prerequisites on Raspberry Pi 4:
#
#   sudo apt-get install python3-pyvisa python3-pyvisa-py
#   sudo apt-get install python3-numpy python3-pip gnuplot
#   sudo pip3 install termplotlib
#
# The term "guide" herein refers to the document:
#
#   Agilent InfiniiVision 7000B Series Oscilloscopes Programmer's Guide
#   https://www.keysight.com/upload/cmc_upload/All/7000B_series_prog_guide.pdf

import os
import sys
import subprocess as proc
import pyvisa
import numpy as np
import termplotlib as tpl

HOST = os.getenv('MSO7034B_HOST', '192.168.0.243')
PORT = os.getenv('MSO7034B_PORT', '5025')

print('connecting to scope at {}:{}'.format(HOST, PORT))
rm = pyvisa.ResourceManager()
scope = rm.open_resource('TCPIP::{}::{}::SOCKET'.format(HOST, PORT))
scope.read_termination = '\n'
scope.write_termination = '\n'
scope.timeout = 30000

print('getting scope id')
r = scope.query('*idn?')
if r.split(',')[1] != 'MSO7034B':
    exit('It\'s dark here. You\'re likely to be eaten by a grue.')
print(r)

print('initializing scope')
scope.clear()
scope.write('*rst')
scope.write(':timebase:mode main')
scope.write(':timebase:range 1e-2')
scope.write(':timebase:delay 0')
scope.write(':timebase:reference left')
scope.write(':channel1:probe 1')
scope.write(':channel1:range 1.6e0')
scope.write(':channel1:offset 0')
scope.write(':channel1:coupling dc')
scope.write(':trigger:mode edge')
scope.write(':trigger:holdoff 1e0')
scope.write(':trigger:level 5.0e-2')
scope.write(':trigger:hfreject on')
scope.write(':trigger:reject hf')
scope.write(':trigger:slope positive')
scope.write(':trigger:source chan1')
scope.write(':trigger:sweep normal')
scope.write(':acquire:type normal')
scope.write(':digitize channel1')

# digitize will block further interaction with instrument,
# so generate a pulse, otherwise we will catch a timeout exception

print('generating pulse')
proc.run(sys.argv[1].split())

print('gathering waveform data')
scope.write(':waveform:source channel1')
scope.write(':waveform:points 1000')
scope.write(':waveform:format word')
scope.write(':waveform:unsigned on')
scope.write(':waveform:byteorder lsbfirst')

# Get axis configuration from preamble (guide p.673)
r = scope.query(':waveform:preamble?')
xinc, xorg, xref, yinc, yorg, yref = [float(i) for i in r.split(',')[4:]]

# Get acquisition data. Python's struct module docs list datatype specifiers:
# https://docs.python.org/3/library/struct.html#format-characters
r = scope.query_binary_values(':waveform:data?', datatype='H')
acq_data = np.array(r)

voltage = (acq_data - yref) * yinc + yorg
time = np.arange(0, xinc * len(voltage), xinc)

filename = 'mso_values.dat'
print('saving waveform data to {}'.format(filename))
np.savetxt(filename, np.column_stack((time, voltage)),
           fmt='%10.6f', delimiter=',', newline='\n')
        
fig = tpl.figure()
fig.plot(time, voltage, label="bumpy snake", width=96, height=24)
fig.show()

# A waveform record consists of either all of the acquired points or a
# subset of the acquired points. The number of points acquired may be
# queried using :ACQuire:POINts? (guide p.184)
#
# :WAVeform:POINts 1000 — returns time buckets 0, 1, 2, 3, 4 ,.., 999
# :WAVeform:POINts 500  — returns time buckets 0, 2, 4, 6, 8 ,.., 998
# :WAVeform:POINts 250  — returns time buckets 0, 4, 8, 12, 16 ,.., 996
# :WAVeform:POINts 100  — returns time buckets 0, 10, 20, 30, 40 ,.., 990


# In BYTE or WORD waveform formats, these data values have special meaning:
#
# • 0x00 or 0x0000 — Hole. Holes are locations where data has not yet been 
#   acquired. Holes can be reasonably expected in the equivalent time 
#   acquisition mode (especially at slower horizontal sweep speeds when 
#   measuring low frequency signals).
#
#   Another situation where there can be zeros in the data, incorrectly,
#   is when programming over telnet port 5024. Port 5024 provides a 
#   command prompt and is intended for ASCII transfers. Use telnet port 
#   5025 instead.
#
# • 0x01 or 0x0001 — Clipped low. These are locations where the waveform 
#   is clipped at the bottom of the oscilloscope display.
#
# • 0xFF or 0xFFFF — Clipped high. These are locations where the 
#   waveform is clipped at the top of the oscilloscope display.

# Save a screenshot
# img = scope.query_binary_values(':display:data? png, scr, col', datatype='c')
# with open('screenshot.png', 'wb') as f:
#     for b in img:
#         f.write(b)
