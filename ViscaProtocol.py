import struct

class ViscaOverIp(object):
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

    @classmethod
    def visca_command(cls, decorated): 
        # Build   | 01 | 00 | ss | ss | ff | ff | ff | ff | payload |
        #         |----------------header-----------------| payload |
        def inner(*args, **kwargs): 
            
            # Get command payload
            command_payload = decorated(*args, **kwargs) 
            
            # Add command type
            cmd = cls.payload_type["visca_command"]
            # Add payload length
            cmd += struct.pack(">H", len(command_payload))
            # Add arbitrary sequence number
            cmd += b'\xff\xff\xff\xff'
            # Add payload
            cmd += command_payload

            return bytearray(cmd)
            
        return inner

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
    @ViscaOverIp.visca_command
    def zoom_cmd(command, speed=None):
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
    
    @staticmethod
    @ViscaOverIp.visca_command
    def abs_position_cmd(pan_pos=0, tilt_pos=0):

        # Limit position to pan in [-170, 170] and tilt in [-20, 90]
        pan_pos = min(pan_pos, 170)
        pan_pos = max(-170, pan_pos)
        tilt_pos = min(tilt_pos, 90)
        tilt_pos = max(-20, tilt_pos)
        
        # Convert degrees to camera steps
        pan_pos *= 51.2
        tilt_pos *= 51.2

        # Encode steps to bytes
        pan_val = struct.pack(">h", int(pan_pos))
        tilt_val = struct.pack(">h", int(tilt_pos))

        payload = b'\x01\x06\x02\x18\x17' 
        payload += pan_val[0] >> 4 + pan_val[0] & 0xf
        payload += pan_val[1] >> 4 + pan_val[1] & 0xf
        payload += tilt_val[0] >> 4 + tilt_val[0] & 0xf
        payload += tilt_val[1] >> 4 + tilt_val[1] & 0xf
        payload += b'\xff'

        return payload
            
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
