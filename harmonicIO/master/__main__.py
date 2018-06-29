from harmonicIO.general.services import SysOut
from .jobqueue import JobManager
from harmonicIO.master.resource_manager import IntelligentResourceManager
from harmonicIO.master.binpacking import BinPacking
from harmonicIO.master.meta_table import LookUpTable

"""
Master entry point
"""


def run_irm():
    """
    Starts the intelligent resource management system, which enables autoscaling features
    """
    if Setting.get_autoscaling():    
        IntelligentResourceManager.start_irm(BinPacking.first_fit)
        SysOut.out_string("Autoscaling supervisor started")


def run_rest_service():
    """
    Run rest as in a thread function
    """
    from .rest_service import RESTService
    rest = RESTService()
    rest.run()


def run_msg_service():
    """
    Run msg service to eliminate back pressure
    """
    from .configuration import Setting
    from .server_socket import ThreadedTCPServer, ThreadedTCPRequestHandler
    import threading
    server = ThreadedTCPServer((Setting.get_node_addr(), Setting.get_data_port_start()),
                               ThreadedTCPRequestHandler, bind_and_activate=True)

    # Start a thread with the server -- that thread will then start one
    server_thread = threading.Thread(target=server.serve_forever)

    # Exit the server thread when the main thread terminates
    server_thread.daemon = True

    SysOut.out_string("Enable Messaging System on port: " + str(Setting.get_data_port_start()))

    server_thread.start()

    """ Have to test for graceful termination. """
    # server.shutdown()
    # server.server_close()


if __name__ == '__main__':
    """
    Entry point
    """
    SysOut.out_string("Running Harmonic Master")
    debug = input("Debug mode?  y/n\n")
    if debug == "y":
        LookUpTable.debugging = True

    # Load configuration from file
    from .configuration import Setting
    Setting.read_cfg_from_file()

    # Print instance information
    SysOut.out_string("Node name: " + Setting.get_node_name())
    SysOut.out_string("Node address: " + Setting.get_node_addr())
    SysOut.out_string("Node port: " + str(Setting.get_node_port()))

    # Create thread for handling REST Service
    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor()

    # Run messaging system service
    pool.submit(run_msg_service)

    # Binding commander to the rest service and enable REST service
    pool.submit(run_rest_service)

    # Start the IRM system
    pool.submit(run_irm)
    