from CameraConnection import CameraConnection
from ViscaProtocol import SRG300

if __name__ == "__main__":
    
    # Initialize a connection
    camera = CameraConnection("192.168.0.100", 52381)
    
    # Send a zoom in command at half the maximum speed
    cmd_zoom = SRG300.zoom_cmd("in", speed=0.5)
    camera.send_command(cmd_zoom)

