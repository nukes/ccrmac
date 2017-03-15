import numpy as np
# import bitalloc_ as b
import quantize as q
import window as w
import psychoac as p
import mdct as m

# Question 1.b)
def BitAllocUniform(bitBudget, maxMantBits, nBands, nLines, SMR=None):
    """
    Return a hard-coded vector that, in the case of the signal use in HW#4,
    gives the allocation of mantissa bits in each scale factor band when
    bits are uniformely distributed for the mantissas.
    """
    mantBits = np.array([3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,2,2,2])

    return mantBits # TO REPLACE WITH YOUR VECTOR

def BitAllocConstSNR(bitBudget, maxMantBits, nBands, nLines, peakSPL):
    """
    Return a hard-coded vector that, in the case of the signal use in HW#4,
    gives the allocation of mantissa bits in each scale factor band when
    bits are distributed for the mantissas to try and keep a constant
    quantization noise floor (assuming a noise floor 6 dB per bit below
    the peak SPL line in the scale factor band).
    """
    mantBits = np.array([0,0,4,13,16,16,16,15,11,0,0,0,0,0,0,0,0,13,14,0,0,14,0,0,0])
    return mantBits

def BitAllocConstMNR(bitBudget, maxMantBits, nBands, nLines, SMR):
    """
    Return a hard-coded vector that, in the case of the signal use in HW#4,
    gives the allocation of mantissa bits in each scale factor band when
    bits are distributed for the mantissas to try and keep the quantization
    noise floor a constant distance below (or above, if bit starved) the
    masked threshold curve (assuming a quantization noise floor 6 dB per
    bit below the peak SPL line in the scale factor band).
    """
    mantBits = np.array([0,4,8,10,13,12,12,12,9,0,2,4,4,4,5,5,2,11,12,0,0,12,0,0,0])
    return mantBits

# Question 1.c)
def BitAlloc(bitBudget, maxMantBits, nBands, nLines, SMR):
    """
    Allocates bits to scale factor bands so as to flatten the NMR across the spectrum

       Arguments:
           bitBudget is total number of mantissa bits to allocate
           maxMantBits is max mantissa bits that can be allocated per line
           nBands is total number of scale factor bands
           nLines[nBands] is number of lines in each scale factor band
           SMR[nBands] is signal-to-mask ratio in each scale factor band

        Return:
            bits[nBands] is number of bits allocated to each scale factor band

        Logic:
           Maximizing SMR over blook gives optimization result that:
               R(i) = P/N + (1 bit/ 6 dB) * (SMR[i] - avgSMR)
           where P is the pool of bits for mantissas and N is number of bands
           This result needs to be adjusted if any R(i) goes below 2 (in which
           case we set R(i)=0) or if any R(i) goes above maxMantBits (in
           which case we set R(i)=maxMantBits).  (Note: 1 Mantissa bit is
           equivalent to 0 mantissa bits when you are using a midtread quantizer.)
           We will not bother to worry about slight variations in bit budget due
           rounding of the above equation to integer values of R(i).
    """
    mantBits = np.zeros_like(nLines,dtype=int)
    localSMR = np.array(SMR,copy=True)
    allocBits = 0

    while allocBits < bitBudget:
        smrSort = np.argsort(localSMR)[::-1]
        maxSMR = smrSort[0]
        if nLines[maxSMR] > 0:
            if allocBits+nLines[maxSMR] >= bitBudget:
                for i in range(1,nBands):
                    maxSMR = smrSort[i]
                    if (allocBits)+nLines[maxSMR] >= bitBudget:
                        pass
                    else:
                        allocBits += nLines[maxSMR]
                        mantBits[maxSMR] += 1
                        localSMR[maxSMR] -= 6
                break
            else:
                allocBits += nLines[maxSMR]
                mantBits[maxSMR] += 1
                localSMR[maxSMR] -= 6
        else:
            localSMR[maxSMR] -= 6

    # Go back through and reallocate lonely bits and overflowing bits
    badBand = mantBits < maxMantBits
    while (mantBits==1).any() and badBand.any():
        # Pick lonely bit in highest critical band possible
        i = np.max(np.argwhere(mantBits==1))
        mantBits[i] = 0
        badBand[i] = False

        i = np.arange(nBands)[badBand][np.argmax(((SMR*(nLines>0))-mantBits*6)[badBand])]
        if (bitBudget-nLines[i]) >= 0 and nLines[i] > 0:
            mantBits[i] += 1
            bitBudget -= nLines[i]
            if mantBits[i] >= maxMantBits:
                badBand[i] = False
            else:
                badBand[i] = False

    mantBits = np.minimum(mantBits, np.ones_like(mantBits)*maxMantBits)
    return mantBits

# Bit Alloc Function to be used with SBR Module
def BitAllocSBR(bitBudget, maxMantBits, nBands, nLines, SMR, cutBand=25):
    """
    Allocates bits to scale factor bands so as to flatten the NMR across the spectrum

       Arguments:
           bitBudget is total number of mantissa bits to allocate
           maxMantBits is max mantissa bits that can be allocated per line
           nBands is total number of scale factor bands
           nLines[nBands] is number of lines in each scale factor band
           SMR[nBands] is signal-to-mask ratio in each scale factor band
           cutBin is the crtical band index above which we will perform HF Reconstruction

        Return:
            bits[nBands] is number of bits allocated to each scale factor band
    """
    cutBin = int(cutBand) # Make sure this is an integer
    mantBits = np.zeros_like(nLines[0:cutBand+1],dtype=int)
    localSMR = np.array(SMR,copy=True)[0:cutBand+1] # SMR of sub band
    subBand = np.array(nLines,copy=True)[0:cutBand+1]
    allocBits = 0

    # db print "SubBand: ", subBand

    while allocBits < bitBudget:
        smrSort = np.argsort(localSMR)[::-1]
        maxSMR = smrSort[0]
        if subBand[maxSMR] > 0:
            if allocBits+subBand[maxSMR] >= bitBudget:
                for i in range(1,nBands-(cutBin+1)):
                    maxSMR = smrSort[i]
                    if (allocBits)+subBand[maxSMR] >= bitBudget or subBand[maxSMR] == 0:
                        pass
                    else:
                        allocBits += subBand[maxSMR]
                        mantBits[maxSMR] += 1
                        localSMR[maxSMR] -= 6

                break
            else:
                allocBits += subBand[maxSMR]
                mantBits[maxSMR] += 1
                localSMR[maxSMR] -= 6
        else:
            localSMR[maxSMR] -= 6

    # Go back through and reallocate lonely bits and overflowing bits
    badBand = mantBits < maxMantBits
    while (mantBits==1).any() and badBand.any():
        # Pick lonely bit in highest critical band possible
        i = np.max(np.argwhere(mantBits==1))
        mantBits[i] = 0
        badBand[i] = False
        i = (np.arange(cutBin+1)[badBand])[np.argmax(((localSMR*(subBand>0))-mantBits*6)[badBand])]
        if (bitBudget-subBand[i]) >= 0 and subBand[i] > 0:
            mantBits[i] += 1
            bitBudget -= subBand[i]
            if mantBits[i] >= maxMantBits:
                badBand[i] = False
            else:
                badBand[i] = False

    mantBits = np.minimum(mantBits, np.ones_like(mantBits)*maxMantBits)
    # db print mantBits
    sbrBits = np.append(mantBits,np.zeros(len(nLines)-len(subBand))) # Add zeros back in for HF band
    #print sbrBits
    return sbrBits.astype(int)

#-----------------------------------------------------------------------------
