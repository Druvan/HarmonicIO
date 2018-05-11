import socket
import docker
from .configuration import Setting
from harmonicIO.general.definition import CStatus, Definition
from harmonicIO.general.services import SysOut

from docker.errors import APIError
from requests.exceptions import HTTPError

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

        self.__client = docker.from_env()

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

        def get_container_status(input):
            res = dict()
            res[Definition.Container.Status.get_str_sid()] = input.short_id
            res[Definition.Container.Status.get_str_image()] = input.image.tags
            res[Definition.Container.Status.get_str_status()] = input.status
            return res

        res = []
        try:
            for item in self.__client.containers.list(all=True):
                res.append(get_container_status(item))
        except (ApiError, HTTPError, docker.errors.NotFound) as e:
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
        except (ApiError, HTTPError) as e:
            SysOut.err_string("Could not remove requested container, exception:\n{}".format(e))
            return False

    def cpu_per_container(self):
        pass

    def calculateCPUPercent(self, container):

        containers = {}
        for container in self.__client.container.list():

            stats = self.__client.api.stats(container.name, stream=False)
            # calculate the change for the cpu usage of the container in between readings
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
            #   // calculate the change for the entire system between readings
            # 
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
            if system_delta > 0.0 and cpu_delta > 0.0:

                # put this data with the container's image name:tag
                containers[(str(container.image)).split('\'')[1]] = (cpu_delta / system_delta) * len(stats["cpu_stats"]["cpu_usage"]["percpu_usage"]) * 100.0


            


    def run_container(self, container_name, volatile=False):

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
                                               cpu_shares=512,
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
                return res.short_id
            else:
                SysOut.out_string("Container " + container_name + " cannot be created!")
                return False
