import os
import sys
import toml
import traceback


class CfgMaster(object):
    def __init__(self):
        self.mod = self.__class__.__name__
        self.load_config()

    def reload_config(self):
        prev_conf = self.cfg
        try:
            self.load_config()
            self.__init__()
            print(f"[{self.mod}] config reloaded")
        except:
            print(f"[{self.mod}] config reload failed")
            traceback.print_exc(file=sys.stdout)
            self.cfg = prev_conf
            self.__init__()

    def dict_converse(self):
        for i in self.cfg:
            for j in self.cfg[i]:
                if j in {"class", "class_r", "instance"}:
                    self.cfg[i][j] = set(self.cfg[i][sys.intern(j)])
                if j == "prog_dict":
                    for k in self.cfg[i][j]:
                        for kk in self.cfg[i][j][k]:
                            if kk == "includes":
                                self.cfg[i][j][k][kk] = \
                                    set(self.cfg[i][j][k][sys.intern(kk)])

    def dict_deconverse(self):
        for i in self.cfg:
            for j in self.cfg[i]:
                if j in {"class", "class_r", "instance"}:
                    self.cfg[i][j] = list(self.cfg[i][j])
                if j == "prog_dict":
                    for k in self.cfg[i][j]:
                        for kk in self.cfg[i][j][k]:
                            if kk == "includes":
                                self.cfg[i][j][k][kk] = \
                                    list(self.cfg[i][j][k][kk])

    def load_config(self):
        user_name = os.environ.get("USER", "neg")
        xdg_config_path = os.environ.get("XDG_CONFIG_HOME", "/home/" +
                                         user_name + "/.config/")
        self.i3_path = xdg_config_path+"/i3/"
        with open(self.i3_path + "/cfg/" + self.mod + ".cfg", "r") as fp:
            self.cfg = toml.load(fp)
        self.dict_converse()

    def dump_config(self):
        user_name = os.environ.get("USER", "neg")
        xdg_config_path = os.environ.get("XDG_CONFIG_HOME", "/home/" +
                                         user_name + "/.config/")
        self.i3_path = xdg_config_path+"/i3/"
        with open(self.i3_path + "/cfg/" + self.mod + ".cfg", "r+") as fp:
            self.dict_deconverse()
            toml.dump(self.cfg, fp)
            self.cfg = toml.load(fp)
        self.dict_converse()

    def add_props(self, tag, prop_str):
        attr_dict = {}
        possible_props = ['class', 'instance', 'window_role', 'title']
        cfg_props = [ 'class', 'instance', 'role' ]
        conv_props = {
            'class': cfg_props[0],
            'instance': cfg_props[1],
            'window_role': cfg_props[2],
        }
        prop_str = prop_str[1:-1]
        for t in prop_str.split('@'):
            if len(t):
                toks = t.split('=')
                attr = toks[0]
                value = toks[1]
                if value[0] == value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                if attr in possible_props:
                    attr_dict[conv_props.get(attr, {})] = value
        for t in self.cfg[tag]:
            if t in cfg_props:
                if attr_dict[t] not in self.cfg[tag][t]:
                    self.cfg[tag][t].add(attr_dict[t])

