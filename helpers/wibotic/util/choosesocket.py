"""Choose real or simulated socket based on connection URL"""
from helpers.wibotic.interface import wiboticsocket, wiboticsocketsim

def SocketFactory(url: str, *args, **kwargs):
    if url.startswith("sim:"):
        return wiboticsocketsim.SimulatedWiboticSocket(url, *args, **kwargs)
    return wiboticsocket.WiboticSocket(url, *args, **kwargs)