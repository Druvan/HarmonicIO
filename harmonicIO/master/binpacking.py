from harmonicIO.general.definition import Definition
from .configuration import IRMSetting

class BinPacking():

    @staticmethod
    def first_fit(input_list, bin_layout,size_descriptors):
        """
        perform a first fit bin packing on the input list, using the alredy existing list of available bins if provided
        """
        
        bins = []
        if bin_layout:
            bins = sorted(bin_layout, key=lambda i: i.index)

        # for each item in the list, go through list from left to right and check if it fits in bin and pack it 
        for item in input_list:
            item_packed = False
            for bin_ in bins:
                if bin_.pack(item):
                    item_packed = True
                    break
                    
            # otherwise make new bin and pack item there
            if not item_packed:
                bins.append(Bin(len(bins),size_descriptors))
                if bins[len(bins)-1].pack(item):
                    item_packed = True
        
        return bins


class Bin():
    
    class ContainerBinStatus():
        PACKED = "packed"
        QUEUED = "queued"
        RUNNING = "running"
        REQUEUED = "requeued"
    
    class Item():
        def __init__(self, data):   
            self.size = data['size_data']
            self.data = data

        def jsonify(self):
            return {"item size" : self.size, "data" : self.data}

        def __str__(self):
            return "Item size: {} data: {}".format(self.size, self.data)

    def __init__(self, bin_index,size_descriptors):
        #if

        self.items = []
        self.free_space = self.get_type_value_dict(size_descriptors,1.0)
        self.space_margin = self.get_type_value_dict(size_descriptors,0.05)
        self.index = bin_index

    def pack(self, item_data):
        item = self.Item(item_data)
        for size_descriptor in self.free_space:
           if item.size[Definition.get_str_avg_()+size_descriptor] < self.free_space[size_descriptor] - self.space_margin[size_descriptor]:
                continue
            else:
                del item  
                return False
        item.data["bin_index"] = self.index
        item.data["bin_status"] = self.ContainerBinStatus.PACKED
        
        for size_descriptor in self.free_space:
            self.free_space[size_descriptor] -= item.size[Definition.get_str_avg_()+size_descriptor]
        self.items.append(item)
        return True

    def remove_item_in_bin(self, identifier, target):
        for i in range(len(self.items)):
            if self.items[i].data[identifier] == target:
                for size_descriptor in self.free_space:
                    self.free_space[size_descriptor] += self.items[i].size[Definition.get_str_avg_()+size_descriptor]
                    if self.free_space[size_descriptor] > 1.0:
                        self.free_space[size_descriptor] = 1.0
                del self.items[i].data["bin_index"]
                del self.items[i].data["bin_status"]
                del self.items[i]
                return True

        return False

    def update_items_in_bin(self, identifier, update_data):
        for item in self.items:
            if item.data[identifier] == update_data[identifier] and not item.data.get("bin_status") == Bin.ContainerBinStatus.RUNNING:
                for size_descriptor in self.free_space:
                    self.free_space[size_descriptor] += item.size[Definition.get_str_avg_()+size_descriptor]
                    item.data['size_data'][Definition.get_str_avg_()+size_descriptor] = update_data['size_data'][Definition.get_str_avg_()+size_descriptor]
                    item.size[Definition.get_str_avg_()+size_descriptor] = item.data['size_data'][Definition.get_str_avg_()+size_descriptor]
                    self.free_space[size_descriptor] -= item.size[Definition.get_str_avg_()+size_descriptor]
                    if self.free_space[size_descriptor] < 0.0:
                        self.free_space[size_descriptor] = 0.0
                    elif self.free_space[size_descriptor] > 1.0:
                        self.free_space[size_descriptor] = 1.0

    def __str__(self):
        bin_items = []
        for item in self.items:
            if isinstance(item, Bin.Item):
                bin_items.append(item.jsonify())
        return ("bin index: {}, space: {}, Items: {}".format(self.index, self.free_space, bin_items))

    def jsonify(self):
        bin_items = []
        for item in self.items:
            if isinstance(item, Bin.Item):
                bin_items.append(item.jsonify())
        return {"bin index" : self.index, "space" : self.free_space, "items" : bin_items}

    def get_type_value_dict(self,types,value):
        ret = {}
        for type_name in types:
            ret[type_name] = value
        
        return ret

