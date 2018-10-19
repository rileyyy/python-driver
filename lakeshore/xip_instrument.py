"""This module implements a parent class that contains all functionality shared by Lake Shore XIP instruments."""

from time import sleep
import serial
from serial.tools.list_ports import comports


class XIPInstrumentConnectionException(Exception):
    """Names a new type of exception specific to instrument connectivity."""
    pass


class XIPInstrument:
    """Parent class that implements functionality shared by all XIP instruments"""

    vid_pid = []

    def __init__(self, serial_number, com_port, baud_rate, timeout, flow_control):
        # Initialize values common to all XIP instruments
        self.device_serial = None
        self.connect_usb(serial_number, com_port, baud_rate, timeout, flow_control)

        # Query the instrument identification information and store the firmware version and model number in variables
        idn_response = self.query('*IDN?').split(',')
        self.firmware_version = idn_response[3]
        self.model_number = idn_response[1]

    def __del__(self):
        self.device_serial.close()

    def command(self, command, check_errors=True):
        """Sends a SCPI command to the instrument"""

        if check_errors:
            # Append the command with an error buffer query and check the response.
            command += ";:SYSTem:ERRor:ALL?"
            response = self.query(command)
            self._error_check(response)

        else:
            # Send command to the instrument over serial.
            self._usb_command(command)

    def query(self, query, check_errors=True):
        """Sends a SCPI query to the instrument and returns the response"""

        # Append the query with an additional error buffer query.
        if check_errors:
            query += ";:SYSTem:ERRor:ALL?"

        # Query the instrument over serial.
        response = self._usb_query(query)

        if check_errors:
            self._error_check(response)
            # If no error has occurred, remove the part of the response returned by the error buffer.
            response = response.replace(';0,"No error"', '')

        # Remove the line break the end of the response before returning it.
        return response.rstrip()

    @staticmethod
    def _error_check(response):
        """Evaluates the instrument response"""

        # If nothing is returned, raise a timeout error.
        if not response:
            raise XIPInstrumentConnectionException("Communication timed out")

        # If the error buffer returns an error, raise an exception with that includes the error.
        if "No error" not in response:
            # Isolate the part of the response that is the error
            response_list = response.split(';')
            returned_errors = response_list[len(response_list) - 1]

            raise XIPInstrumentConnectionException("SCPI command error: " + returned_errors)

    def connect_usb(self, serial_number=None, com_port=None, baud_rate=None, timeout=None, flow_control=None):
        """Establishes a serial USB connection with optional arguments"""

        # Scan the ports for devices matching the VID and PID combos of the instrument
        for port in comports():
            if (port.vid, port.pid) in self.vid_pid:
                # If the com port argument is passed, check for a match
                if port.device == com_port or com_port is None:
                    # If the serial number argument is passed, check for a match
                    if port.serial_number == serial_number or serial_number is None:
                        # Establish a connection with device using the instrument's serial communications parameters
                        self.device_serial = serial.Serial(port.device,
                                                           baudrate=baud_rate,
                                                           timeout=timeout,
                                                           parity=serial.PARITY_NONE,
                                                           rtscts=flow_control)

                        # Send the instrument a line break, wait 100ms, and clear the input buffer so that
                        # any leftover communications from a prior session don't gum up the works
                        self.device_serial.write(b'\n')
                        sleep(0.1)
                        self.device_serial.reset_input_buffer()

                        break
        else:
            raise XIPInstrumentConnectionException("No instrument found with given parameters")

    def disconnect_usb(self):
        """Disconnects the USB connection"""
        self.device_serial.close()
        self.device_serial = None

    def _usb_command(self, command):
        """Sends a command over the serial USB connection"""
        self.device_serial.write(command.encode('ascii') + b'\n')

    def _usb_query(self, query):
        """Queries over the serial USB connection"""

        self._usb_command(query)
        response = self.device_serial.readline().decode('ascii')
        return response
