"""Implements functionality unique to the Lake Shore F41 and F71 Teslameters."""

from collections import namedtuple
import re
from .xip_instrument import XIPInstrument

DataPoint = namedtuple("DataPoint", ['time_elapsed', 'date', 'hour', 'minute', 'second',
                                     'time_zone_hour', 'time_zone_minute',
                                     'magnitude', 'x', 'y', 'z', 'field_control_set_point', 'input_state'])


class Teslameter(XIPInstrument):
    """A XIP Instrument subclass that establishes Teslameter-specific parameters and methods"""

    vid_pid = [(0x1FB9, 0x0405), (0x1FB9, 0x0406)]

    def __init__(self, serial_number=None,
                 com_port=None, baud_rate=115200, flow_control=True,
                 timeout=2.0,
                 ip_address=None):
        # Call the parent init, then fill in values specific to the Teslameter
        XIPInstrument.__init__(self, serial_number, com_port, baud_rate, flow_control, timeout, ip_address)

    def get_buffered_data(self, length_of_time_in_seconds, sample_rate_in_ms=None, file_name=None):
        """Returns an array of parsed field and input state data. It optionally writes the data to a csv file"""

        # Make the amount of time a whole number
        length_of_time_in_seconds = round(length_of_time_in_seconds, 2)

        # Set the sample rate
        if sample_rate_in_ms is not None:
            self.command("SENSE:AVERAGE:COUNT " + str(sample_rate_in_ms / 10))
        else:
            sample_rate_in_ms = 10 * int(self.query("SENSE:AVERAGE:COUNT?"))

        # Clear the buffer by querying it
        self.query('FETC:BUFF:DC?', check_errors=False)

        buffered_data = []
        
        # Create a csv file with headers if a file name is passed. Files of the same name will be overwritten.
        if file_name is not None:
            file = open(file_name + ".csv", "w")
            file.write('time elapsed,date,hour,minute,second,time zone hour,time zone minute,' +
                       'magnitude,x,y,z,field control set point,input state\n')

        # Loop until the designated amount of time has been reached
        while True:
            response = self.query('FETC:BUFF:DC?', check_errors=False)

            # Ignore the response if it contains no data
            if ';' in response:
                # Split apart the response into single data points.
                data_points = response.rstrip(';').split(';')

                for point in data_points:
                    # Divide the data point along its delimiters.
                    parsed_point = re.split(r'T|:|\+|,', point)

                    # If field control is not connected to the instrument, insert 0 for the field control set point.
                    if len(parsed_point) == 11:
                        input_state = parsed_point.pop()
                        parsed_point.append('0')
                        parsed_point.append(input_state)

                    # Calculate how much time has passed.
                    elapsed_time = (len(buffered_data) + 1) * sample_rate_in_ms / 1000

                    # Unpack the parsed point into a namedtuple and append it to the list
                    new_point = DataPoint(elapsed_time, *parsed_point)
                    buffered_data.append(new_point)

                    # Write the data to the file in a csv friendly format if a file name was provided
                    if file_name is not None:
                        file.write(str(elapsed_time) + ',' +
                                   str(parsed_point).replace("'", "").replace("[", "").replace("]", "") +
                                   '\n')

                    # Check to see if time is up. If so, return the data.
                    if len(buffered_data) * sample_rate_in_ms >= length_of_time_in_seconds * 1000:
                        if file_name is not None:
                            file.close()
                        return buffered_data
