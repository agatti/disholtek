#!/usr/bin/env python3

# Copyright (c) 2016 Alessandro Gatti
#
# This software is provided 'as-is', without any express or implied
# warranty. In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgement in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.

from enum import Enum
import os
import struct
import io
import argparse

CODE_ADDRESS_START = 0x0000
CODE_ADDRESS_END = 0x07FF
CODE_FILE_MAX_SIZE = 0x1000


class Format(Enum):
    SPECIAL = 1
    M2A = 2
    A2M = 3
    LITERAL = 4
    ADDRESS = 5
    BIT = 6
    MEMORY = 7
    INVALID = 8


class Instruction(object):

    def __init__(self, address, opcode_name, opcode_type, word):
        if (address < CODE_ADDRESS_START) or (address > CODE_ADDRESS_END):
            raise Exception('Address 0x%04X out of range' % address)
        self.address = address

        self.word = word
        self.first = None
        self.second = None

        if opcode_type == Format.SPECIAL:
            pass
        elif opcode_type == Format.M2A:
            self.first = Instruction.get_data_address(word)
        elif opcode_type == Format.A2M:
            self.first = Instruction.get_data_address(word)
        elif opcode_type == Format.LITERAL:
            self.first = word & 0xFF
        elif opcode_type == Format.ADDRESS:
            self.first = word & 0x7FF
        elif opcode_type == Format.BIT:
            self.first = Instruction.get_data_address(word)
            self.second = Instruction.get_bit(word)
        elif opcode_type == Format.MEMORY:
            self.first = Instruction.get_data_address(word)
        elif opcode_type == Format.INVALID:
            pass
        else:
            raise Exception('Invalid or unrecognised opcode format')
        self.type = opcode_type

        self.name = None
        if opcode_name:
            self.name = opcode_name.strip()

        if (opcode_type != Format.INVALID) and not self.name:
            raise Exception('Invalid or missing opcode name')

    @staticmethod
    def get_data_address(word):
        return (word & 0x7F) + (0x80 if word & (1 << 14) else 0)

    @staticmethod
    def get_bit(word):
        return (word >> 7) & 7


