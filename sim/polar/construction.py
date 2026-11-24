# construction.py
import numpy as np

def bhattacharyya_bec(N, z0):
    """
    Calculate the Bhattacharyya parameters for a Binary Erasure Channel (BEC).
    
    Parameters:
    N (int): The number of channels (must be a power of 2).
    z0 (float): The initial Bhattacharyya parameter for the BEC (smaller = more reliable).
    
    Returns:
    np.ndarray: An array of Bhattacharyya parameters for each channel.
    """

    if N & (N - 1) != 0 or N <= 0: # example (N=4): 1000 & 0111 = 0000 != 0, so N is not a power of 2
        raise ValueError("N must be a positive power of 2.")
    
    # Initialize the Bhattacharyya parameters
    #======================OLD VERSION========================
    # z = np.zeros(N) # Creating n-length array of zeros
    
    # z[0] = z0 # place the initial Bhattacharyya parameter in the first index of the array
    # 
    # # Calculate the Bhattacharyya parameters recursively
    # for i in range(1, int(np.log2(N)) + 1): #running from 1 to log2(N) + 1 
    #     for j in range(2**(i-1)):
    #         z[2*j] = 2 * z[j] - z[j]**2
    #         z[2*j + 1] = z[j]**2
    
    #======================NEW VERSION========================
    z = np.array([z0], dtype=float) # Creating an array with the initial Bhattacharyya parameter at the first index
    for _ in range(int(np.log2(N))):
        z_new = np.empty(2 * len(z))
        z_new[0::2] = 2 * z - z**2   # minus (worse) channel
        z_new[1::2] = z**2           # plus  (better) channel
        z = z_new
    return z

def design_z0(design_snr_db,R):
    """AWGN/BPSK -> equivalent BEC: Z = exp(-R*Eb/N0)."""
    return np.exp(-R * 10 ** (design_snr_db / 10))

def get_frozen_mask(N,K, design_snr_db = 0.0):
    """Get the frozen bit mask.
    True = frozen, False = information bit.
    
    Parameters:
    N (int): The code length (must be a power of 2).
    K (int): The number of information bits. ===IMPORTANT===
    design_snr_db (float): The design SNR in dB for the BEC
    """
    R = K/N
    z = bhattacharyya_bec(N, design_z0(design_snr_db,R))
    sorted_indices = np.argsort(z)[:K] # K most reliable channels
    mask = np.ones(N, dtype=bool) # Initialize all bits as frozen (True)
    mask[sorted_indices] = False # Set the K most reliable channels as information bits

    return mask