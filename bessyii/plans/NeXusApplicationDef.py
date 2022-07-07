"""
This file contains plans which generate metadata that allows the data from them to be more easily mapped into NeXus application definitions

In general, they are thin wrappers on existing plans.

"""

# Define a special plan that does the mapping from BESSY beamline world to NeXus

from bluesky.plans import scan

def xas(detectors, mono, start,stop,res,md=None):
    
    """
    scan the mono (energy) between start and stop energy with a step of res. 
    Assumes that the first detector in the list is the absorbed energy, and the second is the incoming.
    
    Adds to the metadata dict and gives names based on the above assumptions. Names are complient with NXXas
    
    See: https://manual.nexusformat.org/classes/applications/NXxas.html

    Parameters
    ----------
    detectors : list
        list of 'readable' objects
    mono :
        Object of positioner type 
    start : float
        The start energy of the mono
    stop : float
        The stop energy of the mono
    res : float
        The energy resolution during the scan
    md : dict, optional
        metadata

    """
    
    num = int(abs(stop-start)/res+1)
    
    md = md or {}
    _md = {'technique': 'xas',
           'monochromator': mono.name,
           'incoming_beam': detectors[1].name,
           'absorbed_beam': detectors[0].name
           }
    _md.update(md)

    yield from scan(detectors, mono,start, stop,num, md=_md)   
    
    
    
# let's make a simulated detector.


from ophyd.sim import SynGauss, SynAxis, motor
from ophyd import Component as Cpt
from ophyd import Signal

class SynGaussMonitor(SynGauss):
    
    """
    An extension of the SynGauss device to include additional parameters that help us clasify it for generating NeXus files
    
    
    """
    mode = Cpt(Signal, kind='config')
    preset = Cpt(Signal, value = 0.1, kind='config')
    
    def __init__(self, prefix,mode, *args, **kwargs):
        
        super().__init__(prefix,*args,**kwargs)
        self.mode.put(mode)
        
        

noisy_det_monitor = SynGaussMonitor('noisy_det_monitor','timer',motor, 'motor', center=0, Imax=1, sigma=10,noise='uniform')