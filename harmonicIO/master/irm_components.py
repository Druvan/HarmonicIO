import math
import queue
import threading
import json
import time
from urllib.request import urlopen
from urllib.error import HTTPError
import copy

from harmonicIO.general.services import SysOut
from harmonicIO.general.definition import Definition
from .binpacking import BinPacking, Bin
from .meta_table import LookUpTable
from .messaging_system import MessagesQueue
from .configuration import Setting, IRMSetting

BinStatus = Bin.ContainerBinStatus

class ContainerQueue():

    def __init__(self, ttl, queue_cap=0):
        self.__queue = queue.Queue(maxsize=queue_cap)
        self.container_queue_lock = threading.Lock()
        self.initial_TTL = ttl

    def queue_lock(self):
        self.container_queue_lock.acquire()
        #SysOut.debug_string("Acquired container queue lock! I am {}".format(threading.current_thread()))

    def queue_unlock(self):
        self.container_queue_lock.release()
        #SysOut.debug_string("Released container queue lock! I am {}".format(threading.current_thread()))

    def view_queue(self):
        return self.__queue.queue

    def update_containers(self, c_image, update_data):
        self.queue_lock()
        try:
            for item in self.__queue.queue:
                if item[Definition.Container.get_str_con_image_name()] == c_image:
                    item[Definition.get_str_size_data()] = update_data[Definition.get_str_size_data()]
        finally:
            self.queue_unlock()


    def put_container(self, container_data):
        self.queue_lock()
        try:
            if container_data.get(Definition.get_str_size_data()) == None:
                size_data = LookUpTable.ImageMetadata.get_metadata(container_data[Definition.Container.get_str_con_image_name()])
                  
                if size_data:
                    size_data = size_data.get(Definition.get_str_size_data())
                container_data[Definition.get_str_size_data()] = size_data

            ttl = container_data.get("TTL")
            if ttl == None:
                container_data["TTL"] = self.initial_TTL
            elif ttl > 0:
                container_data["TTL"] -= 1
            else:
                del container_data
                container_data = False
                SysOut.debug_string("Dropped container, TTL 0")

            if container_data:
                self.__queue.put(container_data)

        finally:
            self.queue_unlock()

    def get_current_queue_list(self):
        """
        dequeue all items currently available in queue and put into a list
        """
        current_list = []
        self.queue_lock()
        try:
            while True:
                current_list.append(self.__queue.get_nowait())
        except queue.Empty:
            pass
        finally:
            self.queue_unlock()
        return current_list


