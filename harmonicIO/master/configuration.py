from harmonicIO.general.services import SysOut
import json

class Setting(object):
    __node_name = None
    __node_addr = None
    __node_port = None
    __node_data_port_start = None
    __node_data_port_stop = None
    __std_idle_time = None
    __token = "None"
    __autoscaling = None
    __min_CPU = None


    @staticmethod
    def set_node_addr(addr=None):
        if addr:
            Setting.__node_addr = addr
        else:
            import socket
            from harmonicIO.general.services import Services
            Setting.__node_addr = socket.gethostname()
            SysOut.debug_string(Setting.__node_addr)
            # if addr is valid
            if Services.is_valid_ipv4(Setting.__node_addr) or Services.is_valid_ipv6(Setting.__node_addr):
                return None

            # if addr is not valid
            Setting.__node_addr = Services.get_host_name_i()
            if Services.is_valid_ipv4(Setting.__node_addr) or Services.is_valid_ipv6(Setting.__node_addr):
                return None

            SysOut.terminate_string("Cannot get node ip address!")

    @staticmethod
    def get_node_name():
        return Setting.__node_name

    @staticmethod
    def get_node_addr():
        return Setting.__node_addr

    @staticmethod
    def get_node_port():
        return Setting.__node_port

    @staticmethod
    def get_data_port_start():
        return Setting.__node_data_port_start

    @staticmethod
    def get_data_port_stop():
        return Setting.__node_data_port_stop

    @staticmethod
    def get_std_idle_time():
        return Setting.__std_idle_time

    @staticmethod
    def get_token():
        return Setting.__token

    @staticmethod
    def get_autoscaling():
        return Setting.__autoscaling

    @staticmethod
    def get_min_cpu():
        return Setting.__min_CPU

    @staticmethod
    def get_settings():
        return json.dumps({
            Setting.get_node_name(): {
                "node_addr": Setting.get_node_addr(),
                "node_port": Setting.get_node_port(),
                "node_data_port_range": "{}-{}".format(Setting.get_data_port_start(), Setting.get_data_port_stop()),
                "autoscaling": Setting.get_autoscaling(),
                "minimum CPU": Setting.get_min_cpu()
            }
        })

    @staticmethod
    def read_cfg_from_file():
        from harmonicIO.general.services import Services, SysOut
        if not Services.is_file_exist('harmonicIO/master/configuration.json'):
            SysOut.terminate_string('harmonicIO/master/configuration.json does not exist!')
        else:
            with open('harmonicIO/master/configuration.json', 'rt') as t:
                cfg = json.loads(t.read())

                try:
                    from harmonicIO.general.definition import Definition
                    # Check for the json structure
                    if  Definition.get_str_node_name() in cfg and \
                        Definition.get_str_node_port() in cfg and \
                        Definition.get_str_master_addr() in cfg and \
                        Definition.get_str_data_port_range() in cfg and \
                        Definition.get_str_idle_time() in cfg:
                        # Check port number is int or not
                        if not isinstance(cfg[Definition.get_str_node_port()], int):
                            SysOut.terminate_string("Node port must be integer!")
                        if not isinstance(cfg[Definition.get_str_master_addr()], str):
                            SysOut.terminate_string("Master address must be string!")
                        elif not isinstance(cfg[Definition.get_str_data_port_range()], list):
                            SysOut.terminate_string("Port range must be list!")
                        elif not (isinstance(cfg[Definition.get_str_data_port_range()][0], int) and \
                                  isinstance(cfg[Definition.get_str_data_port_range()][1], int)):
                            SysOut.terminate_string("Port range must be integer!")
                        elif len(cfg[Definition.get_str_data_port_range()]) != 2:
                            SysOut.terminate_string("Port range must compost of two elements: start, stop!")
                        elif not isinstance(cfg[Definition.get_str_idle_time()], int):
                            SysOut.terminate_string("Idle time must be integer!")
                        elif cfg[Definition.get_str_data_port_range()][0] > \
                             cfg[Definition.get_str_data_port_range()][1]:
                            SysOut.terminate_string("Start port range must greater than stop port range!")
                        elif not cfg.get("minimum_CPU_size") or cfg.get("minimum_CPU_size") > 1.0:
                            SysOut.terminate_string("Minimum CPU usage must be above 0.0 and below 1.0")
                        else:
                            Setting.__node_name = cfg[Definition.get_str_node_name()].strip()
                            Setting.__node_port = cfg[Definition.get_str_node_port()]
                            Setting.__node_data_port_start = cfg[Definition.get_str_data_port_range()][0]
                            Setting.__node_data_port_stop = cfg[Definition.get_str_data_port_range()][1]
                            Setting.__std_idle_time = cfg[Definition.get_str_idle_time()]
                            Setting.__autoscaling = cfg.get('auto_scaling_enabled')
                            Setting.__min_CPU = float(cfg.get('minimum_CPU_size'))
                            SysOut.out_string("Load setting successful.")

                        try:
                            if cfg[Definition.get_str_master_addr()].lower() == "auto":
                                Setting.__node_addr = Services.get_host_name_i()
                                SysOut.out_string("Assigning master ip address automatically.")
                            elif Services.is_valid_ipv4(cfg[Definition.get_str_master_addr()]) or \
                                 Services.is_valid_ipv6(cfg[Definition.get_str_master_addr()]):
                                Setting.set_node_addr(cfg[Definition.get_str_master_addr()])
                            else:
                                SysOut.terminate_string("Invalid master IP address format!")

                        except:
                            SysOut.terminate_string("Cannot assign IP address to the master!")

                    else:
                        SysOut.terminate_string("Invalid data in configuration file.")
                except:
                    SysOut.terminate_string("Invalid data in configuration file.")

