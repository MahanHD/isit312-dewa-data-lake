#!/usr/bin/env python3
"""Map: one raw reading -> "meter_id <TAB> hour_ts <TAB> kwh <TAB> 1". Same rules as Shared rules 3."""
import re
import sys

NUMBER = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")

for line in sys.stdin:
    parts = line.rstrip("\r\n").split(",")
    if len(parts) != 4 or parts[0] == "LCLid":
        continue
    meter, kwh = parts[0].strip(), parts[3].strip()
    if not NUMBER.match(kwh) or float(kwh) < 0:
        continue
    print(f"{meter}\t{parts[2][:13]}:00:00\t{kwh}\t1")
