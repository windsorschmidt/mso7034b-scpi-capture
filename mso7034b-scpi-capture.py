#!/bin/env python3

# About:
#
# Remotely configure MSO7034B oscilloscope and capture one-shot pulse data.
# Requires Python VISA packages to access scope using socket/SCPI interface:
#
#   sudo pip3 install pyvisa pyvisa-py
#
# The term "guide" herein refers to the document:
#
#   Agilent InfiniiVision 7000B Series Oscilloscopes Programmer's Guide
#   https://www.keysight.com/upload/cmc_upload/All/7000B_series_prog_guide.pdf

import os
import numpy as np
import matplotlib.pyplot as plt
import pyvisa

# Read SCPI socket parameters from environment variables set with, e.g.:
#
# export MSO7034B_IP=n.n.n.n
# export MSO7034B_PORT=nnnn
#
IP = os.getenv('MSO7034B_HOST')
PORT = os.getenv('MSO7034B_PORT')

# Set up resource handle to scope
rm = pyvisa.ResourceManager()
scope = rm.open_resource('TCPIP::{}::{}::SOCKET'.format(IP, PORT))
scope.read_termination = '\n'
scope.write_termination = '\n'
scope.timeout = 10000

r = scope.query('*idn?')
if r.split(',')[1] != 'MSO7034B':
    exit('It\'s dark here. You\'re likely to be eaten by a grue.')
    
# Set scope parameters
scope.clear()
scope.write('*rst')
scope.write(':timebase:mode main')
scope.write(':timebase:range 1e-2')
scope.write(':timebase:delay 0')
scope.write(':timebase:reference center')
scope.write(':channel1:probe 10')
scope.write(':channel1:range 8')
scope.write(':channel1:offset 0')
scope.write(':channel1:coupling dc')
scope.write(':trigger:sweep normal')
scope.write(':trigger:edge:source chan1')
scope.write(':trigger:level .1')
scope.write(':trigger:slope positive')
scope.write(':acquire:type normal')
scope.write(':acquire:complete 100')
scope.write(':acquire:count 1')
scope.write(':digitize channel1')
scope.write(':waveform:points 1000')
scope.write(':waveform:format word')
scope.write(':waveform:unsigned on')
scope.write(':waveform:byteorder lsbfirst')
scope.write(':waveform:source channel1')

# Get X/Y axis ranges
xrng = float(scope.query(':timebase:range?'))
yrng = float(scope.query(':channel1:range?'))

# Get axis configuration from preamble (guide p.673)
r = scope.query(':waveform:preamble?')
xinc, xorg, xref, yinc, yorg, yref = [float(i) for i in r.split(',')[4:]]

# Get acquisition data. Python's struct module docs list datatype specifiers:
# https://docs.python.org/3/library/struct.html#format-characters
r = scope.query_binary_values(':waveform:data?', datatype='H')
acq_data = np.array(r)

volts = (acq_data - yref) * yinc + yorg
time = np.arange(0, xinc * len(volts), xinc)

# Plot acquisition data
plt.ylabel('volts')
plt.xlabel('time')
plt.margins(x=0)
plt.grid(color='#bbbbbb', linestyle='-', linewidth=1)
plt.xticks(np.arange(0, xrng, step=xrng/10))
plt.ylim(-yrng/2, yrng/2)
plt.plot(time, volts) 
plt.show()

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

# Read the trigger event flag (cleared by scope on read)
# print(scope.query(':ter?'))

# Save an image of the scope's display to disk
# img = scope.query_binary_values(':display:data? png, scr, col', datatype='c')
# with open('scope_screenshot.png', 'wb') as f:
#     for b in img:
#         f.write(b)