class IRMSetting():
    def __init__(self):
        try:
            with open('harmonicIO/master/irm_configuration.json', 'r') as cfg_file:
                data = json.loads(cfg_file.read())
        except FileNotFoundError:
            SysOut.err_string("Config file for IRM missing!")
        else:
            try:
                self.packing_interval = int(data["packing_interval"])
                self.default_share = data["default_share"]
                self.profiling_interval = int(data["profiling_interval"])
                self.step_length = int(data["predictor_interval"])
                self.roc_lower = int(data["lower_rate_limit"])
                self.roc_upper = int(data["upper_rate_limit"])
                self.roc_minimum = int(data["slowdown_rate"])
                self.queue_limit = int(data["queue_size_limit"])
                self.waiting_time = int(data["scaleup_waiting_time"])
                self.large_increment = int(data["large_scaleup_amount"])
                self.small_increment = int(data["small_scaleup_amount"])
                self.ttl = int(data["container_request_TTL"])
                self.active_resource_types = [k for k,v in data["resource_types_active"].items() if v == True]


            except KeyError as e:
                raise KeyError("Missing config settings for following option: {}".format(e.args[0]))
            except TypeError as e:
                raise TypeError("Invalid config settings for options")
            finally:
                error = ""
                if self.profiling_interval < 1:
                    error += "profiling interval not above 0\n"
                if self.step_length < 1:
                    error += "step length not above 0\n"
                if self.roc_lower < 1:
                    error += "lower rate limit not above 0\n"
                if self.roc_upper <= self.roc_lower:
                    error += "upper rate limit not above lower rate limit\n"
                if self.roc_minimum > -1:
                    error += "slowdown rate not below 0\n"
                if self.queue_limit < 1:
                    error += "queue limit not above 0\n"
                if self.waiting_time < 1:
                    error += "scaleup waiting time not above 0\n"
                if self.large_increment <= self.small_increment:
                    error += "large increment smaller than small increment\n"
                if self.small_increment < 1:
                    error += "small increment not above 0\n"
                if self.ttl < 1:
                    error += "initial TTL must be above 0\n"
                if not error == "":
                    raise ValueError("Invalid value setting for option: {}".format(error))

    def get_active_resource_type_array(resource_dict):
        return [k for k,v in mydict.items() if v == true]


    def get_config(self):
        return json.dumps({
            "packing_interval" : self.packing_interval,
            "default_share" : self.default_share,
            "profiling_interval" : self.profiling_interval,
            "predictor_interval" : self.step_length,
            "lower_rate_limit" : self.roc_lower,
            "upper_rate_limit" : self.roc_upper,
            "slowdown_rate" : self.roc_minimum,
            "queue_size_limit" : self.queue_limit,
            "scaleup_waiting_time" : self.waiting_time,
            "large_scaleup_amount" : self.large_increment,
            "small_scaleup_amount" : self.small_increment,
            "container_request_TTL" : self.ttl,
            "active_resource_types" : self.active_resource_types
        })