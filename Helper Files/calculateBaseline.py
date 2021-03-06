
"""
Need to Install in the Python Enviroment Beforehand:
    $ pip install BaselineRemoval
"""

# Import Basic Modules
import numpy as np
# Import Modules for Baseline Subtraction
from BaselineRemoval import BaselineRemoval
# Import Modules for Low Pass Filter
from scipy.signal import savgol_filter
from scipy.signal import butter, lfilter 
# Import Modules to Find Peak
from scipy.interpolate import UnivariateSpline
import scipy.signal
# Modules to Plot
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------#
# --------------------- Specify/Find File Names -----------------------------#

class filterData:
    
    def butterParams(self, cutoffFreq = [0.1, 7], samplingFreq = 800, order=3, filterType = 'low'):
        nyq = 0.5 * samplingFreq
        if filterType == "band":
            normal_cutoff = [freq/nyq for freq in cutoffFreq]
        else:
            normal_cutoff = cutoffFreq / nyq
        sos = butter(order, normal_cutoff, btype = filterType, analog = False, output='sos')
        return sos
    
    def butterFilter(self, data, cutoffFreq, samplingFreq, order = 3, filterType = 'band'):
        sos = self.butterParams(cutoffFreq, samplingFreq, order, filterType)
        return scipy.signal.sosfiltfilt(sos, data)

class polynomialBaselineFit:
    
    def baselineSubtractionAPI(self, current, polynomialOrder, reductiveScan):
        # Get Baseline Depending on Ox/Red Curve
        if reductiveScan:
            baseObj = BaselineRemoval(-current)
            baseline = current + baseObj.ModPoly(polynomialOrder)
        else:
            baseObj = BaselineRemoval(current)
            baseline = current - baseObj.ModPoly(polynomialOrder)
        # Return Baseline
        return baseline
    
    def baselineSubtraction(self, potential, current, polynomialOrder, Iterations, reductiveScan):
        if reductiveScan:
            baseline = - self.getBaseline(potential, -current, Iterations, polynomialOrder)
        else:
            baseline = self.getBaseline(potential, current, Iterations, polynomialOrder)
        # Return Baseline
        return baseline
    
    def getBaseline(self, x, y, Iterations, order):
        yHold = y.copy()
        for _ in range(Iterations):
            fitI = np.polyfit(x, yHold, order)
            baseline = np.polyval(fitI, x)
            for i in range(len(y)):
                if yHold[i] > baseline[i]:
                    yHold[i] = baseline[i]
        return baseline
        
