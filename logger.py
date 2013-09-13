from epoc import EmotivEPOC
from time import clock, sleep

# Enumerations for EEG channels (14 channels)
CH_F3, CH_FC5, CH_AF3, CH_F7, CH_T7,  CH_P7, CH_O1,\
CH_O2, CH_P8,  CH_T8,  CH_F8, CH_AF4, CH_FC6,CH_F4 = range(14)

emotiv = EmotivEPOC()

print("Enumerating devices...")
try:
    emotiv.enumerate()
except EmotivEPOCNotFoundException, e:
    if emotiv.permissionProblem:
        print("Please make sure that device permissions are handled.")
    else:
        print("Please make sure that device permissions are handled or"\
                " at least 1 Emotiv EPOC dongle is plugged.")
    sys.exit(1)

for k,v in emotiv.devices.iteritems():
    print("Found dongle with S/N: %s" % k)

emotiv.setupEncryption()
from psychopy.core import getTime
import numpy as np

SAMPLE_SIZE=1000
MAX_TEST_SECS=30.0

no_data_durs = np.zeros(SAMPLE_SIZE)
battery_durs = np.zeros(SAMPLE_SIZE)
signal_durs = np.zeros(SAMPLE_SIZE)
sig_i,bat_i,none_i=(0,0,0)
groups_collected=0

test_start=getTime()

def printGroupStats(sample_array,sample_count,sample_type_label):
    if  sample_count > 0:
        sample_array=sample_array[:sample_count]

    if  sample_count > 0 or  sample_count == -1:
        print sample_type_label,' ( in msec ):'
        print '\tCount:',len(sample_array)
        print '\tMin:',sample_array.min()
        print '\tMax:',sample_array.max()
        print '\tmean:',sample_array.mean()
        print '\tmedian:',np.median(sample_array)
        print '\tstd:',sample_array.std()
        print
    else:
        print 'Warning: {0} collected no sample data'.format(sample_type_label)

try:
    while getTime()-test_start<MAX_TEST_SECS and groups_collected<3:
        start_time=getTime()*1000.0
        signal = emotiv.getSignal()
        sig_time=getTime()*1000.0
        battery = emotiv.getBatteryLevel()
        battery_time=getTime()*1000.0

        sig_dur=sig_time-start_time
        bat_dur=battery_time-sig_time
        total_dur=sig_dur+bat_dur
        #we need to print in the try clause to avoid printing errors on the battery packet (count=128)
        try:
            for index, electrode in enumerate(signal):
                # we know it is a signal event*
                if sig_i<SAMPLE_SIZE:
                    signal_durs[sig_i]=sig_dur
                    sig_i+=1
                elif sig_i==SAMPLE_SIZE and sig_i!=-1:
                    sig_i=-1

            printGroupStats(signal_durs,"Signal Read Stats")
            groups_collected+=1
            break;
        except:
            if battery:
            # We know it is a battery reading???? IS THIS THE CASE?
                if bat_i<SAMPLE_SIZE:
                    battery_durs[bat_i]=bat_dur
                    bat_i+=1
                elif bat_i==SAMPLE_SIZE and bat_i!=-1:
                    bat_i=-1

            printGroupStats(battery_durs,bat_i,"Battery Read Stats")
            groups_collected+=1
            break;

        else:
        # We know no new data was available. ???? *IS THIS THE CASE?*
            if none_i<SAMPLE_SIZE:
                no_data_durs[none_i]=total_dur
                none_i+=1
            elif none_i==SAMPLE_SIZE and none_i!=-1:
                none_i=-1

        printGroupStats(no_data_durs,none_i,"No data Read Stats")
        groups_collected+=1
        break;

try:
    while True:
        signal = emotiv.getSignal()
        battery = emotiv.getBatteryLevel()
        #we need to print in the try clause to avoid printing errors on the battery packet (count=128)
        try:
            for index, electrode in enumerate(signal):
                #print emotiv.channelNames[index], signal[index]
                pass
        except:
            print battery
except KeyboardInterrupt, ke:
    emotiv.disconnect()
    sys.exit(1)
