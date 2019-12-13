import socket
import multiprocessing
import time
import struct
from ViscaProtocol import CameraMessageDecoder, SRG300

class CameraConnection:

    def __init__(self, cam_ip="192.168.0.100", cam_port=52381):
        self.cam_ip = cam_ip
        self.cam_port = cam_port
        self.computer_ip = None
        self.sequence_no = 1

        # Initialize the socket connection
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.connect((cam_ip, cam_port))
        self.computer_ip = self.sock.getsockname()[0]
        self.sock.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Initialize listening connection
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.q = multiprocessing.Queue()
        listen_process = multiprocessing.Process(target=self.listen_to_camera, args=(self.q,))
        listen_process.start()
        time.sleep(1)


    def send_command(self, cam_command):
        # Insert correct sequence number
        cam_command = bytearray(cam_command)
        struct.pack_into(">I", cam_command, 4, self.sequence_no)

        ack_received = False
        while not ack_received:
            # Send the command
            struct.pack_into(">I", cam_command, 4, self.sequence_no)
            self.sock.sendto(cam_command, (self.cam_ip, self.cam_port))
            
            # Check if we have received an acknowledgement message
            returned_messages = self.q.get()
            for message in returned_messages:
                print("Camera message: "),
                if message.payload == "Acknowledge":
                    ack_received = True
                    print("Ack received for command number {} of type {}".format(message.sequence_no, message.command_type))
                elif message.payload == "Completion":
                    print("Completion received for command number {}".format(message.sequence_no))
                else:
                    print(message.payload)

            if ack_received:
                break
            else:
                print("Camera Acknowledgement Timeout Reached")
                print("Resending Command ")
                
        self.sequence_no += 1

    def listen_to_camera(self, q):
        if self.computer_ip is None:
            print("Network Error")
            return
        
        print("Computer ip: " + self.computer_ip)
        print("Cam Port: " + str(self.cam_port))
        self.listening_socket.bind((self.computer_ip, int(self.cam_port)))

        # Start listening
        messages_from_cam = []
        while True:
            # grab any messages
            data, addr = self.listening_socket.recvfrom(1024)

            # need to check if this message is from our camera
            msg = CameraMessageDecoder(data, addr, SRG300)
            messages_from_cam.append(msg)

            # put the message list in the queue
            q.put(messages_from_cam)