class ContainerAllocator():

    def __init__(self, packing_algo, autoscaling):
        config = IRMSetting()

        self.target_worker_number = 0
        self.container_q = ContainerQueue(ttl=config.ttl)
        self.packing_algorithm = packing_algo
        self.allocation_q = queue.Queue()
        self.allocation_lock = threading.Lock()
        self.bins = []
        self.bin_layout_lock = threading.Lock()
        self.size_descriptor = Definition.get_str_size_desc()

        self.packing_interval = config.packing_interval
        self.default_cpu_share = config.default_cpu_share
        self.profiler = WorkerProfiler(self.container_q, self, config.profiling_interval)
        if autoscaling:
            self.load_predictor = LoadPredictor(self, config.step_length,config.roc_lower, config.roc_upper,
                                                config.roc_minimum, config.queue_limit, config.waiting_time,
                                                config.large_increment, config.small_increment)

        print("Settings loaded!")

        # start threads that manage packing and queues
        bin_packing_manager = threading.Thread(target=self.packing_manager)
        bin_packing_manager.daemon=True
        bin_packing_manager.start()

        for _ in range(4):
            queue_manager_thread = threading.Thread(target=self.queue_manager)
            queue_manager_thread.daemon=True
            queue_manager_thread.start()

    def bin_lock(self):
        self.bin_layout_lock.acquire()
        #SysOut.debug_string("Acquired bin lock! I am {}".format(threading.current_thread()))

    def bin_unlock(self):
        self.bin_layout_lock.release()
        #SysOut.debug_string("Released bin lock! I am {}".format(threading.current_thread()))

    def queue_lock(self):
        self.allocation_lock.acquire()
        #SysOut.debug_string("Acquired allocation queue lock! I am {}".format(threading.current_thread()))

    def queue_unlock(self):
        self.allocation_lock.release()
        #SysOut.debug_string("Released allocation queue lock! I am {}".format(threading.current_thread()))

    def queue_manager(self):
        SysOut.debug_string("Started a queue manager thread! ID: {}".format(threading.current_thread()))
        deleteflag = "deleteme"
        while True:
            time.sleep(1)
            target_worker = None
            sid = None
            workers = LookUpTable.Workers.verbose()

            self.queue_lock()
            try:
                container_data = self.allocation_q.get_nowait().data
            except queue.Empty:
                continue
            finally:
                self.queue_unlock()


            if container_data["bin_status"] in [BinStatus.QUEUED, BinStatus.REQUEUED]:

                for worker in workers:
                    if workers[worker].get("bin_index", -99) == container_data["bin_index"]:
                        target_worker = (workers[worker][Definition.get_str_node_addr()], workers[worker][Definition.get_str_node_port()])

                if target_worker:
                    try:
                        sid = self.start_container_on_worker(target_worker, container_data)
                    except HTTPError as h:
                        SysOut.debug_string(h.msg)

                if sid and not sid == deleteflag:
                    container_data[Definition.Container.Status.get_str_sid()] = sid
                    container_data["bin_status"] = BinStatus.RUNNING
                    del container_data["TTL"]
                    #SysOut.debug_string("Added container with sid {}".format(sid))

                else:
                    self.bin_lock()
                    try:

                        #SysOut.debug_string("Could not start container on target worker! Requeueing as failed!\n")
                        container_data[Definition.Container.Status.get_str_sid()] = deleteflag

                        # ensure fresh copy of data is requeued and remove item from bins
                        new_container_data = copy.deepcopy(container_data)

                        self.bins[container_data["bin_index"]].remove_item_in_bin(Definition.Container.Status.get_str_sid(), deleteflag)
                        #SysOut.debug_string("Tried to delete container {} from bins, result: {}".format(container_data, deleted))
                        for field in ["bin_index", "bin_status", Definition.Container.Status.get_str_sid()]:
                            del new_container_data[field]

                    finally:
                        self.bin_unlock()

                    # requeue the copy
                    SysOut.debug_string("Requeueing new container: {}".format(new_container_data))
                    self.container_q.put_container(new_container_data)

            self.allocation_q.task_done()

    def packing_manager(self):
        SysOut.debug_string("Started bin packing manager! ID: {}".format(threading.current_thread()))
        while True:
            time.sleep(self.packing_interval)
            self.pack_containers()
            self.update_bins()

    def pack_containers(self):
        """
        perform bin packing with containers in workers, giving each container a worker to be allocated on and the amount of workers
        """
        container_list = self.container_q.get_current_queue_list()
        if len(container_list) > 0:
            self.bin_lock() # bin layout may not be mutated externally during packing
            try:
                # if any containers don't yet have average cpu usage, add default value now
                for cont in container_list:
                    if cont.get(Definition.get_str_size_data()) == None:
                        cont[Definition.get_str_size_data()] = {}
                        cont[Definition.get_str_size_data()][self.size_descriptor] = self.default_cpu_share
                        cont[Definition.get_str_size_data()][Definition.get_str_memory_avg()] = self.default_cpu_share
                        
                        SysOut.debug_string("Container {} added size".format(cont))
                bins_layout = self.packing_algorithm(container_list, self.bins)
                self.bins = bins_layout

                for bin_ in self.bins:
                    for item in bin_.items:
                        if item.data["bin_status"] == BinStatus.PACKED:
                            item.data["bin_status"] = BinStatus.QUEUED
                            self.__enqueue_container(item)
            finally:
                self.bin_unlock()
        self.target_worker_number = len(self.bins) + self.calculate_overhead_workers(len(self.bins))


    def update_bins(self):
        """
        Updates the bins, removing the last ones that are not currently used
        """
        self.bin_lock()
        try:
            while len(self.bins) > 0:
                last_bin_index = len(self.bins) - 1
                if not self.bins[last_bin_index].items:
                    del self.bins[last_bin_index]
                else:
                    break
        finally:
            self.bin_unlock()

    #ISSUE: had list index out of range on 224

    def calculate_overhead_workers(self, number_of_current_workers):
        """
        calculates a suggested amount of additional workers to have some headroom with available workers, based on some logarithmic proportion when above 10 workers
        """
        if number_of_current_workers < 10:
            return 1
        elif number_of_current_workers < 100:
            return math.ceil(math.log(number_of_current_workers)*0.5)
        else:
            return math.trunc(math.log(number_of_current_workers))

    def __enqueue_container(self, container):
        self.queue_lock()
        try:
            self.allocation_q.put(container)
        finally:
            self.queue_unlock()

    def update_binned_containers(self, update_data):
        """
        update all containers of the same image as in update_data within all bins
        """
        self.bin_lock()
        try:
            for bin_ in self.bins:
                bin_.update_items_in_bin(Definition.Container.get_str_con_image_name(), update_data)
        finally:
            self.bin_unlock()

    def update_queued_containers(self, c_name, update_data):
        self.queue_lock()
        try:
            for item in self.allocation_q.queue:
                if item.data[Definition.Container.get_str_con_image_name()] == c_name:
                    for field in [self.size_descriptor]:
                        item.data[field] = update_data[field]
        finally:
            self.queue_unlock()

    def remove_container_by_id(self, csid):
        """
        remove container with specified short_id. Should only be called via external event when a container finishes and exits the system
        or when container could not be allocated after being packed and queued
        """
        target_bin = -1
        self.bin_lock()
        try:
            for _bin in self.bins:
                for item in _bin.items:
                    if item.data.get(Definition.Container.Status.get_str_sid(), "") == csid:
                        target_bin = _bin.index
                        break

            if target_bin > -1:
                self.bins[target_bin].remove_item_in_bin(Definition.Container.Status.get_str_sid(), csid)

        finally:
            self.bin_unlock()
            return True if target_bin > -1 else False

    def start_container_on_worker(self, target_worker, container):
        # send request to worker
        cont = dict(container)
         
        cont[Definition.Container.get_str_cpu_share()] = container[Definition.get_str_size_data()][self.size_descriptor]
        worker_url = "http://{}:{}/docker?token=None&command=create".format(target_worker[0], target_worker[1])
        req_data = bytes(json.dumps(cont), 'utf-8')
        resp = urlopen(worker_url, req_data)

        if resp.getcode() == 200: # container was created
            sid = str(resp.read(), 'utf-8')
            print("Received sid from container: " + sid)
            return sid
        return None




