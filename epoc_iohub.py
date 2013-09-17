import numpy as np
import threading
from Queue import Queue, Empty
import usb
from bitstring import BitArray
from Crypto.Cipher import AES

CH_F3, CH_FC5, CH_AF3, CH_F7, CH_T7,  CH_P7, CH_O1,\
CH_O2, CH_P8,  CH_T8,  CH_F8, CH_AF4, CH_FC6,CH_F4 = range(14)
class EPOCError(Exception):
    """Base class for exceptions in this module."""
    pass

class EPOCTurnedOffError(EPOCError):
    """Exception raised when Emotiv EPOC is not turned on."""
    pass

class EPOCUSBError(EPOCError):
    """Exception raised when error occurs during I/O operations."""
    pass

class EmotivDataAcquisitionThread(threading.Thread):
    def __init__(self, msg_queue, device, cipher, group=None, target=None, name=None, args=(), kwargs={}):
        # So the Queue should be created in the iohub EmotivDevice and then passed into the
        # EmotivDataAcquisitionThread init method.
        self.msg_queue=msg_queue
        self.device = device
        self.cipher = cipher

        self.is_running=False
        threading.Thread.__init__(self,group, target, name, args, kwargs)

        # Define a contact quality ordering
        # See:
        #   github.com/openyou/emokit/blob/master/doc/emotiv_protocol.asciidoc
        # For counter values between 0-15
        self.cqOrder = ["F3", "FC5", "AF3", "F7", "T7",  "P7",  "O1",
                        "O2", "P8",  "T8",  "F8", "AF4", "FC6", "F4",
                        "F8", "AF4"]
        # 16-63 is currently unknown
        self.cqOrder.extend([None,] * 48)
        # Now the first 16 values repeat once more and ends with 'FC6'
        self.cqOrder.extend(self.cqOrder[:16])
        self.cqOrder.append("FC6")
        # Finally pattern 77-80 repeats until 127
        self.cqOrder.extend(self.cqOrder[-4:] * 12)

        # Channel names
        self.channelNames = ["F3", "FC5", "AF3", "F7", "T7", "P7", "O1",
                             "O2", "P8",  "T8",  "F8", "AF4","FC6","F4"]

        ##################
        # ADC parameters #
        # ################

        # Sampling rate: 128Hz (Internal: 2048Hz)
        self.sampling_rate = 128

        # Vertical resolution (0.51 microVolt)
        self.resolution = 0.51

        # Each channel has 14 bits of data
        self.ch_bits = 14

        self.sample_buffer=np.ndarray([1,14])

        # Battery levels
        # github.com/openyou/emokit/blob/master/doc/emotiv_protocol.asciidoc
        self.battery_levels = {247:99, 246:97, 245:93, 244:89, 243:85,
                               242:82, 241:77, 240:72, 239:66, 238:62,
                               237:55, 236:46, 235:32, 234:20, 233:12,
                               232: 6, 231: 4, 230: 3, 229: 2, 228: 1,
                               227: 1, 226: 1,
                               }
        # 100% for bit values between 248-255
        self.battery_levels.update(dict([(k,100) for k in range(248, 256)]))
        # 0% for bit values between 128-225
        self.battery_levels.update(dict([(k,0)   for k in range(128, 226)]))
        self.battery = 0
        self.quality = {
                            "F3" : 0, "FC5" : 0, "AF3" : 0, "F7" : 0,
                            "T7" : 0, "P7"  : 0, "O1"  : 0, "O2" : 0,
                            "P8" : 0, "T8"  : 0, "F8"  : 0, "AF4": 0,
                            "FC6": 0, "F4"  : 0,
                       }
    def run(self):
        # This is called when the thread is started, and is where you would get any new event data from
        # the actual emotive device. Any new events would be put in the msg_queue so the iohub
        # EmotivDevice can get events on the queue
        self.is_running=True
        while self.is_running==True:
            try:
                raw = self.device.read(32,timeout=10)
                bits = BitArray(bytes=self.cipher.decrypt(raw))
            except usb.USBError as e:
                if e.errno == 110:
                    raise EPOCTurnedOffError("Make sure that headset is turned on")
                else:
                    raise EPOCUSBError("USB I/O error with errno = %d" % usb_exception.errno)
            else:
                # Counter / Battery
                if bits[0]:
                    self.battery = self.battery_levels[bits[0:8].uint]
                else:
                    self.counter = bits[0:8].uint
                    ## Connection quality available with counters
                    try:
                        self.quality[self.cqOrder[self.counter]] = bits[107:121].uint
                        #print(self.quality[self.cqOrder[self.counter]])
                    except KeyError:
                        pass

                    #signal
                    self.sample_buffer[0][CH_F3] = bits[8:22].uint
                    self.sample_buffer[0][CH_FC5] = bits[22:36].uint
                    self.sample_buffer[0][CH_AF3] = bits[36:50].uint
                    self.sample_buffer[0][CH_F7] = bits[50:64].uint
                    self.sample_buffer[0][CH_T7] = bits[64:78].uint
                    self.sample_buffer[0][CH_P7] = bits[78:92].uint
                    self.sample_buffer[0][CH_O1] = bits[92:106].uint
                    self.sample_buffer[0][CH_O2] = bits[134:148].uint
                    self.sample_buffer[0][CH_P8] = bits[148:162].uint
                    self.sample_buffer[0][CH_T8] = bits[162:176].uint
                    self.sample_buffer[0][CH_F8] = bits[176:190].uint
                    self.sample_buffer[0][CH_AF4] = bits[190:204].uint
                    self.sample_buffer[0][CH_FC6] = bits[204:218].uint
                    self.sample_buffer[0][CH_F4] = bits[218:232].uint

                    ## Gyroscope
                    self.gyroX = bits[233:240].uint - 106
                    self.gyroY = bits[240:248].uint - 106

                    # we put a 4 element dict in the msg queue
                    self.msg_queue.put({'signal':self.sample_buffer[0],
                                        'gyro':(self.gyroX,self.gyroY),
                                        'battery':self.battery,
                                        'quality':self.quality})