class Disassembler(object):

    def __init__(self, input_path, labels=True):
        self._words = self._load_binary_file(input_path)
        self._code_address = 0

        self._instructions = [self._decode_word(word, address)
                              for (word, address) in enumerate(self._words)]

        self._labels = {}
        self._has_labels = labels
        if labels:
            self._assign_labels()

    def generate_output(self):
        with io.StringIO() as output:
            for (address, instruction) in enumerate(self._instructions):
                output.write(self._format_instruction(address,
                                                      instruction))
            return output.getvalue()

    def _load_binary_file(self, path):
        if not os.path.isfile(path):
            raise Exception('%s is not a file' % path)
        statinfo = os.stat(path)
        if statinfo.st_size == 0:
            raise Exception('%s does not contain any code' % path)
        elif (statinfo.st_size % 2) == 1:
            raise Exception('%s is not word-aligned' % path)
        elif statinfo.st_size > CODE_FILE_MAX_SIZE:
            raise Exception('%s is too big to fit in the MCU memory' % path)
        with open(path, 'rb') as source:
            source_bytes = source.read(statinfo.st_size)
            if len(source_bytes) != statinfo.st_size:
                raise Exception('I/O error when reading %s' % path)
            return struct.unpack('<%dH' % (statinfo.st_size / 2), source_bytes)

    _MEMORY_MAP = [
        # 00H
        'IAR0', 'MP0', 'IAR1', 'MP1', 'BP', 'ACC', 'PCL', 'TBLP', 'TBLH',
        'TBHP', 'STATUS', 'SMOD', 'CTRL', 'INTEG', 'INTC0', 'INTC1',
        # 10H
        None, None, None, 'LVRC', 'PA', 'PAC', 'PAPU', 'PAWU', None, None,
        'WDTC', 'TBC', 'TMR', 'TMRC', 'EEA', 'EED', 'PB',
        # 20H
        'PBC', 'PBPU',
        'I2CTOC', 'SIMC0', 'SIMC1', 'SIMD', 'SIMC2', None, None, None, None,
        None, None, None, None, None,
        # 30H
        None, None, None, None, None, None, None, None, None, None, None, None,
        None, None, None, None,
        # 40H
        None, None, None, 'TKTMR', 'TKC0', 'TK16DL', 'TK16DH', 'TKC1',
        'TKM016DL', 'TKM016DH', 'TKM0ROL', 'TKM0ROH', 'TKM0C0', 'TKM0C1',
        'TKM116DL', 'TKM116DH',
        # 50H
        'TKM1ROL', 'TKM1ROH', 'TKM1C0', 'TKM1C1', None, None, None, None,
        None, None, None, None, None, None, None, None
    ]

    _SPECIAL_MASK = 0b1111111111111000
    _SPECIAL_MARK = 0b0000000000000000
    _SPECIAL_LIST = 0b0000000000000111
    _SPECIAL_OPCODES = {
        0b0000000000000000: 'NOP',
        0b0000000000000001: 'CLR WDT1',
        0b0000000000000010: 'HALT',
        0b0000000000000011: 'RET',
        0b0000000000000100: 'RETI',
        0b0000000000000101: 'CLR WDT2',
    }

    _BIT_MASK = 0b1011000000000000
    _BIT_MARK = 0b0011000000000000
    _BIT_LIST = 0b0011110000000000
    _BIT_OPCODES = {
        0b0011000000000000: 'SET',
        0b0011010000000000: 'CLR',
        0b0011100000000000: 'SNZ',
        0b0011110000000000: 'SZ',
    }

    _ADDRESS_MASK = 0b1111000000000000
    _ADDRESS_MARK = 0b0010000000000000
    _ADDRESS_LIST = 0b1111100000000000
    _ADDRESS_OPCODES = {
        0b0010000000000000: 'CALL',
        0b0010100000000000: 'JMP',
    }

    _LITERAL_MASK = 0b1000100000000000
    _LITERAL_MARK = 0b0000100000000000
    _LITERAL_LIST = 0b0000111100000000
    _LITERAL_OPCODES = {
        0b0000100100000000: 'RET',
        0b0000101000000000: 'SUB',
        0b0000101100000000: 'ADD',
        0b0000110000000000: 'XOR',
        0b0000110100000000: 'OR',
        0b0000111000000000: 'AND',
        0b0000111100000000: 'MOV',
    }

    _M2A_MASK = 0b1001111110000000
    _M2A_MARK = 0b0000000010000000
    _M2A_LIST = 0b0001111110000000
    _M2A_OPCODES = {
        0b0000000010000000: 'MOV',
    }

    _OTHER_OPCODES_MASK = 0b1001111110000000
    _OTHER_OPCODES = {
        0b0000000010000000: (Format.M2A, 'MOV'),
        0b0000000100000000: (Format.MEMORY, 'CPLA'),
        0b0000000110000000: (Format.MEMORY, 'CPL'),
        0b0000001000000000: (Format.A2M, 'SUB'),
        0b0000001010000000: (Format.A2M, 'SUBM'),
        0b0000001100000000: (Format.A2M, 'ADD'),
        0b0000001110000000: (Format.A2M, 'ADDM'),
        0b0000010000000000: (Format.A2M, 'XOR'),
        0b0000010010000000: (Format.A2M, 'XORM'),
        0b0000010100000000: (Format.A2M, 'OR'),
        0b0000010110000000: (Format.A2M, 'ORM'),
        0b0000011000000000: (Format.A2M, 'AND'),
        0b0000011010000000: (Format.A2M, 'ANDM'),
        0b0000011100000000: (Format.A2M, 'MOV'),
        0b0001000000000000: (Format.MEMORY, 'SZA'),
        0b0001000010000000: (Format.MEMORY, 'SZ'),
        0b0001000100000000: (Format.MEMORY, 'SWAPA'),
        0b0001000110000000: (Format.MEMORY, 'SWAP'),
        0b0001001000000000: (Format.A2M, 'SBC'),
        0b0001001010000000: (Format.A2M, 'SBCM'),
        0b0001001100000000: (Format.A2M, 'ADC'),
        0b0001001110000000: (Format.A2M, 'ADCM'),
        0b0001010000000000: (Format.MEMORY, 'INCA'),
        0b0001010010000000: (Format.MEMORY, 'INC'),
        0b0001010100000000: (Format.MEMORY, 'DECA'),
        0b0001010110000000: (Format.MEMORY, 'DEC'),
        0b0001011000000000: (Format.MEMORY, 'SIZA'),
        0b0001011010000000: (Format.MEMORY, 'SIZ'),
        0b0001011100000000: (Format.MEMORY, 'SDZA'),
        0b0001011110000000: (Format.MEMORY, 'SDZ'),
        0b0001100000000000: (Format.MEMORY, 'RLA'),
        0b0001100010000000: (Format.MEMORY, 'RL'),
        0b0001100100000000: (Format.MEMORY, 'RRA'),
        0b0001100110000000: (Format.MEMORY, 'RR'),
        0b0001101000000000: (Format.MEMORY, 'RLCA'),
        0b0001101010000000: (Format.MEMORY, 'RLC'),
        0b0001101100000000: (Format.MEMORY, 'RRCA'),
        0b0001101110000000: (Format.MEMORY, 'RRC'),
        0b0001110100000000: (Format.MEMORY, 'TABRDC'),
        0b0001110110000000: (Format.MEMORY, 'TABRDL'),
        0b0001111010000000: (Format.MEMORY, 'DAA'),
        0b0001111100000000: (Format.MEMORY, 'CLR'),
        0b0001111110000000: (Format.MEMORY, 'SET'),
    }

    def _decode_word(self, address, word):
        if (word & Disassembler._SPECIAL_MASK) == Disassembler._SPECIAL_MARK:
            opcode_word = word & Disassembler._SPECIAL_LIST
            opcode_name = Disassembler._SPECIAL_OPCODES.get(opcode_word, None)
            if opcode_name:
                return Instruction(address, opcode_name, Format.SPECIAL, word)

        if (word & Disassembler._BIT_MASK) == Disassembler._BIT_MARK:
            opcode_word = word & Disassembler._BIT_LIST
            opcode_name = Disassembler._BIT_OPCODES.get(
                opcode_word, None)
            if opcode_name:
                return Instruction(address, opcode_name, Format.BIT, word)

        if (word & Disassembler._ADDRESS_MASK) == Disassembler._ADDRESS_MARK:
            opcode_word = word & Disassembler._ADDRESS_LIST
            opcode_name = Disassembler._ADDRESS_OPCODES.get(opcode_word, None)
            if opcode_name:
                return Instruction(address, opcode_name, Format.ADDRESS, word)

        opcode_word = word & Disassembler._OTHER_OPCODES_MASK
        (opcode_type, opcode_name) = Disassembler._OTHER_OPCODES.get(
            opcode_word, (None, None))
        if (opcode_type is not None) and (opcode_name is not None):
            return Instruction(address, opcode_name, opcode_type, word)

        if (word & Disassembler._LITERAL_MASK) == Disassembler._LITERAL_MARK:
            opcode_word = word & Disassembler._LITERAL_LIST
            opcode_name = Disassembler._LITERAL_OPCODES.get(opcode_word, None)
            if opcode_name:
                return Instruction(address, opcode_name, Format.LITERAL, word)

        if (word & Disassembler._M2A_MASK) == Disassembler._M2A_MARK:
            opcode_word = word & Disassembler._M2A_LIST
            opcode_name = Disassembler._M2A_OPCODES.get(
                opcode_word, None)
            if opcode_name:
                return Instruction(address, opcode_name, Format.M2A, word)

        return Instruction(address, None, Format.INVALID, word)

    def _assign_labels(self):
        counter = 0
        for instruction in self._instructions:
            if instruction.type == Format.ADDRESS:
                if instruction.first in self._labels:
                    continue

                self._labels[instruction.first] = 'label%04X' % counter
                counter += 1

    def _lookup_memory_location(self, location):
        if location < 0:
            raise Exception('Invalid memory location %d' % location)
        result = None
        if location < len(Disassembler._MEMORY_MAP):
            result = Disassembler._MEMORY_MAP[location]
        if not result:
            result = '[0%02Xh]' % location
        return result

    def _format_instruction(self, address, instruction):
        with io.StringIO() as output:
            if address in self._labels:
                output.write('\n%s:\n\n' % self._labels[address])

            output.write('%04X\t%04X\t' % (address, instruction.word))

            if instruction.type == Format.SPECIAL:
                output.write(instruction.name)
            elif instruction.type == Format.M2A:
                target = self._lookup_memory_location(instruction.first)
                output.write('%s\t%s, A' % (instruction.name, target))
            elif instruction.type == Format.A2M:
                target = self._lookup_memory_location(instruction.first)
                output.write('%s\tA, %s' % (instruction.name, target))
            elif instruction.type == Format.LITERAL:
                output.write('%s\tA, 0%02Xh' % (instruction.name,
                                                instruction.first))
            elif instruction.type == Format.ADDRESS:
                target = self._labels[instruction.first] \
                    if self._has_labels else ('0%04Xh' % instruction.first)
                output.write('%s\t%s' % (instruction.name, target))
            elif instruction.type == Format.BIT:
                target = self._lookup_memory_location(instruction.first)
                output.write('%s\t%s.%d' % (instruction.name, target,
                                            instruction.second))
            elif instruction.type == Format.MEMORY:
                target = self._lookup_memory_location(instruction.first)
                output.write('%s\t%s' % (instruction.name, target))
            else:
                output.write('; (%s) Invalid opcode' %
                             bin(instruction.word)[2:].zfill(16))

            output.write('\n')

            return output.getvalue()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='A Holtek BS83B08A-3 binary code disassembler')
    parser.add_argument('binary', metavar='FILE', type=str,
                        help='the binary file to disassemble')
    parser.add_argument('--no-labels', action='store_false',
                        help='do not generate labels')

    arguments = parser.parse_args()

    disassembler = Disassembler(arguments.binary, labels=arguments.no_labels)
    print(disassembler.generate_output())

# vim:et:syn=python:fdm=marker:ff=unix:number:ai:sta:fenc=utf-8
