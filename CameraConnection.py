import socket
import multiprocessing
import time
import struct

class CameraConnection:

    def __init__(self, cam_ip, cam_port):
        self.CamIP = cam_ip
        self.CamPort = cam_port
        self.ComputerIP = None
        self.sequenceNo = 1

        # Initialize the socket connection
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.connect((cam_ip, 52381))
        self.ComputerIP = self.sock.getsockname()[0]
        self.sock.close()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Initialize listening connection
        self.ListenSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        self.q = multiprocessing.Queue()
        listen_process = multiprocessing.Process(target=self.listen_to_camera, args=(self.q,))
        listen_process.start()
        time.sleep(1)


    def send_command(self, cam_command):
        # Insert correct sequence number
        cam_command = bytearray(cam_command)
        struct.pack_into(">I", cam_command, 4, self.sequenceNo)

        ack_received = False
        while not ack_received:
            # Send the command
            struct.pack_into(">I", cam_command, 4, self.sequenceNo)
            self.sock.sendto(cam_command, (self.CamIP, self.CamPort))
            
            # Wait for the Camera timeout
            time.sleep(0.1)

            # Check if we have received an acknowledgement message
            returned_messages = self.q.get()
            for message in returned_messages:
                if message.payload == "Acknowledge":
                    ack_received = True
                    print("Ack received for command number {} of type {}".format(message.sequence_no, message.command_type))
                if message.payload == "Completion":
                    print("Completion received for command number {}".format(message.sequence_no))
                elif message.payload == "Sequence Abnormality":
                    print("Sequence Abnormality")
                elif message.payload == "Message Abnormality":
                    print("Message Abnormality")
                else:
                    print("unresolved camera message")

            if ack_received:
                break
            else:
                print("Camera Acknowledgement Timeout Reached")
                print("Resending Command ")
                
        self.sequenceNo += 1

    def listen_to_camera(self, q):
        if self.ComputerIP is None:
            print("Network Error")
            return
        
        print("Computer Ip: " + self.ComputerIP)
        print("Cam Port: " + str(self.CamPort))
        self.ListenSocket.bind((self.ComputerIP, int(self.CamPort)))

        # Start listening
        messages_from_cam = []
        while True:
            # grab any messages
            data, addr = self.ListenSocket.recvfrom(1024)

            # need to check if this message is from our camera
            msg = CameraMessagesData(data, addr)
            messages_from_cam.append(msg)

            # put the message list in the queue
            q.put(messages_from_cam)


# Class to handle VISCA messages for sony SRG 300h
class CameraMessagesData:

    def __init__(self, data, addr):
        self.data = data
        self.addr = addr
        self.length = CameraMessagesData.decrypt_length(data)
        self.sequence_no = CameraMessagesData.decrypt_sequence_no(data)
        self.command_type = CameraMessagesData.decrypt_sequence_type(data)
        self.payload = CameraMessagesData.decrypt_payload(data)
        
    @staticmethod
    def decrypt_sequence_no(data):
        return struct.unpack(">I", data[4:8])[0]

    @staticmethod
    def decrypt_sequence_type(data):
        type_lut = {
            0x0100: "VISCA command",
            0x0110: "VISCA inquiry",
            0x0111: "VISCA reply",
            0x0120: "VISCA setting command",
            0x0200: "Control command",
            0x0201: "Control reply"
        }
        type_no = struct.unpack(">H", data[0:2])[0]
        return type_lut[type_no]

    @staticmethod
    def decrypt_length(data):
        return struct.unpack(">H", data[2:4])[0]

    @staticmethod
    def decrypt_payload(data):
        lut_control_reply = {
            0x01: "Acknowledge",
            0x0f01: "Sequence Abnormality",
            0x0f02: "Message Abnormality"
        }

        lut_command_reply = {
            0x9041ff: "Acknowledge",
            0x9051ff: "Completion"
        }

        length = CameraMessagesData.decrypt_length(data)
        command_type = CameraMessagesData.decrypt_sequence_type(data)
        if command_type == "Control reply":
            payload = struct.unpack(">I", data[8:8 + length])[0]
            return lut_control_reply[payload]
        elif command_type == "VISCA reply":
            payload = struct.unpack(">I", data[8:8 + length])[0]
            return lut_command_reply[payload]

        return "Not decrypted"
