import socket
import multiprocessing
from threading import Thread
from queue import Queue
import time
import struct
from .ViscaProtocol import CameraMessageDecoder, SRG300

class CameraConnection:

    def __init__(self, cam_ip="192.168.0.100", cam_port=52381):
        self.cam_ip = cam_ip
        self.cam_port = cam_port
        self.computer_ip = None
        self.sequence_no = 1
        self.listen_stop = False

        # Initialize the socket connection
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.connect((cam_ip, cam_port))
        self.computer_ip = self.sock.getsockname()[0]
        self.sock.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Initialize listening connection
        self.listening_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.q = Queue()
        self.listen_process = Thread(target=self.listen_to_camera, args=(self.q,))
        self.listen_process.start()
        time.sleep(1)

    def __del__(self):
        self.listen_stop = True
        if getattr(self, "listen_process", None) is not None:
            self.listen_process.join()
        if getattr(self, "sock", None) is not None:
            self.sock.close()
        print("listening thread exited gracefully")

    def reset_camera_sequence(self, reset_command):
        self.send_command(reset_command)
        self.sequence_no = 1

    def send_command(self, cam_command, camera=SRG300, timeout=0.2):
        """
        Sends command until Acknowledge is received
        """
        # Insert correct sequence number
        cam_command = bytearray(cam_command)
        start_time = time.time()
        ack_received = False
        while not ack_received:
            # Send the command
            struct.pack_into(">I", cam_command, 4, self.sequence_no)
            self.sock.sendto(cam_command, (self.cam_ip, self.cam_port))

            # Check if we have received an acknowledgement message
            while not self.q.empty() or (time.time() - start_time) < timeout:
                data, addr = self.q.get(block=True)
                message = CameraMessageDecoder(data, addr, camera)
                if message.payload == "Acknowledge":
                    ack_received = True
                    print("Ack received for command number {} of type {}".format(message.sequence_no, message.command_type))
                    break
                elif message.payload == "Sequence Abnormality":
                    raise Exception("Sequence Abnormality")
                elif message.payload == "Impossible":
                    print("Impossible right now, retrying")
                else:
                    print("payload:", message.payload)
                time.sleep(0.1)

            if ack_received:
                break
            else:
                print("Camera Acknowledgement Timeout Reached")
                
        self.sequence_no += 1

    def listen_to_camera(self, q):
        if self.computer_ip is None:
            print("Network Error")
            return
        
        print("Computer ip: " + self.computer_ip)
        print("Cam Port: " + str(self.cam_port))
        self.listening_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listening_socket.bind((self.computer_ip, int(self.cam_port)))

        # Start listening
        while True:
            # grab any messages
            if self.listen_stop:
                break
            data, addr = self.listening_socket.recvfrom(1024)
            # Check if this message is from our camera
            if addr[0] == self.cam_ip:
                q.put((data, addr))

        self.listening_socket.close()
            
