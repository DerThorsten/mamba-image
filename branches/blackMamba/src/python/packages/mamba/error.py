"""
This module handles computation errors in mamba module.
"""

import mamba.core as core

class MambaError(Exception):
    """
    Mamba basic exception.
    Occurs when the mamba library returns an error (return value different of NO_ERR).
    """
    
    def __init__(self, errValue):
        self.errValue = errValue
        self.errMsg   = core.MB_StrErr(self.errValue)
        
    def __str__(self):
        return "[errno "+str(self.errValue)+"] "+self.errMsg
        
        

def raiseExceptionOnError(err):
    """
    Raises a mamba exception if an error occurred in computations.
    The returned values of mamba C library are used to determine if there was an
    error or not.
    """
    if err!=core.NO_ERR:
        raise MambaError(err)