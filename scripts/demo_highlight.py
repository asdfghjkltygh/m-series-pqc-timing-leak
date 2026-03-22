#!/usr/bin/env python3
"""Record just the demo ending for GIF capture.

Run this script and screen-record the terminal for a 15-second clip
showing the bar comparison: 62.49 FAIL vs 0.58 PASS.
"""
import sys
import time

from rich.console import Console

console = Console()

console.print()
console.print("  So what did we find?", style="bold white")
time.sleep(1.5)

console.print()
console.print("  The mandatory test, run the standard way:", style="dim")
time.sleep(0.5)

# Animated long bar
max_width = 45
for i in range(max_width + 1):
    bar = "\u2501" * i
    sys.stdout.write(f"\r  {bar}")
    sys.stdout.flush()
    time.sleep(0.04)
console.print(f"  62.49  ", style="bold red", end="")
console.print("FAIL", style="bold red")
time.sleep(2.0)

console.print()
console.print(
    "  The same test, measurements in alternating order:", style="dim"
)
time.sleep(0.5)

# Tiny bar
small = max(1, int(0.58 / 62.49 * max_width))
for i in range(small + 1):
    bar = "\u2501" * i
    sys.stdout.write(f"\r  {bar}")
    sys.stdout.flush()
    time.sleep(0.1)
padding = " " * (max_width - small)
console.print(f"{padding}  0.58  ", style="bold green", end="")
console.print("PASS", style="bold green")
time.sleep(2.0)

console.print()
console.print("  Same encryption. Same hardware. Same test.", style="dim")
console.print(
    "  The only thing we changed: the order of the measurements.",
    style="dim",
)
time.sleep(2.0)

console.print()
console.print(
    "  github.com/asdfghjkltygh/m-series-pqc-timing-leak", style="dim"
)
time.sleep(1.0)
console.print(
    "  The test lied. The encryption was safe all along.",
    style="bold magenta",
)
time.sleep(3.0)
