class BatchErrorCode:
    SUCCESS = 0
    CREATE_SOCKET_ERROR = 1
    PROCESSING_ERROR = 2


class CStatus:
    AVAILABLE = 0
    BUSY = 1


class CRole:
    STREAM_CONNECTOR = 0
    MASTER = 1
    WORKER = 2
    MESSAGING_SYSTEM = 4


class CTuple:
    SC = 0
    MS = 1
    WK = 2
    RT = 3


class Definition(object):
    @staticmethod
    def get_str_node_name():
        return "node_name"

    @staticmethod
    def get_str_size_desc():
        return "avg_cpu"

    @staticmethod
    def get_str_node_role():
        return "node_role"

    @staticmethod
    def get_str_node_internal_addr():
        return "node_internal_addr"

    @staticmethod
    def get_str_node_external_addr():
        return "node_external_addr"

    @staticmethod
    def get_str_node_addr():
        return "node_addr"

    @staticmethod
    def get_str_node_port():
        return "node_port"

    @staticmethod
    def get_str_server_addr():
        return "server_addr"

    @staticmethod
    def get_str_server_port():
        return "server_port"

    @staticmethod
    def get_str_master_addr():
        return "master_addr"

    @staticmethod
    def get_str_master_port():
        return "master_port"

    @staticmethod
    def get_str_workers_num():
        return "workers_num"

    @staticmethod
    def get_str_repo_addr():
        return "repo_addr"

    @staticmethod
    def get_str_repo_port():
        return "repo_port"

    @staticmethod
    def get_str_idle_time():
        return "std_idle_time"

    @staticmethod
    def get_str_data_port_range():
        return "node_data_port_range"

    @staticmethod
    def get_str_container_idle_timeout():
        return "container_idle_timeout"

    @staticmethod
    def get_str_token():
        return "token"

    @staticmethod
    def get_str_load1():
        return "load1"

    @staticmethod
    def get_str_load5():
        return "load5"

    @staticmethod
    def get_str_load15():
        return "load15"

    @staticmethod
    def get_str_tuple_id():
        return "t_id"

    @staticmethod
    def get_str_last_update():
        return "last_upd"

    @staticmethod
    def get_cpu_load_command():
        return ['uptime', '|', 'awk', '{ print $8 $9 $10}']

    class Master(object):

        class DataLog(object):
            @staticmethod
            def get_str_data_cmd():
                return "m_cmd"

            @staticmethod
            def get_str_release_data():
                return "release"

        @staticmethod
        def get_str_check_master(addr, port, token):
            return "http://" + addr + ":" + str(port) + "/" + Definition.REST.get_str_status() + "?" + \
                   Definition.REST.get_str_token() + "=" + token

        @staticmethod
        def get_str_push_req(addr, port, token):
            return "http://" + addr + ":" + str(port) + "/" + Definition.REST.get_str_stream_req() + "?" + \
                   Definition.REST.get_str_token() + "=" + token

        @staticmethod
        def get_str_push_req_container_ext(container_name, container_os, priority, source_name, digest):
            return  "&" + Definition.Container.get_str_con_image_name() + "=" + container_name + \
                    "&" + Definition.Container.get_str_container_os() + "=" + container_os + \
                    "&" + Definition.Container.get_str_container_priority() + "=" + str(priority) + \
                    "&" + Definition.Container.get_str_data_source() + "=" + source_name + \
                    "&" + Definition.Container.get_str_data_digest() + "=" + digest

        @staticmethod
        def get_str_end_point(ret, sc=list()):
            response = dict()
            response[Definition.get_str_node_addr()] = ret[Definition.REST.Batch.get_str_batch_addr()]
            response[Definition.get_str_node_port()] = ret[Definition.REST.Batch.get_str_batch_port()]
            response[Definition.get_str_node_role()] = CRole.WORKER
            response[Definition.Master.DataLog.get_str_data_cmd()] = sc
            return str(response)

        @staticmethod
        def get_str_end_point_MS(setting, sc=list()):
            response = dict()
            response[Definition.get_str_node_addr()] = setting.get_node_addr()
            response[Definition.get_str_node_port()] = setting.get_data_port_start()
            response[Definition.get_str_node_role()] = CRole.MESSAGING_SYSTEM
            response[Definition.Master.DataLog.get_str_data_cmd()] = sc
            return str(response)

    class REST(object):
        @staticmethod
        def get_str_status():
            return "status"

        @staticmethod
        def get_str_stream_req():
            return "streamRequest"

        @staticmethod
        def get_str_msg_query():
            return "messagesQuery"

        @staticmethod
        def get_str_cont_mgr():
            return "containerRequest"

        @staticmethod
        def get_str_reg_func():
            return "registeredFunctions"

        @staticmethod
        def get_str_token():
            return "token"

        @staticmethod
        def get_str_docker():
            return "docker"

        @staticmethod
        def get_str_local_imgs():
            return "local_images"

        class Batch(object):
            @staticmethod
            def get_str_batch_addr():
                return "batch_addr"

            @staticmethod
            def get_str_batch_port():
                return "batch_port"

            @staticmethod
            def get_str_batch_status():
                return "batch_status"

    class MessagesQueue(object):

        @staticmethod
        def get_str_command():
            return "command"

        @staticmethod
        def get_str_queue_length():
            return "queueLength"

        @staticmethod
        def get_str_current_id():
            return "current_id"

    class ChannelStatus(object):
        @staticmethod
        def get_str_pe_status():
            return "pe_status"

    class Container(object):
        @staticmethod
        def get_str_con_image_name():
            return "c_name"

        @staticmethod
        def get_str_container_os():
            return "c_os"

        @staticmethod
        def get_str_container_priority():
            return "priority"

        @staticmethod
        def get_str_data_source():
            return "source"

        @staticmethod
        def get_str_data_digest():
            return "digest"

        @staticmethod
        def get_str_cpu_share():
            return "cpu_share"

        class Status(object):

            @staticmethod
            def get_str_sid():
                return "short_id"

            @staticmethod
            def get_str_image():
                return "image"

            @staticmethod
            def get_str_status():
                return "status"

    class Docker(object):

        @staticmethod
        def get_str_command():
            return "command"

        @staticmethod
        def get_str_create():
            return "create"

        @staticmethod
        def get_str_remove():
            return "remove"

        @staticmethod
        def get_str_list():
            return "list"

        @staticmethod
        def get_str_status():
            return "status"

        @staticmethod
        def get_str_query():
            return "query"

        @staticmethod
        def get_str_finished():
            return "finished"

        class HDE(object):

            @staticmethod
            def get_str_node_name():
                return "HDE_NODE_NAME"

            @staticmethod
            def get_str_node_addr():
                return "HDE_NODE_ADDR"

            @staticmethod
            def get_str_node_rest_port():
                return "HDE_NODE_REST_PORT"

            @staticmethod
            def get_str_node_data_port():
                return "HDE_NODE_DATA_PORT"

            @staticmethod
            def get_str_node_forward_port():
                return "HDE_NODE_PORT"

            @staticmethod
            def get_str_master_addr():
                return "HDE_MASTER_ADDR"

            @staticmethod
            def get_str_master_port():
                return "HDE_MASTER_PORT"

            @staticmethod
            def get_str_std_idle_time():
                return "HDE_STD_IDLE_TIME"

            @staticmethod
            def get_str_token():
                return "HDE_TOKEN"

            @staticmethod
            def get_str_idle_timeout():
                return "HDE_IDLE_TIMEOUT"
