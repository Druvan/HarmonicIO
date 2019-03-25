"""
Worker entry point.
"""
import threading
import urllib3
import json
import time
from concurrent.futures import ThreadPoolExecutor

from .configuration import Setting
from harmonicIO.general.services import SysOut, Services
from harmonicIO.general.definition import Definition, CRole
from harmonicIO.worker.docker_service import DockerService
from .garbage_collector import GarbageCollector
from .rest_service import RESTService

def run_rest_service():
    """
    Run rest as in a thread function
    """
    rest = RESTService()
    rest.run()


def start_gc_thread():
    """
    A thread that will continuously check for terminated containers and remove them
    """
    garbage_collector = GarbageCollector(10)
    gc_thread = threading.Thread(garbage_collector.collect_exited_containers())
    gc_thread.daemon = True
    gc_thread.start()

    SysOut.out_string("Garbage collector started")


def start_worker_updater():
    updater_thread = threading.Thread(target=update_worker_status)
    updater_thread.daemon = True
    updater_thread.start()

    SysOut.out_string("Started worker update loop")

def update_worker_status():
    """
    Update the worker status to the master as well as container info.
    """
    while True:
        # Get machine status by calling a unix command and fetch for load average
        try:
            content = Services.get_machine_status(Setting, CRole.WORKER)
            content[Definition.REST.get_str_docker()] = DockerService.get_containers_status()
            content[Definition.REST.get_str_local_imgs()] = DockerService.get_local_images()
            content["local_image_stats"] = DockerService.get_local_image_stats()
        except KeyboardInterrupt:
            break
        except Exception as e:
            SysOut.err_string("Encountered exception! {}".format(e))

        s_content = bytes(json.dumps(content), 'utf-8')

        html = urllib3.PoolManager()
        try:
            r = html.request('PUT', Definition.Master.get_str_check_master(Setting.get_master_addr(),
                                                                        Setting.get_master_port(),
                                                                        Setting.get_token()),
                            body=s_content)

            if r.status != 200:
                SysOut.err_string("Cannot update worker status to the master! {}").format(r)
            else:
                SysOut.debug_string("Reports status to master node complete.")

        except Exception as e:
            SysOut.err_string("Master is not available!")
            print(e)

        time.sleep(Setting.get_report_interval())



if __name__ == "__main__":
    """
    Entry point
    """
    SysOut.out_string("Running Harmonic Worker")
    SysOut.debug = True

    # Load configuration from file
    Setting.read_cfg_from_file()

    # Override master and repo address
    # Setting.set_variables_from_ev()

    # Print instance information
    SysOut.out_string("Node name: " + Setting.get_node_name())
    SysOut.out_string("Node internal address: " + Setting.get_node_internal_addr())
    if Setting.get_node_external_addr():
        SysOut.out_string("Node external address: " + Setting.get_node_external_addr())
    SysOut.out_string("Node port: " + str(Setting.get_node_port()))
    SysOut.out_string("Port range: {0} to {1} ({2} ports available)".format(Setting.get_data_port_start(),
                                                                 Setting.get_data_port_stop(),
                                                                 Setting.get_data_port_stop() -
                                                                 Setting.get_data_port_start()))

    # Init docker driver
    DockerService.init()

    # Create thread for handling REST Service
    pool = ThreadPoolExecutor()

    # Binding commander to the rest service and enable REST service
    pool.submit(run_rest_service)

    # Update the worker status
    pool.submit(start_worker_updater)

    # Start garbage collector thread
    pool.submit(start_gc_thread)
