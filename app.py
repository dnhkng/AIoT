import pyglet
import numpy as np
import usb
import threading
import time

VENDOR_ID     = 0x1234   #: Vendor Id
PRODUCT_ID    = 0x0000   #: Product Id for the bridged usb cable
INTERFACE_ID  = 0x81     #: The interface we use to talk to the device
PACKET_LENGTH = 0x40     #: 64 bytes

class NiaData():
    """ Looks after the collection and processing of NIA data"""
    def __init__(self) :
        self.points = 1024
        self.incoming_data = np.zeros(self.points * 2, dtype=np.uint32)
        self.processed_data = np.ones(4096, dtype=np.uint32)
        self.normalized_data = np.ones(4096, dtype=np.float32)
        self.fourier_data = np.zeros((280, 160), dtype=np.int8)
        self.device = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        self.nia_connected = True        
        try:        
            self.device.reset()
        except:
            self.nia_connected = False

    def _bulk_read(self):
        """ Read data off the NIA from its internal buffer, of up to 16 samples"""
        read_bytes = self.device.read(INTERFACE_ID, PACKET_LENGTH, timeout=30)
        return read_bytes

    def get_data(self):
        """ This function is called via threading, so that pyglet can plot the
        previous set of data whist this function collects the new data. 
        It sorts out the data into a list of the last seconds worth of data
        (~4096 samples)"""

        if self.nia_connected is False:
            self.normalized_data = np.random.randn(4096)
            time.sleep(0.250)
            return

        count = 0
        while True:
            bytes_data = self._bulk_read()
            point_count = int(bytes_data[54])

            for i in range(point_count):
                self.incoming_data[count + i] = int.from_bytes(bytes_data[i * 3:i * 3 + 3], byteorder='little')

            count = count + point_count

            if count >= self.points:
                break

        self.processed_data[:-count] = self.processed_data[count:]
        self.processed_data[-count:] = self.incoming_data[:count]

        mean, std = np.mean(self.processed_data), np.std(self.processed_data)

        self.normalized_data = np.where(self.processed_data > mean + std * 10, self.processed_data - 2 ** 16,
                                      self.processed_data)
        self.normalized_data = np.where(self.processed_data < mean - std * 10, self.processed_data + 2 ** 16,
                                      self.processed_data)
        self.normalized_data = self.normalized_data - mean
        self.normalized_data = self.normalized_data / std

    def waveform(self):
        """ This function takes a subset of the last second-worth of data,
        filters out frequecies over 30 Herz, and returns image data in a
        string for pyglet """
        x_max = np.max(np.abs(self.normalized_data))

        data = (self.normalized_data / x_max)*69 +70
        wave = np.ones((140,410), dtype=np.int8)
        wave = np.dstack((wave*0,wave*0,wave*51))
        for i in range(410):
            wave[int(data[i*2]),i,:] = [0,204,255]
        return wave.tostring()
	
    def fourier(self):
        """This function performs a fourier trasform on the last 140 samples taken
        with a Hanning window, and adds the normalised results to an array. The highest
        values is found and used to generate a marker to visualize the brains dominant frequency.
        The FT is also partitioned to represent 8 groups of frequencies, 4 alpha and 4 beta,
        as defined by the waves tuple. These, along with array of fourier data are returned to
        be plotted by pyglet
        """
        self.fourier_data[1:280, :] = self.fourier_data[0:279, :]
        x = abs(np.fft.fftn(self.normalized_data * np.hanning(self.points*4)))[5:45]
        x_max = max(x)
        x_min = min(x)
        x = (255*(x-x_min)/(x_max-x_min))
        pointer = np.zeros((160), dtype=np.int8)
        pointer[(np.argmax(x))*4:(np.argmax(x))*4+4]= 255
        y = np.vstack((x,x,x,x))
        y = np.ravel(y,'F')
        self.fourier_data[5, :] = y
        self.fourier_data[0:4, :] = np.vstack((pointer, pointer, pointer, pointer))
        fingers = []
        waves = (6,9,12,15,20,25,30,35, 40)
        for i in range(8):
            fingers.append(int(sum(x[waves[i]:waves[i+1]])/100))
        return self.fourier_data.tostring(), f_data = np.ones(4096, dtype=np.float32)ingers


def update(x):
    """ The main pyglet loop, this function starts a data collection thread, whilst
    processing and displying the previously collected data. At the end of the loop the
    threads are joined"""
    
    window.clear()

    data_thread = threading.Thread(target=nia_data.get_data)
    data_thread.start()

    fourier_data,steps = nia_data.fourier()

    waterfall = pyglet.image.ImageData(160,248,'I', fourier_data)
    waterfall.blit(20,20)

    for i in range(8):  # this blits the brain-fingers blocks
        for j in range(steps[i]):
            step.blit(i*50+210, j*15+180)


    graph = nia_data.waveform()
    graph_image = pyglet.image.ImageData(410,140,'RGB', graph)
    graph_image.blit(210,20)
    data_thread.join()


nia_data = NiaData()
window = pyglet.window.Window(640, 300)
step = pyglet.image.load('step.png')


pyglet.clock.schedule(update)
pyglet.app.run()