class EmotivDevice(object):

    # These seem to be the same for every device

    INTERFACE_DESC = "Emotiv RAW DATA"
    MANUFACTURER_DESC = "Emotiv Systems Pty Ltd"
    __slots__=("_packetLoss","_counter","_battery","_quality","_gyro", "_signal", "_msg_q", "_device",
               "_serial", "_key", "_cipher", "_ac_thread")

    def __init__(self, serialNumber=None):

        # Any attributes of the class that can / should have the same
        # value across instances of the class should be moved
        # to be class attributes as shown for INTERFACE_DESC , MANUFACTURER_DESC
        # Any attributes which should be at an instance level need to defined as slots.
        # as shown for the data acq. attributes.

        # All the recoding specific code has been moved to
        # EmotivDataAcquisitionThread class
        # EmotivDevice scans for the device, defines queues, starts the acquisition thread and gets
        # the data from it in a non-blocking way

        # Acquired data
        self._packetLoss = 0
        self._counter = 0
        self._battery = 0
        self._gyro = 0
        self._signal = []
        self._quality = []

        # Queue
        self._msg_q = Queue()

        # Initialize device
        self._enumerate()
        self._setupEncryption()
        # acquisition thread
        self._ac_thread=EmotivDataAcquisitionThread(self._msg_q, self._device, self._cipher)

    def _is_emotiv_epoc(self, device):
        """Custom match function for libusb."""
        try:
            manu = usb.util.get_string(device, len(self.MANUFACTURER_DESC),
                                       device.iManufacturer)
        except usb.core.USBError, ue:
            # Skip failing devices as it happens on Raspberry Pi
            if ue.errno == 32:
                return False
            elif ue.errno == 13:
                pass
        else:
            if manu == self.MANUFACTURER_DESC:
                # Found a dongle, check for interface class 3
                for interf in device.get_active_configuration():
                    ifStr = usb.util.get_string(device, len(self.INTERFACE_DESC),
                                                interf.iInterface)
                    if ifStr == self.INTERFACE_DESC:
                        return True

    def _enumerate(self):
        """Scans the usb system for the device"""
        devs = usb.core.find(find_all=True, custom_match=self._is_emotiv_epoc)

        if not devs:
            raise EmotivEPOCNotFoundException("No plugged Emotiv EPOC")

        for dev in devs:
            sn = usb.util.get_string(dev, 32, dev.iSerialNumber)
            cfg = dev.get_active_configuration()

            for interf in dev.get_active_configuration():
                if dev.is_kernel_driver_active(interf.bInterfaceNumber):
                    # Detach kernel drivers and claim through libusb
                    dev.detach_kernel_driver(interf.bInterfaceNumber)
                    usb.util.claim_interface(dev, interf.bInterfaceNumber)

            # 2nd interface is the one we need
            self._device = usb.util.find_descriptor(interf,
                                 bEndpointAddress=usb.ENDPOINT_IN|2)
            self._serial = sn
            break

    def _setupEncryption(self, research=True):
        """Generate the encryption key and setup Crypto module.
        The key is based on the serial number of the device and the
        information whether it is a research or consumer device.
        """
        if research:
            self._key = ''.join([self._serial[15], '\x00',
                                self._serial[14], '\x54',
                                self._serial[13], '\x10',
                                self._serial[12], '\x42',
                                self._serial[15], '\x00',
                                self._serial[14], '\x48',
                                self._serial[13], '\x00',
                                self._serial[12], '\x50'])
        else:
            self._key = ''.join([self._serial[15], '\x00',
                                self._serial[14], '\x48',
                                self._serial[13], '\x00',
                                self._serial[12], '\x54',
                                self._serial[15], '\x10',
                                self._serial[14], '\x42',
                                self._serial[13], '\x00',
                                self._serial[12], '\x50'])

        self._cipher = AES.new(self._key)


    def startAcuisition(self):
        self._ac_thread.start()

    def getSignal(self):
        try:
            sig = self._msg_q.get(block=False)['signal']
            return sig
        except Empty:
            return None

    def getGyro(self):
        try:
            sig = self._msg_q.get(block=False)['gyro']
            return sig
        except Empty:
            return None

    def getContactQuality(self):
        try:
            sig = self._msg_q.get(block=False)['quality']
            return sig
        except Empty:
            return None

    def getBatteryLevel(self):
        """Returns the battery level."""
        try:
            sig = self._msg_q.get(block=False)['battery']
            return sig
        except Empty:
            return None

    def disconnect(self):
        """Release the claimed interfaces."""

        for dev in self.devices.values():
            cfg = dev.get_active_configuration()

            for interf in dev.get_active_configuration():
                usb.util.release_interface(dev, interf.bInterfaceNumber)