class bestLinearFit2:
    
    def __init__(self):
        self.minPeakDuration = 10
        self.minLeftBoundaryInd = 0
    
    def findBaseline(self, xData, yData, reductiveScan):
        
        reductiveScale = -(2*reductiveScan - 1)
        # ------------------------- Find the Peaks ------------------------- #
        # Find the Peak
        peakIndices = list(self.findPeak(xData, yData*reductiveScale, deriv=False))      
        peakIndices.extend(self.findPeak(xData, savgol_filter(yData, 9, 3, deriv=1)*reductiveScale, deriv=True))   
        peakIndices = list(set(peakIndices))
        # Return None if No Peak Found
        if len(peakIndices) == 0:
            print("No Peak Found in Data")
            return yData
        # Sort the Indices so They Appear 1-by-1
        peakIndices.sort()
        print("Initial Peak Indices:", peakIndices, xData[peakIndices])
        # ------------------------------------------------------------------ #

        # ------------------ Find and Remove the Baseline ------------------ #
        finalIndices = []; peakIndCuts = []
        for peakInd in peakIndices:
            # Get Baseline from Best Linear Fit
            leftCutInd, rightCutInd = self.findLinearBaseline(xData, yData, peakInd)
            if None in [leftCutInd, rightCutInd] or rightCutInd - leftCutInd < self.minPeakDuration:
                continue
            finalIndices.append(peakInd)
            peakIndCuts.extend([leftCutInd, rightCutInd])
        
        if len(finalIndices) == 0:
            print("No Baseline Data Found")
            return yData
        # ------------------------------------------------------------------ #
        
        # ------------------ Organize the Peak Boundaries ------------------ #
        finalIndCuts = [-1]
        peakCutPointer = 0; peakCutIndBuffer = 0
        # Loop Through the Peak Boundaries, and Remove Overlapping Boundaries
        for _ in range(len(peakIndCuts)):
            peakCutInd = peakIndCuts[peakCutPointer]
            
            # If we are at the Last Peak, Add the Peak
            if peakCutPointer == len(peakIndCuts) - 1:
                finalIndCuts.append(peakCutInd)
                break
            # If the Adjacent Peak is Before, Skip Over the Peak (Peaks Overlap)
            elif peakIndCuts[peakCutPointer+1] <= peakCutInd + peakCutIndBuffer:
                peakCutPointer += 2
            # Else, Keep the Peak Boundary and Check the Next
            else:
                peakCutPointer += 1
                finalIndCuts.append(peakCutInd)
        finalIndCuts.append(len(yData))
                
        # ASSERTION: There Should be an Even Number of Boundaries (LEFT, RIGHT)
        assert len(finalIndCuts)%2 == 0
        # ------------------------------------------------------------------ #

        # --------------------- Calculate the Baseline --------------------- #
        previousBoundaryInd = finalIndCuts[0]
        baseline = []; removeData = True;
        for peakBoundaryInd in finalIndCuts[1:]:
            
            if removeData:
                baseline = np.concatenate((baseline, yData[previousBoundaryInd+1:peakBoundaryInd]))
            else:
                # Fit Lines to Ends of Graph
                lineSlope, slopeIntercept = np.polyfit(xData[[previousBoundaryInd, peakBoundaryInd]], yData[[previousBoundaryInd, peakBoundaryInd]], 1)
                linearFit = lineSlope*xData + slopeIntercept
                
                # Piece Together yData's Baseline
                baseline = np.concatenate((baseline, linearFit[previousBoundaryInd:peakBoundaryInd+1]))
            
            # Reset for the Next Round
            previousBoundaryInd = peakBoundaryInd
            removeData = not removeData
        # ------------------------------------------------------------------ #
        return baseline
    
    def findPeak(self, xData, yData, ignoredBoundaryPoints = 5, deriv = False):
        # Find All Peaks in the Data
        peakInfo = scipy.signal.find_peaks(yData, prominence=10E-10, distance = 5)
        # Extract the Peak Information
        peakProminences = peakInfo[1]['prominences']
        peakIndices = peakInfo[0]
        
        # Remove Peaks Nearby Boundaries
        allProminences = peakProminences[np.logical_and(peakIndices < len(xData) - ignoredBoundaryPoints, peakIndices >= ignoredBoundaryPoints)]
        peakIndices = peakIndices[np.logical_and(peakIndices < len(xData) - ignoredBoundaryPoints, peakIndices >= ignoredBoundaryPoints)]

        if len(peakIndices) == 0 and not deriv:
            filteredVelocity = savgol_filter(yData, 9, 3, deriv=1)
            return self.findPeak(xData, filteredVelocity, ignoredBoundaryPoints, deriv = True)
        # If No Peak is Found, Return None
        return peakIndices
    
    def findPeakGeneral(self, xData, yData):
        peakInfo = scipy.signal.find_peaks(yData, prominence=10E-10, distance = 10)
        peakIndices = peakInfo[0]
        return peakIndices

    
    def findLinearBaseline(self, xData, yData, peakInd):
        # Define a threshold for distinguishing good/bad lines
        maxBadPointsTotal = int(len(xData)/10)
        # Store Possibly Good Tangent Indexes
        goodTangentInd = [[] for _ in range(maxBadPointsTotal)]
        
        # For Each Index Pair on the Left and Right of the Peak
        for rightInd in range(peakInd+2, len(yData), 1):
            for leftInd in range(peakInd-2, self.minLeftBoundaryInd, -1):
                
                # Initialize range of data to check
                checkPeakBuffer = 0#int((rightInd - leftInd)/4)
                xDataCut = xData[max(0, leftInd - checkPeakBuffer):rightInd + checkPeakBuffer]
                yDataCut = yData[max(0, leftInd - checkPeakBuffer):rightInd + checkPeakBuffer]
                
                # Draw a Linear Line Between the Points
                lineSlope = (yData[leftInd] - yData[rightInd])/(xData[leftInd] - xData[rightInd])
                slopeIntercept = yData[leftInd] - lineSlope*xData[leftInd]
                linearFit = lineSlope*xDataCut + slopeIntercept
    
                # Find the Number of Points Above the Tangent Line
                numWrongSideOfTangent = len(linearFit[linearFit - yDataCut > 0])
                
                # If a Tangent Line is Drawn Correctly, Return the Tangent Points' Indexes
                # if numWrongSideOfTangent == 0 and rightInd - leftInd > self.minPeakDuration:
                #     return (leftInd, rightInd)
                # Define a threshold for distinguishing good/bad lines
                maxBadPoints = int(len(linearFit)/15) # Minimum 1/6
                if numWrongSideOfTangent < maxBadPoints and rightInd - leftInd > self.minPeakDuration:
                    goodTangentInd[numWrongSideOfTangent].append((leftInd, rightInd))
                    
        # If Nothing Found, Try and Return a Semi-Optimal Tangent Position
        for goodInd in range(maxBadPointsTotal):
            if len(goodTangentInd[goodInd]) != 0:
                return max(goodTangentInd[goodInd], key=lambda tangentPair: tangentPair[1]-tangentPair[0])
        return None, None