class WorkerProfiler():

    def __init__(self, cq, ca, interval):
        self.c_queue = cq
        self.c_allocator = ca
        self.update_interval = interval
        #NOTE: update fields not used, fix and start using? Can't recall why container os string is included...
        #self.update_fields = [Definition.Container.get_str_container_os, "bin_status", "bin_index", ca.size_descriptor]

        self.updater_thread = threading.Thread(target=self.update_container_information)
        self.updater_thread.daemon=True
        self.updater_thread.start()

    def update_container_information(self):
        SysOut.debug_string("Started a profiler thread! ID: {}".format(threading.current_thread()))
        while True:
            time.sleep(self.update_interval)

            # gather metadata about containers and put in meta table
            SysOut.debug_string("Profiling container metadata")
            self.gather_container_metadata()

            # update all containers in both container and allocation queues (as they are waiting) and in the bins with new data from the meta table
            for container_image in LookUpTable.ImageMetadata.verbose():
                container_data = LookUpTable.ImageMetadata.get_metadata(container_image)
                container_data[Definition.Container.get_str_con_image_name()] = container_image
                #SysOut.debug_string("Updating containers with image name {} with following data: {}".format(container_image, container_data))

                # container queue
                self.c_queue.update_containers(container_image, container_data)
                #SysOut.debug_string("Updated container queue")

                # allocation queue
                self.c_allocator.update_queued_containers(container_image, container_data)
                #SysOut.debug_string("Updated allocation queue")

                # bins
                self.c_allocator.update_binned_containers(container_data)
                #SysOut.debug_string("Updated bins")

    def gather_container_metadata(self):
        """
        transfers data from individual containers in metadata to container image-based metadata which is more interesting
        for the resource manager, such as average cpu usage across all instances of a specific container image.
        """
        running_containers = LookUpTable.Containers.running_containers()
        current_workers = LookUpTable.Workers.verbose()
        SysOut.debug_string("Gathering metadata for containers: {}".format(running_containers))
        for container_name in running_containers:
            total_counter = 0
            avg_sum = {}
            for worker in current_workers:
                local_counter = 0
                if container_name in current_workers[worker]["local_image_stats"]:
                    for local in current_workers[worker][Definition.REST.get_str_docker()]:
                        if local[Definition.Container.Status.get_str_image()] == container_name:
                            local_counter +=1
                    for descriptor in current_workers[worker]["local_image_stats"][container_name]:
 
                        avg_sum[descriptor] = avg_sum.get(descriptor,0) + current_workers[worker]["local_image_stats"][container_name][descriptor] * local_counter
                    [self.c_allocator.size_descriptor] * local_counter
                total_counter += local_counter
            if total_counter:
                data = {}
                for descriptor in avg_sum:
                    data[descriptor] = avg_sum[descriptor]/total_counter
                LookUpTable.ImageMetadata.push_metadata(container_name, data)


