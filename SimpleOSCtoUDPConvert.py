import socket
import multiprocessing
import time
import struct
import codecs

class OscCommandListener:

    def __init__(self, osc_ip, osc_port):
        self.OscIP = osc_ip
        self.OscPort = osc_port

        # Set up the socket to receive
        self.sock = socket.socket(socket.AF_INET,  # Internet
                            socket.SOCK_DGRAM)  # UDP
        self.sock.bind((self.OscIP, self.OscPort))

        # Set up the process to listen
        q = multiprocessing.Queue
        self.ListenProcess = multiprocessing.Process(target=self.wait_for_udp_packet())
        self.ListenProcess.start()

    def wait_for_udp_packet(self):

        # Start Listening
        converted_message = None
        print("Listening for OSC on: " + self.OscIP + ":" + str(self.OscPort))
        while True:
            # grab any messages
            data, addr = self.sock.recvfrom(1024)  # buffer size is 1024 bytes

            # Try to convert the osc packet to udp
            # If it doesn't succeed due to unicode decode error
            #      This means that it is a message from the camera since it is in hex code
            print("")
            print("Received OSC Message: ", data)
            print("Sending to converter...")
            try:
                converted_message = self.convert_osc_udp(data.decode())
            except UnicodeDecodeError:
                pass
                print("Received Cam Message: ", data)

            # Set up a camera connection
            conn = CameraConnection(converted_message[0], int(converted_message[1]))

            # Send the message to the camera
            conn.send_command(converted_message[2])

    def convert_osc_udp(self, message=""):
        # message format: "192.168.0.0::52381::hex-message<?>"

        # Find where the end of the message is, marked by '<?>'
        x1 = message.find("<?>")
        if x1 != -1:
            # Strip off everything after '<?>' including '<?>
            message = message[:x1]

            # Split the message into each part
            #   The parts are separated by '::'
            message_split = message.split('::')
            if len(message_split) == 3:
                # load the individual parts into variables
                ip = message_split[0]
                port = int(message_split[1])
                hexstuff = message_split[2]

                ReturnArray = [ip, port, hexstuff]
                return ReturnArray

            else:
                # not the correct number of parameters
                print("ERROR: Incorrect number of parameters, 3 expected (ip, port, hex command")

        else:
            # There is no '<?>'
            print("ERROR: Syntax Error. ")
            print("There is no end of command signifier, '<?>' is needed to signify end of command")

