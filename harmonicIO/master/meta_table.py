from harmonicIO.general.services import Services, SysOut
from harmonicIO.general.definition import Definition, CTuple


class DataStatStatus(object):
    PENDING = 0
    PROCESSING = 1
    RESTREAM = 2


class LookUpTable(object):

    debugging = False

    class Workers(object):
        __workers = {}
        @staticmethod
        def verbose():
            return LookUpTable.Workers.__workers

        @staticmethod
        def active_workers():
            """
            returns the number of workers currrently labeled with "active" : True
            """
            aw = 0
            for worker in LookUpTable.Workers.__workers:
                if LookUpTable.Workers.__workers[worker]["active"] == True:
                    aw += 1
            return aw

        # CURRENTLY DOING
        # ISSUE: every time worker checks in, add worker is called, need to only add worker if nonexistent
        # otherwise update accordingly
        @staticmethod
        def update_worker(dict_input):
            worker_ip = dict_input[Definition.get_str_node_addr()]
            if not worker_ip in LookUpTable.Workers.__workers:
                dict_input[Definition.get_str_last_update()] = Services.get_current_timestamp()
                LookUpTable.Workers.__workers[worker_ip] = dict_input
                #dict_input["bin_index"] = LookUpTable.Workers.active_workers()
                #dict_input["active"] = True
            else:
                LookUpTable.Workers.__workers[worker_ip][Definition.get_str_last_update()] = Services.get_current_timestamp()
                #LookUpTable.Workers.__workers[worker_ip]["bin_index"] = LookUpTable.Workers.active_workers()


        @staticmethod
        def del_worker(worker_addr):
            """
            removes the entry of worker with provided address
            """
            del LookUpTable.Workers.__workers[worker_addr]
            
        @staticmethod
        def enable_worker():
            """
            for testing purposes, marks an inactive worker as active and updates its index 
            """
            for worker in LookUpTable.Workers.__workers:
                if not LookUpTable.Workers.__workers[worker]["active"]:
                    LookUpTable.Workers.__workers[worker]["active"] = True
                    LookUpTable.Workers.__workers[worker]["bin_index"] = LookUpTable.Workers.active_workers()
                    return True

            # no more workers available
            return False

        @staticmethod
        def disable_worker():
            """
            for testing purposes, marks the highest index worker as inactive 
            """
            index = LookUpTable.Workers.active_workers()
            for worker in LookUpTable.Workers.__workers:
                if LookUpTable.Workers.__workers[worker].get("bin_index") == index-1:
                    LookUpTable.Workers.__workers[worker_addr]["active"] = False
                    del LookUpTable.Workers.__workers[worker_addr]["bin_index"]
                    break

    class Containers(object):
        __containers = {}

        @staticmethod
        def get_container_object(req):
            ret = dict()
            ret[Definition.REST.Batch.get_str_batch_addr()] = req.params[Definition.REST.Batch.get_str_batch_addr()].strip()
            ret[Definition.REST.Batch.get_str_batch_port()] = int(req.params[Definition.REST.Batch.get_str_batch_port()])
            ret[Definition.REST.Batch.get_str_batch_status()] = int(req.params[Definition.REST.Batch.get_str_batch_status()])
            ret[Definition.Container.get_str_con_image_name()] = req.params[Definition.Container.get_str_con_image_name()].strip()
            ret[Definition.Container.Status.get_str_sid()] = req.params[Definition.Container.Status.get_str_sid()]
            
            return ret

        @staticmethod
        def verbose():
            return LookUpTable.Containers.__containers

        @staticmethod
        def update_container(dict_input):

            def cont_in_table(dict_input):
                conts = LookUpTable.Containers.__containers[dict_input[Definition.Container.get_str_con_image_name()]]
                for cont in conts:
                    if dict_input.get(Definition.Container.Status.get_str_sid()) == cont.get(Definition.Container.Status.get_str_sid()):
                        return cont
                return None
            
            if dict_input[Definition.Container.get_str_con_image_name()] not in LookUpTable.Containers.__containers: # no containers for this image exist
                new_cont = [dict_input]
                LookUpTable.Containers.__containers[dict_input[Definition.Container.get_str_con_image_name()]] = new_cont
            else:
                cont = cont_in_table(dict_input)
                if not cont: # this specific container is not already in table
                    LookUpTable.Containers.__containers[dict_input[Definition.Container.get_str_con_image_name()]].append(dict_input)
                else: # container was already in table, update timestamp
                    cont[Definition.get_str_last_update()] = Services.get_current_timestamp()

        @staticmethod
        def get_candidate_container(image_name):
            if image_name not in LookUpTable.Containers.__containers:
                return None

            if len(LookUpTable.Containers.__containers[image_name]) > 0:
                return LookUpTable.Containers.__containers[image_name].pop()

            return None

        @staticmethod
        def del_container(container_name, short_id):
            conts = LookUpTable.Containers.__containers.get(container_name)
            if not conts:
                return False
            else: 
                # conts is list of containers with same c_name
                
                # List filter code based on: https://stackoverflow.com/questions/1235618/python-remove-dictionary-from-list
                # Removes item with specified short_id from list
                conts[:] = [con for con in conts if con.get(Definition.Container.Status.get_str_sid()) != short_id]

                # notify IRM about container removal
                from .resource_manager import IntelligentResourceManager # NOTE: local import required to avoid circular dependencies
                IntelligentResourceManager.remove_container(container_name, short_id)

            return True

    class Tuples(object):
        __tuples = {}

        @staticmethod
        def get_tuple_object(req):
            # parameters
            ret = dict()
            ret[Definition.Container.get_str_data_digest()] = req.params[Definition.Container.get_str_data_digest()].strip()
            ret[Definition.Container.get_str_con_image_name()] = req.params[Definition.Container.get_str_con_image_name()].strip()
            ret[Definition.Container.get_str_container_os()] = req.params[Definition.Container.get_str_container_os()].strip()
            ret[Definition.Container.get_str_data_source()] = req.params[Definition.Container.get_str_data_source()].strip()
            ret[Definition.Container.get_str_container_priority()] = 0
            ret[Definition.REST.get_str_status()] = CTuple.SC
            ret[Definition.get_str_last_update()] = Services.get_current_timestamp()
            return ret

        @staticmethod
        def get_tuple_id(tuple_info):
            return tuple_info[Definition.Container.get_str_data_digest()][0:12] + ":" + str(tuple_info[Definition.get_str_last_update()])

        @staticmethod
        def add_tuple_info(tuple_info):
            LookUpTable.Tuples.__tuples[LookUpTable.Tuples.get_tuple_id(tuple_info)] = tuple_info

        @staticmethod
        def verbose():
            return LookUpTable.Tuples.__tuples

    class Jobs(object):
        __jobs = {}

        # create new job from request dictionary
        @staticmethod
        def new_job(request):
            new_item = {}
            new_id = request.get('job_id')
            if not new_id:
                SysOut.warn_string("Couldn't create job, no ID provided!")
                return False

            if new_id in LookUpTable.Jobs.__jobs:
                SysOut.warn_string("Job already exists in system, can't create!")
                return False

            new_item['job_id'] = new_id
            new_item['job_status'] = request.get('job_status')
            new_item[Definition.Container.get_str_con_image_name()] = request.get(Definition.Container.get_str_con_image_name())
            new_item['user_token'] = request.get(Definition.get_str_token())
            new_item['volatile'] = request.get('volatile')
            LookUpTable.Jobs.__jobs[new_id] = new_item

            return True

        @staticmethod
        def update_job(request):
            job_id = request.get('job_id')
            if not job_id in LookUpTable.Jobs.__jobs:
                SysOut.warn_string("Couldn't update job, no existing job matching ID!")
                return False

            tkn = request.get(Definition.get_str_token())
            if not tkn == LookUpTable.Jobs.__jobs[job_id]['user_token']:
                SysOut.warn_string("Incorrect token, refusing update.")
                return False

            old_job = LookUpTable.Jobs.__jobs[job_id]
            old_job['job_status'] = request.get('job_status')

            return True

        @staticmethod
        def verbose():
            return LookUpTable.Jobs.__jobs

    class ImageMetadata():
        
        __container_data = {}

        @staticmethod
        def push_metadata(container_image_name, data):
            """
            Updates data of specified container with a cumulative moving average, with a history of maximum 10000 previous averages.
            Data is dictionary of fields to update, such as CPU usage
            """
            container_dataset = LookUpTable.ImageMetadata.__container_data
            c_data = container_dataset.get(container_image_name, None)
            if c_data:
                history = c_data.get("update_count", None)
                if not history:
                    c_data["update_count"] = 1
                for field in data:
                    c_data[field] = (history * float(c_data.get(field, 0)) + float(data[field])) / (history + 1)
                if history < 10000:
                    c_data["update_count"] += 1

        
        @staticmethod
        def verbose():
            return LookUpTable.ImageMetadata.__container_data
            

        

    
    @staticmethod
    def update_worker(dict_input):
        LookUpTable.Workers.update_worker(dict_input)

    @staticmethod
    def get_candidate_container(image_name):
        return LookUpTable.Containers.get_candidate_container(image_name)

    @staticmethod
    def new_job(request):
        return LookUpTable.Jobs.new_job(request)

    @staticmethod
    def update_job(request):
        return LookUpTable.Jobs.update_job(request)

    @staticmethod
    def poll_id(id):
        return id in LookUpTable.Jobs.verbose()

    @staticmethod
    def remove_container(c_name, csid):
        return LookUpTable.Containers.del_container(c_name, csid)

    @staticmethod
    def verbose():
        ret = dict()
        ret['WORKERS'] = LookUpTable.Workers.verbose()
        ret['CONTAINERS'] = LookUpTable.Containers.verbose()
        ret['TUPLES'] = LookUpTable.Tuples.verbose()
        ret['JOBS'] = LookUpTable.Jobs.verbose()
        ret['IMAGEDATA'] = LookUpTable.ImageMetadata.verbose()
        if LookUpTable.debugging:
            from .resource_manager import IntelligentResourceManager # again, necessary local import
            debug = {}
            debug["bins"] = IntelligentResourceManager.container_manager.bins
            debug["allocation queue"] = IntelligentResourceManager.container_manager.allocation_q.queue
            debug["container queue"] = IntelligentResourceManager.container_manager.container_q.view_queue()
            debug["load predictor data"] = IntelligentResourceManager.container_manager.load_predictor.image_data
            ret['DEGUBBING_DATA'] = debug

        return ret
