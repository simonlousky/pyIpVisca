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
    def _command_suffix(cls, payload):
        # Add payload length
        cmd = struct.pack(">H", len(payload))
        # Add arbitrary sequence number
        cmd += b'\xff\xff\xff\xff'
        # Add payload
        cmd += payload
        return cmd

    # Decorator for visca commands
    @classmethod
    def visca_command(cls, decorated): 
        # Build   | 01 | 00 | ss | ss | ff | ff | ff | ff | payload |
        #         |----------------header-----------------| payload |
        def inner(*args, **kwargs): 
            
            # Get command payload
            command_payload = decorated(*args, **kwargs) 
            # Add command type
            cmd = cls.payload_type["visca_command"]
            # Add suffix
            cmd += cls._command_suffix(command_payload)

            return bytearray(cmd)
            
        return inner

        # Decorator for visca commands
    @classmethod
    def control_command(cls, decorated): 
        # Build   | 01 | 00 | ss | ss | ff | ff | ff | ff | payload |
        #         |----------------header-----------------| payload |
        def inner(*args, **kwargs): 
            
            # Get command payload
            command_payload = decorated(*args, **kwargs) 
            # Add command type
            cmd = cls.payload_type["control_command"]
            # Add suffix
            cmd += cls._command_suffix(command_payload)

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
    @ViscaOverIp.control_command
    def reset_sequence_cmd():
        return b'\x01'

    @staticmethod
    @ViscaOverIp.visca_command
    def power_on_cmd():
        return b'\x81\x01\x04\x07\x03\xff'

    @staticmethod
    @ViscaOverIp.visca_command
    def power_off_cmd():
        return b'\x81\x01\x04\x00\x03\xff'

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
                # bitwise operation
                zoom_byte = bytes([b'\x20'[0] | speed_byte[0]])
                return payload + zoom_byte + b'\xff'
            elif command == "out":
                zoom_byte = bytes([b'\x30'[0] | speed_byte[0]])
                return payload + zoom_byte + b'\xff'
        
        return None
    
    @staticmethod
    @ViscaOverIp.visca_command
    def abs_position_cmd(pan_pos=0, tilt_pos=0, speed=1.0):
        '''
        pan_pos:    The wanted azimuth (right/left) relative to the camera's 0 direction
                    Value is in degrees between -170 and 170
        tilt_pos:   The wanted tilt (up/down) relative to the camera's 0 direction
                    Value is in degrees between -20 and 90
        speed:      The moving speed of the camera, between 0 and 1.0 (0 is slowest)

        Currently suited only for non flipped image (camera sitting on a table)
        '''
        # Limit position to pan in [-170, 170] and tilt in [-20, 90]
        pan_pos = min(pan_pos, 170)
        pan_pos = max(-170, pan_pos)
        tilt_pos = min(tilt_pos, 90)
        tilt_pos = max(-20, tilt_pos)
        speed = min(speed, 1.0)
        speed = max(0, speed)
        
        # Convert degrees to camera steps
        pan_pos *= 51.2
        tilt_pos *= 51.2

        # Normalize speed to limit values
        pan_speed = int(speed * 0x17) + 1
        tilt_speed = int(speed * 0x16) + 1

        # Base command
        payload = bytearray(b'\x81\x01\x06\x02')

        # Encode speeds to bytes
        payload += struct.pack(">B", pan_speed)
        payload += struct.pack(">B", tilt_speed)

        # Encode steps to bytes
        pan_val = struct.pack(">h", int(pan_pos))
        tilt_val = struct.pack(">h", int(tilt_pos))
        payload += bytearray([pan_val[0] >> 4, pan_val[0] & 0xf, pan_val[1] >> 4, pan_val[1] & 0xf])
        payload += bytearray([tilt_val[0] >> 4, tilt_val[0] & 0xf, tilt_val[1] >> 4, tilt_val[1] & 0xf])
        payload += b'\xff'

        return payload

    @staticmethod
    @ViscaOverIp.visca_command
    def relative_position_cmd(pan_pos=0, tilt_pos=0, speed=1.0):
        '''
        pan_pos:    The wanted azimuth (right/left) relative to the camera's current direction
                    Value is in degrees between -170 and 170
        tilt_pos:   The wanted tilt (up/down) relative to the camera's current direction
                    Value is in degrees between -20 and 90
        speed:      The moving speed of the camera, between 0 and 1.0 (0 is slowest)

        Currently suited only for non flipped image (camera sitting on a table)
        '''
        # Limit position to pan in [-170, 170] and tilt in [-20, 90]
        pan_pos = min(pan_pos, 170)
        pan_pos = max(-170, pan_pos)
        tilt_pos = min(tilt_pos, 90)
        tilt_pos = max(-20, tilt_pos)
        speed = min(speed, 1.0)
        speed = max(0, speed)
        
        # Convert degrees to camera steps
        pan_pos *= 51.2
        tilt_pos *= 51.2

        # Normalize speed to limit values
        pan_speed = int(speed * 0x17) + 1
        tilt_speed = int(speed * 0x16) + 1

        # Base command
        payload = bytearray(b'\x81\x01\x06\x03')

        # Encode speeds to bytes
        payload += struct.pack(">B", pan_speed)
        payload += struct.pack(">B", tilt_speed)

        # Encode steps to bytes
        pan_val = struct.pack(">h", int(pan_pos))
        tilt_val = struct.pack(">h", int(tilt_pos))
        payload += bytearray([pan_val[0] >> 4, pan_val[0] & 0xf, pan_val[1] >> 4, pan_val[1] & 0xf])
        payload += bytearray([tilt_val[0] >> 4, tilt_val[0] & 0xf, tilt_val[1] >> 4, tilt_val[1] & 0xf])
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

if __name__ == "__main__":
    def pprint(data):
        print( ":".join("{:02x}".format(c) for c in data))
    
    cmd = SRG300.abs_position_cmd(-180,10)
    pprint(cmd)
    cmd = SRG300.abs_position_cmd(0.5, 5)
    pprint(cmd)
    cmd = SRG300.relative_position_cmd(10, 10, 0.5)
    pprint(cmd)
    cmd = SRG300.zoom_cmd("in")
    pprint(cmd)
    cmd = SRG300.zoom_cmd("out")
    pprint(cmd)
    cmd = SRG300.zoom_cmd("in", 0.5)
    pprint(cmd)
    cmd = SRG300.zoom_cmd("out", 0.5)
    pprint(cmd)