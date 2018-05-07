
class BinPacking():

    @staticmethod
    def first_fit(input_list, bin_layout):
        """
        perform a first fit bin packing on the input list, using the alredy existing list of available bins if provided
        """
        bins = []
        if bin_layout:
            bins = bin_layout

        # for each item in the list, go through list from left to right and check if it fits in bin and pack it 
        for item in input_list:
            item_packed = False
            for bin_ in bins:
                if bin_.pack(item):
                    item_packed = True
                    item["bin_index"] = bin_.index
                    break
                    
            # otherwise make new bin
            if not item_packed:
                bins.append(Bin(len(bins)))
                if bins[len(bins)-1].pack(item):
                    item_packed = True
                    item["bin_index"] = bin_.index


        return bins


class Bin():
    
    def __init__(self, bin_index):
        self.items = []
        self.free_space = 1.0
        self.index = bin_index
        self.space_margin = 0.05

    def pack(self, item):
        item_size = item['avg_cpu']
        if item_size < self.free_space - self.space_margin:
            self.items.append(item)
            self.free_space -= item_size
            return True
        else:
            return False

    def remove_item_in_bin(self, item):
        if item in self.items:
            try:
                self.items.remove(item)
                return True
            except ValueError:
                print("could not remove item!")
                return False

    def update_items_in_bin(self, identifier, update_data):
        for item in self.items:
            if item[identifier] == update_data[identifier]:
                for field in update_data:
                    item[field] = update_data[field]


    def __str__(self):
        return ("Bin {}: {}. Free space: {}".format(self.index, self.items, self.free_space))

    