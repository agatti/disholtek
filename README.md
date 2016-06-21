# A simple disassembler for Holtek BS83B08A-3 microcontroller binaries.

## Current version: 0.1

This Python script disassembles binaries for Holtek's BS83B08A-3 low cost
microcontrollers, creating something that can be easily reassembled.

The script requires Python 3.4 or later to run, and its usage is almost
self-explanatory.  Just pass the binary file you want to disassemble as an
argument to the `bs83bdis.py` file and you'll get the result sent to STDOUT.
The script performs some basic checks to reject oversized or unaligned input
files.

## To do list:

* Lookup bit definitions so the disassembler can output something like
`CLR CSEN` instead of `CLR SIMC2.2`.
* Expand support for extra memory banks and sizes, to handle BS83B08A-4,
BS83B12A-3, BS83B12A-4, BS83B16A-3, and BS83B16A-4 microcontrollers.
* Add some heuristic to see whether to address `SIMC2` as `SIMA`.
* Support more Holtek microcontrollers (there are plenty to add!).
* Create an automatically generated test suite using the output of HT-IDE3000.

## Licence

This script is licensed under the ZLib licence, whose text can be found in the
LICENCE file in the repository.

Copyright (C) 2016 Alessandro Gatti
