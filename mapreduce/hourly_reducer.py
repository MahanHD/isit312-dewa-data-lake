#!/usr/bin/env python3
"""Reduce (also the combiner): sum kWh and reading counts per (meter_id, hour_ts). Input is sorted by key."""
import sys

key, kwh, readings = None, 0.0, 0
for line in sys.stdin:
    meter, hour, value, count = line.rstrip("\n").split("\t")
    if (meter, hour) != key:
        if key:
            print(f"{key[0]}\t{key[1]}\t{kwh!r}\t{readings}")
        key, kwh, readings = (meter, hour), 0.0, 0
    kwh += float(value)
    readings += int(count)
if key:
    print(f"{key[0]}\t{key[1]}\t{kwh!r}\t{readings}")
