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

try:
    while True:
        signal = emotiv.getSignal()
        battery = emotiv.getBatteryLevel()
        #we need to print in the try clause to avoid printing errors on the battery packet (count=128)
        try:
            for index, electrode in enumerate(signal):
                print emotiv.channelNames[index], signal[index]
        except:
            pass
except KeyboardInterrupt, ke:
    emotiv.disconnect()
    sys.exit(1)