class LoadPredictor():

    def __init__(self, cm, step, lower, upper, minimum, q_size_limit, waiting_time, large, small):
        self.c_manager = cm
        self.step_length = step
        self.image_data = {}

        self.roc_positive_lower = lower
        self.roc_positive_upper = upper
        self.roc_minimum = minimum
        self.queue_length_limit = q_size_limit
        self.wait_time = waiting_time
        self.large_increment = large
        self.small_increment = small

        self.analyzer_thread = threading.Thread(target=self.analyze_roc_for_autoscaling)
        self.analyzer_thread.daemon = False
        self.analyzer_thread.start()

    def calculate_roc_per_image(self):
        current_queue = MessagesQueue.verbose()
        for image in current_queue:
            if not self.image_data.get(image):
                self.image_data[image] = {"roc" : current_queue[image]/self.step_length, "previous" : current_queue[image]}
            else:
                self.image_data[image]["roc"] = int((current_queue[image] - self.image_data[image]["previous"]) / self.step_length)
                self.image_data[image]["previous"] = current_queue[image]

    def queue_container(self, container_data):
        self.c_manager.container_q.put_container(container_data)

    def analyze_roc_for_autoscaling(self):
        SysOut.debug_string("Started a load predictor thread! ID: {}".format(threading.current_thread()))
        while True:
            time.sleep(self.step_length)
            self.calculate_roc_per_image()

            for image in self.image_data:

                last_start = self.image_data[image].get("last_start", 0)
                if int(time.time()) - last_start > self.wait_time:

                    # a new container was not recently started so action should be taken if needed
                    roc = self.image_data[image]["roc"]
                    increment = 0
                    image_queue_length = MessagesQueue.verbose().get(image, 0)

                    # decide how many containers should be added, if any, and send these to the container queue
                    # cases: RoC above either limit or RoC negative but queue length above limit
                    if roc > self.roc_positive_upper:
                        increment = self.large_increment
                    elif image_queue_length > self.queue_length_limit and roc > self.roc_minimum:
                        increment = self.large_increment
                    elif roc > self.roc_positive_lower:
                        increment = self.small_increment
                    elif image_queue_length > self.queue_length_limit:
                        increment = self.small_increment

                    if increment > 0:
                        for _ in range(increment):
                            self.queue_container({Definition.Container.get_str_con_image_name() : image, "volatile" : True})
                        self.image_data[image]["last_start"] = int(time.time())


