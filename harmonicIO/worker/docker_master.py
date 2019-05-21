import socket
import docker
from time import mktime
from datetime import datetime
from psutil import virtual_memory
from .configuration import Setting
from harmonicIO.general.definition import CStatus, Definition
from harmonicIO.general.services import SysOut

from docker.errors import APIError, NotFound
from requests.exceptions import HTTPError
from json.decoder import JSONDecodeError

class ChannelStatus(object):
    def __init__(self, port):
        self.port = port
        if self.is_port_open():
            self.status = CStatus.BUSY
        else:
            self.status = CStatus.AVAILABLE

    def is_port_open(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', self.port))
        sock.close()

        if result == 0:
            return True

        return False


class DockerMaster(object):

    def __init__(self):
        self.__ports = []
        self.max_memory = virtual_memory().total
        self.__client = docker.from_env()
        self.max_network_bandwidth = Setting.get_bandwidth() * 1000000 # From MB to bytes
        self.prev_network = {}

        SysOut.out_string("Docker master initialization complete.")

        # Define port status
        for port_num in range(Setting.get_data_port_start(), Setting.get_data_port_stop()):
            self.__ports += [ChannelStatus(port_num)]

        # Check number of available port
        available_port = 0
        for item in self.__ports:
            if item.status == CStatus.AVAILABLE:
                available_port += 1

        self.__available_port = available_port

    def __get_available_port(self):
        for item in self.__ports:
            if item.status == CStatus.AVAILABLE:
                item.status = CStatus.BUSY
                return item.port

        return None

    def __update_ports(self):
        for port in self.__ports:
            if port.is_port_open():
                port.status = CStatus.BUSY
            else:
                port.status = CStatus.AVAILABLE

    def get_containers_status(self):

        def get_container_status(cont):
            res = dict()
            res[Definition.Container.Status.get_str_sid()] = cont.id[:12]
            res[Definition.Container.Status.get_str_image()] = (str(cont.image)).split('\'')[1]
            res[Definition.Container.Status.get_str_status()] = cont.status
            return res

        res = []
        try:
            for item in self.__client.containers.list(all=True):
                res.append(get_container_status(item))
        except (APIError, HTTPError, NotFound) as e:
            SysOut.err_string("Could not find requested container, exception:\n{}".format(e))
            # To print all logs:
            #print(item.logs(stdout=True, stderr=True))

        return res

    def get_local_images(self):
        # get a list of all tags of all locally available images on this machine
        imgs = self.__client.images.list()
        local_imgs = []
        for img in imgs:
            local_imgs += img.tags

        return local_imgs

    def delete_container(self, cont_shortid):
        # remove a container from the worker by provided short id, only removes exited containers
        try:
            self.__client.containers.get(cont_shortid).remove()
            return True
        except (APIError, HTTPError, NotFound) as e:
            SysOut.err_string("Could not remove requested container, exception:\n{}".format(e))
            return False

    def stats_info_per_container(self):

        containers = {}
        tmp_containers = {}
        counts = {}

        try:
            conts_to_check = self.__client.containers.list(all=False)
        except AttributeError as e:
            SysOut.err_string(e)
            conts_to_check = []

        SysOut.debug_string("Containers to check: {}".format(conts_to_check))
        deb_individual = {}

        for container in conts_to_check:
            container_name = (str(container.image)).split('\'')[1]
            stats = self.get_container_stats(container)
            current_cont_stats = {}
            if stats:
                if not container_name in containers:
                    containers[container_name] = {}
                    tmp_containers[container_name] = {}
                
                # Add new measurement types here
                current_cont_stats[Definition.get_str_size_desc()] = self.calculate_cpu_usage(stats)
                current_cont_stats[Definition.get_str_memory_avg()] = self.calculate_memory_usage(stats)
                current_cont_stats[Definition.get_str_network_avg()] = self.calculate_network_usage(stats,container_name)
                
                if not container_name in deb_individual:
                    deb_individual[container_name] = {}
                for type_name, type_value in current_cont_stats.items(): 
                    if(current_cont_stats[type_name] != None):
                        tmp_containers[container_name][type_name] = tmp_containers[container_name].get(type_name,0) + current_cont_stats[type_name]
                        self.add_debug_info(deb_individual[container_name],type_name[4:],current_cont_stats[type_name])
                
                if( not tmp_containers[container_name] ):
                    del tmp_containers[container_name]
                    continue
                count = counts.get(container_name,0) + 1
                counts[container_name] = count
                
        for container_name,tmp_container in tmp_containers.items():
            
            count = counts[container_name]
            for type_name,type_avg in tmp_container.items():
                self.update_avg_info(containers[container_name],type_name,type_avg,count)
        
        containers["DEBUG"] = deb_individual

        SysOut.debug_string("Size per container: {}".format(containers))
        return containers

    def update_avg_info(self,container_dict,info_key,sum,count):
        if(count > 0):
            avg = sum/count
        else: 
            avg = 0

        container_dict[info_key] = avg
        
    def calc_procent(self, numinator, denominator):

        procent = None

        if(denominator != 0):
            procent = numinator/denominator

        return procent

    def add_debug_info(self,container_dict,info_key,info):
        
        if not info_key in container_dict:
            container_dict[info_key] = []
        container_dict[info_key].append(info)

        return container_dict



    def get_container_stats(self, container):

        try:
            stats = self.__client.api.stats(container.name, stream=False)
            
        except (NotFound, HTTPError):
            stats = None
        
        return stats

    def calculate_network_usage(self,stats,container_name):
        """
        calculate given container stats
        Returns network usage of container across instances on current worker as a fraction of maximum network usage (1.0).
        Based on framework: https://github.com/eon01/DoMonit/blob/master/domonit/stats.py
        """
        i=0
        network_usage_procent = None
        if stats:
            try:
                network_stats = stats['networks']
                current_bytes = 0

                for nic in network_stats.values():
                    current_bytes += nic.get('rx_bytes') + nic.get('tx_bytes')

                current_time = datetime.strptime(stats.get('read')[0:26],'%Y-%m-%dT%H:%M:%S.%f')
                prev_network = self.prev_network.get(container_name)

                if prev_network:
                    prev_bytes = prev_network.get('bytes')
                    prev_time = prev_network.get('time')
                    diff_time = (current_time - prev_time).total_seconds()
                    network_stats_usage = 0
                    for nic in network_stats.values():
                        network_stats_usage += nic.get('rx_bytes',0) + nic.get('tx_bytes',0)
                    network_stats_usage - prev_bytes
                    
                    network_usage_procent = self.calc_procent(network_stats_usage, self.max_network_bandwidth)
                self.prev_network[container_name] = {'bytes' : current_bytes,'time' : current_time,"stats" : stats}
            except (KeyError, JSONDecodeError):
                network_usage_procent = None

        return network_usage_procent

    def calculate_memory_usage(self,stats):
        """
        calculate given container stats
        Returns memory usage of container across instances on current worker as a fraction of maximum memory usage (1.0).
        Based on framework: https://github.com/eon01/DoMonit/blob/master/domonit/stats.py
        """
        memory_usage_procent = None
        
        if stats:
            try:
                memory_stats_usage = int(stats['memory_stats']['usage'])
                memory_stats_limit = self.max_memory

                memory_usage_procent = self.calc_procent(memory_stats_usage, memory_stats_limit)
            except (KeyError, JSONDecodeError):
                memory_usage_procent = None

        return memory_usage_procent

    def calculate_cpu_usage(self, stats):
        """
        calculate given container stats
        Returns CPU usage of container across instances on current worker as a fraction of maximum cpu usage (1.0).
        Based on discussion here: https://stackoverflow.com/questions/30271942/get-docker-container-cpu-usage-as-percentage
        """

        current_CPU = None
        if stats:
            try:
                # calculate the change for the cpu usage of the container in between readings
                cpu_delta = float(stats["cpu_stats"]["cpu_usage"]["total_usage"]) - float(stats["precpu_stats"]["cpu_usage"]["total_usage"])
                # calculate the change for the entire system between readings
                system_delta = float(stats["cpu_stats"]["system_cpu_usage"]) - float(stats["precpu_stats"]["system_cpu_usage"])

                #if system_delta > 0.0 and cpu_delta > 0.0:
                current_CPU = self.calc_procent(cpu_delta, system_delta) # Num of cpu's: len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"])

            except (KeyError, JSONDecodeError):
                current_CPU = None

        return current_CPU

    def run_container(self, container_name, cpu_share=0.5, volatile=False):

        def get_ports_setting(expose, ports):
            return {str(expose) + '/tcp': ports}

        def get_env_setting(expose, a_port, volatile):
            ret = dict()
            ret[Definition.Docker.HDE.get_str_node_name()] = container_name
            ret[Definition.Docker.HDE.get_str_node_addr()] = Setting.get_node_addr()
            ret[Definition.Docker.HDE.get_str_node_rest_port()] = Setting.get_node_port()
            ret[Definition.Docker.HDE.get_str_node_data_port()] = expose
            ret[Definition.Docker.HDE.get_str_node_forward_port()] = a_port
            ret[Definition.Docker.HDE.get_str_master_addr()] = Setting.get_master_addr()
            ret[Definition.Docker.HDE.get_str_master_port()] = Setting.get_master_port()
            ret[Definition.Docker.HDE.get_str_std_idle_time()] = Setting.get_std_idle_time()
            ret[Definition.Docker.HDE.get_str_token()] = Setting.get_token()
            if volatile:
                ret[Definition.Docker.HDE.get_str_idle_timeout()] = Setting.get_container_idle_timeout()
            return ret

        self.__update_ports()

        port = self.__get_available_port()
        expose_port = 80

        if not port:
            SysOut.err_string("No more port available!")
            return False
        else:
            print('starting container ' + container_name)
            res = self.__client.containers.run(container_name,
                                               detach=True,
                                               stderr=True,
                                               stdout=True,
                                               cpu_shares=max(2, int(1024*cpu_share)),
                                               mem_limit='1g',
                                               ports=get_ports_setting(expose_port, port),
                                               environment=get_env_setting(expose_port, port, volatile))
            import time
            time.sleep(1)
            print('..created container, logs:')
            print(res.logs(stdout=True, stderr=True))

            if res:
                SysOut.out_string("Container " + container_name + " is created!")
                SysOut.out_string("Container " + container_name + " is " + res.status + " ")
                # return short id of container
                return res.id[:12] # Docker API truncates short id to only 10 characters, while internally 12 are used
            else:
                SysOut.out_string("Container " + container_name + " cannot be created!")
                return False
