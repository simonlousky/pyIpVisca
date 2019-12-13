import struct

class ViscaOverIp:
    header_payload_type_range = (0,2)
    header_payload_length_range = (2,4)
    header_sequence_no_range = (4,8)
    payload_start = 8

    payload_type = {
        "visca_command": b'\x01\x00',
        "visca_inquiry": b'\x01\x10',
        "visca_reply": b'\x01\x11',
        "visca_setting_command": b'\x01\x20',  
        "control_command": b'\x02\x00',
        "control_reply": b'\x02\x01'
    }

class SRG300:
    '''
    Command reference for Sony SRG-300h
    '''
    # Incoming
    command_payloads = {
        "power_on": b'\x81\x01\x04\x00\x02\xff',
        "power_off": b'\x81\x01\x04\x00\x03\xff',
        
        # go
        "go_home": b'\x81\x01\x06\x04\xff',
        "go_preset1": b'\x81\x01\x04\x3F\x02\x00\xff',
        "go_preset2": b'\x81\x01\x04\x3F\x02\x01\xff',
        "go_preset3": b'\x81\x01\x04\x3F\x02\x02\xff',
        "go_preset4": b'\x81\x01\x04\x3F\x02\x03\xff'
        # move

        # zoom
    }
    
    control_payloads = {
        "reset_sequence": b'\x01'
    }

    # Outgoing
    control_reply = {
        b'\x01': "Acknowledge",
        b'\x0f\x01': "Sequence Abnormality",
        b'\x0f\x02': "Message Abnormality"
    }

    command_reply = {
        b'\x90\x41\xff': "Acknowledge",
        b'\x90\x51\xff': "Completion"
    }

    @staticmethod
    def zoom(command, speed=None):
        '''
        command: "in", "out", "stop"
        speed: float between 0 and 1, None means standard
        '''
        payload = b'\x81\x01\x04\x07'
        if command == "stop":
            return payload + b'\x00\xff'
        
        if speed is None:
            if command == "in":
                return payload + b'\x02\xff'
            elif command == "out":
                return payload + b'\x03\xff'
        
        if speed is not None:
            speed = min(1, speed)
            speed = max(0, speed)
            speed *= 7
            speed_byte = struct.pack("B", int(speed))
        
            if command == "in":
                return payload + b'\x2' + speed_byte + b'\xff'
            elif command == "out":
                return payload + b'\x3' + speed_byte + b'\xff'
        
        return None
            
class CameraMessageEncoder:

    @staticmethod
    def visca_command(command, sequence_no, Camera):
        '''
        | payload type | payload length | seq no | payload |
        ----------------------------------------------------
        |      2B      |       2B       |   4B   |  1B-16B |  
        '''
        payload = Camera.command_payload.get(command)
        if payload is None:
            raise Exception("Wrong command")

        cmd = ViscaOverIp.payload_type["visca_command"]
        cmd += struct.pack(">H", len(payload))
        cmd += struct.pack(">I", sequence_no)
        cmd += payload

class CameraMessageDecoder:
    def __init__(self, data, addr, Camera):
        self.data = data
        self.addr = addr
        self.length = CameraMessageDecoder.decrypt_length(data)
        self.sequence_no = CameraMessageDecoder.decrypt_sequence_no(data)
        self.command_type = CameraMessageDecoder.decrypt_sequence_type(data)
        self.payload = CameraMessageDecoder.decrypt_payload(data, Camera)
    
    @staticmethod
    def decrypt_sequence_no(data):
        return struct.unpack(">I", data[slice(*ViscaOverIp.header_sequence_no_range)])[0]

    @staticmethod
    def decrypt_sequence_type(data):
        type_lut = {v: k for k, v in ViscaOverIp.payload_type.items()}
        type_data = data[slice(*ViscaOverIp.header_payload_type_range)]
        return type_lut.get(type_data)

    @staticmethod
    def decrypt_length(data):
        return struct.unpack(">H", data[slice(*ViscaOverIp.header_payload_length_range)])[0]

    @staticmethod
    def decrypt_payload(data, Camera):
        length = CameraMessageDecoder.decrypt_length(data)
        command_type = CameraMessageDecoder.decrypt_sequence_type(data)
        payload = data[ViscaOverIp.payload_start:-1]

        if command_type == "control_reply":
            return Camera.control_reply.get(payload)
        elif command_type == "visca_reply":
            return Camera.visca_reply.get(payload)

        return "not_decrypted"