class bestLinearFit:
    
    def __init__(self, potential, current):
        self.potential = potential
        self.current = current
        self.linearFit = []
        self.baseline = None
    
    def findPeak(self, smoothCurrent, reductiveScale = 1, ignoredBoundaryPoints = 10):
        smoothCurrentPeaks = scipy.signal.find_peaks(reductiveScale*smoothCurrent.derivative(n=1)(self.potential), prominence=10E-4, width=4)
        allPeakInds = smoothCurrentPeaks[0]
        allProminences = smoothCurrentPeaks[1]['prominences']
        # Remove Peaks Nearby Boundaries
        allProminences = allProminences[np.logical_and(allPeakInds < len(self.potential) - ignoredBoundaryPoints, allPeakInds >= ignoredBoundaryPoints)]
        allPeakInds = allPeakInds[np.logical_and(allPeakInds < len(self.potential) - ignoredBoundaryPoints, allPeakInds >= ignoredBoundaryPoints)]
        
        if len(allPeakInds) > 0:
            bestPeak = allProminences.argmax()
            peakInd = allPeakInds[bestPeak]
        else:
            peakInd = None
        
        return peakInd
    
    def findInflection(self, smoothCurrent, peakInd):
        smoothCurrentPeaks = scipy.signal.find_peaks(smoothCurrent.derivative(n=2)(self.potential), prominence=10E-10)
        allPeakInds = smoothCurrentPeaks[0]
        # Remove Peaks Nearby Boundaries
        ignoredBoundaryPoints = 10
        allPeakInds = allPeakInds[np.logical_and(allPeakInds < len(self.potential) - ignoredBoundaryPoints, allPeakInds >= ignoredBoundaryPoints)]

        leftPoints = allPeakInds[allPeakInds < peakInd]
        if len(leftPoints) > 0 and len(leftPoints) < len(allPeakInds):
            leftInd = np.where(allPeakInds == leftPoints[-1])[0][0]
            leftCutInd = allPeakInds[leftInd]
            rightCutInd = allPeakInds[leftInd + 1]
        else:
            leftCutInd = None; rightCutInd = None
        
        return leftCutInd, rightCutInd
    
    def createTangentLine(self, peakInd, smoothCurrent, reductiveScale = 1, nearbyBuffer = 10, saveGoodInd = 4):
        smoothCurrentY = smoothCurrent(self.potential)
        # Divide the Current into Two Groups: Left and Right
        leftCurrent = self.current[0:peakInd]
        rightCurrent = self.current[peakInd+1:len(self.current)]
        # Store Possibly Good Tangent Indexes
        goodTangentInd = {}
        for goodInd in range(1+saveGoodInd):
            goodTangentInd[goodInd] = []
        
        for rightInd, rightPoint in enumerate(rightCurrent):
            rightInd = rightInd + peakInd + 1
            for leftInd, leftPoint in enumerate(leftCurrent):
                # Fit Lines to Ends of Graph
                m0, b0 = np.polyfit(self.potential[[leftInd, rightInd]], self.current[[leftInd, rightInd]], 1)
                linearFit = m0*self.potential + b0

                numWrongSideOfTangent = len(reductiveScale*linearFit[linearFit - smoothCurrentY > 0])
                # If a Tangent Line is Drawn Correctly, Return the Tangent Points' Indexes
                if numWrongSideOfTangent <= saveGoodInd:
                    goodTangentInd[numWrongSideOfTangent].append((leftInd, rightInd))
        
        # If Nothing Found, Try and Return a Semi-Optimal Tangent Position
        for goodInd in sorted(goodTangentInd.keys()):
            if len(goodTangentInd[goodInd]) != 0:
                return min(goodTangentInd[goodInd], key=lambda tangentPair: tangentPair[1]-tangentPair[0])
        return None, None
        
    
    def findLinearBaseline(self, reductiveScan):
        # Smooth Current to Remove Extremely Small Peaks
        smoothCurrent = UnivariateSpline(self.potential, self.current, s=10E-6, k=5)
        # Find the Peak
        reductiveScale = -(2*reductiveScan - 1)
        peakInd = self.findPeak(smoothCurrent, reductiveScale)
        print(peakInd)
        
        # If a Peak Was Found, Find Baseline
        if peakInd != None:
            # Find the Peak Bounds
            leftCutInd, rightCutInd = self.createTangentLine(peakInd, smoothCurrent, reductiveScale)
            print(leftCutInd, rightCutInd, peakInd)
            # If No Bounds Found Than it Was a Single Point Deviation
            if None in [leftCutInd, rightCutInd]:
                return self.current
            
            # Fit Lines to Ends of Graph
            m0, b0 = np.polyfit(self.potential[[leftCutInd, rightCutInd]], self.current[[leftCutInd, rightCutInd]], 1)
            self.linearFit = m0*self.potential + b0
            
            # Piece Together the Current's Baseline
            self.baseline = np.concatenate((self.current[0:leftCutInd+1], self.linearFit[leftCutInd+1: rightCutInd], self.current[rightCutInd:len(self.current)]))
            return self.baseline
        # Else, the Baseline is the Potential (No Peak)
        else:
            return self.current
    
    def plotLinearFit(self, leftCutInd, rightCutInd, peakInd):
        plt.figure()
        plt.plot(self.potential, self.current);
        plt.plot(self.potential[[leftCutInd, rightCutInd, peakInd]],  self.current[[leftCutInd, rightCutInd, peakInd]], 'o');
        plt.plot(self.potential, self.linearFit, linewidth=0.3)
        plt.show()
        
        plt.figure()
        plt.plot(self.potential, self.current, label = "True Data")
        plt.plot(self.potential, self.baseline, label="Baseline Current")
        plt.show()
        


