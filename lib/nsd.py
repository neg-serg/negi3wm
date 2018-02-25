import i3ipc
import uuid
import re
import os
import shlex
import subprocess
import geom
import time
from threading import Thread
from modlib import *
from typing import Callable, List

from singleton import *
from cfg_master import *

class ns(CfgMaster, Matcher):
    __metaclass__ = Singleton

    def __init__(self) -> None:
        super().__init__()
        self.winlist=None
        self.fullscreen_list=[]
        self.nsgeom=geom.geom(self.cfg)
        self.marked={l:[] for l in self.cfg}
        self.i3 = i3ipc.Connection()
        self.transients=[]
        self.mark_all_tags(hide=True)
        self.auto_save_geom(False)

        self.i3.on('window::new', self.mark_tag)
        self.i3.on('window::close', self.unmark_tag)

    def make_mark_str(self, tag: str) -> str:
        uuid_str = str(str(uuid.uuid4().fields[-1]))
        return f'mark {tag}-{uuid_str}'

    def focus(self, tag: str, hide=True) -> None:
        if not len(self.transients):
            [
                win.command('move container to workspace current')
                for win in self.marked[tag]
            ]
            if hide:
                self.unfocus_all_but_current(tag)
        else:
            try:
                self.transients[0].command('focus')
                del self.transients[0]
            except:
                self.mark_all_tags(hide=False)

    def unfocus(self, tag: str) -> None:
        if self.geom_auto_save:
            self.geom_save(tag)
        [
            win.command('move scratchpad')
            for win in self.marked[tag]
        ]
        self.restore_fullscreens()

    def unfocus_all_but_current(self, tag: str) -> None:
        focused = self.i3.get_tree().find_focused()
        for win in self.marked[tag]:
            if win.id != focused.id:
                win.command('move scratchpad')
            else:
                win.command('move container to workspace current')

    def find_visible_windows(self):
        visible_windows = []
        wswins=filter(
            lambda win: win.window,
            self.i3.get_tree().find_focused().workspace().descendents()
        )
        for w in wswins:
            xprop = subprocess.check_output(['xprop', '-id', str(w.window)]).decode()
            if '_NET_WM_STATE_HIDDEN' not in xprop:
                visible_windows.append(w)
        return visible_windows

    def check_dialog_win(self, w):
        if w.window_instance == "Places" or w.window_role == "GtkFileChooserDialog":
            return False
        xprop = subprocess.check_output(['xprop', '-id', str(w.window)]).decode()
        return not (
            '_NET_WM_WINDOW_TYPE_DIALOG' in xprop
            or
            '_NET_WM_STATE_MODAL' in xprop
        )

    def dialog_toggle(self):
        wlist = self.i3.get_tree().leaves()
        for win in wlist:
            if not self.check_dialog_win(win):
                win.command('move container to workspace current, show scratchpad')

    def toggle_fs(self, win):
        if win.fullscreen_mode:
            win.command('fullscreen toggle')
            self.fullscreen_list.append(win)

    def toggle(self, tag : str) -> None:
        if not len(self.marked[tag]) and "prog" in self.cfg[tag]:
            try:
                prog_str=re.sub("~", os.path.realpath(os.path.expandvars("$HOME")), self.cfg[tag]["prog"])
                self.i3.command(f'exec {prog_str}')
            except:
                pass

        if self.visible_count(tag) > 0:
            self.unfocus(tag)
            return

        # We need to hide scratchpad it is visible, regardless it focused or not
        focused = self.i3.get_tree().find_focused()

        for w in self.marked[tag]:
            if focused.id == w.id:
                self.unfocus(tag)
                return

        self.toggle_fs(focused)
        self.focus(tag)

    def focus_sub_tag(self, tag: str, subtag_classes_set):
        focused=self.i3.get_tree().find_focused()

        self.toggle_fs(focused)

        if focused.window_class in subtag_classes_set:
            return

        self.focus(tag, hide=True)

        visible_windows = self.find_visible_windows()
        for w in visible_windows:
            for i in self.marked[tag]:
                if w.window_class in subtag_classes_set and w.id == i.id:
                    self.i3.command(f'[con_id={w.id}] focus')

        for _ in self.marked[tag]:
            focused=self.i3.get_tree().find_focused()
            if not focused.window_class in subtag_classes_set:
                self.next_win()

    def run_subtag(self, tag: str, app : str) -> None:
        if app in self.cfg[tag].get("prog_dict",{}):
            class_list=[win.window_class for win in self.marked[tag]]
            subtag_classes_set=set(self.cfg[tag].get("prog_dict",{}).get(app,{}).get("includes",{}))
            subtag_classes_matched=[w for w in class_list if w in subtag_classes_set]
            if not len(subtag_classes_matched):
                try:
                    prog_str=re.sub(
                        "~", os.path.realpath(os.path.expandvars("$HOME")),
                        self.cfg[tag].get("prog_dict",{}).get(app,{}).get("prog",{})
                    )
                    self.i3.command(f'exec {prog_str}')
                except:
                    pass
            else:
                self.focus_sub_tag(tag, subtag_classes_set)
        else:
            self.toggle(tag)

    def restore_fullscreens(self) -> None:
        [win.command('fullscreen toggle') for win in self.fullscreen_list]
        self.fullscreen_list=[]

    def visible_count(self, tag: str):
        visible_windows = self.find_visible_windows()
        vmarked = 0
        for w in visible_windows:
            for i in self.marked[tag]:
                vmarked+=(w.id == i.id)
        return vmarked

    def get_current_tag(self, focused) -> str:
        for tag in self.cfg:
            for i in self.marked[tag]:
                if focused.id == i.id:
                    return tag

    def apply_to_current_tag(self, func : Callable) -> bool:
        curr_tag=self.get_current_tag(self.i3.get_tree().find_focused())
        curr_tag_exits=(curr_tag != None)
        if curr_tag_exits:
            func(curr_tag)
        return curr_tag_exits

    def next_win(self, hide=True) -> None:
        def next_win_(tag: str) -> None:
            self.focus(tag, Hide)
            for idx,win in enumerate(self.marked[tag]):
                if focused_win.id != win.id:
                    self.marked[tag][idx].command('move container to workspace current')
                    self.marked[tag].insert(len(self.marked[tag]), self.marked[tag].pop(idx))
                    win.command('move scratchpad')
            self.focus(tag, Hide)
        Hide=hide
        focused_win=self.i3.get_tree().find_focused()
        self.apply_to_current_tag(next_win_)

    def hide_current(self) -> None:
        if not self.apply_to_current_tag(self.unfocus):
            self.i3.command('[con_id=__focused__] scratchpad show')

    def geom_restore(self, tag: str) -> None:
        for idx,win in enumerate(self.marked[tag]):
            # delete previous mark
            del self.marked[tag][idx]

            # then make a new mark and move scratchpad
            win_cmd=f"{self.make_mark_str(tag)}, move scratchpad, {self.nsgeom.get_geom(tag)}"
            win.command(win_cmd)
            self.marked[tag].append(win)

    def geom_restore_current(self) -> None:
        self.apply_to_current_tag(self.geom_restore)

    def geom_dump(self, tag: str) -> None:
        focused = self.i3.get_tree().find_focused()
        for idx,win in enumerate(self.marked[tag]):
            if win.id == focused.id:
                self.cfg[tag]["geom"]=f"{focused.rect.width}x{focused.rect.height}+{focused.rect.x}+{focused.rect.y}"
                self.dump_config()
                break

    def geom_save(self, tag: str) -> None:
        focused = self.i3.get_tree().find_focused()
        for idx,win in enumerate(self.marked[tag]):
            if win.id == focused.id:
                self.cfg[tag]["geom"]=f"{focused.rect.width}x{focused.rect.height}+{focused.rect.x}+{focused.rect.y}"
                if win.rect.x != focused.rect.x \
                or win.rect.y != focused.rect.y \
                or win.rect.width != focused.rect.width \
                or win.rect.height != focused.rect.height:
                    self.nsgeom=geom.geom(self.cfg)
                    win.rect.x=focused.rect.x
                    win.rect.y=focused.rect.y
                    win.rect.width=focused.rect.width
                    win.rect.height=focused.rect.height
                break

    def auto_update_geom(self):
        def auto_update_geom_payload(sleep=0.5):
            while True:
                self.geom_save_current()
                time.sleep(sleep)
        Thread(target=auto_update_geom_payload, daemon=True).start()

    def auto_save_geom(self, save=True, with_notification=True):
        self.geom_auto_save=save
        if with_notification:
            notify_msg(f"geometry autosave={save}")

    def autosave_toggle(self):
        if self.geom_auto_save:
            self.auto_save_geom(False)
        else:
            self.auto_save_geom(True)

    def geom_dump_current(self):
        self.apply_to_current_tag(self.geom_dump)

    def geom_save_current(self):
        self.apply_to_current_tag(self.geom_save)

    def switch(self, args : List) -> None:
        {
            "show": self.focus,
            "hide": self.unfocus_all_but_current,
            "next": self.next_win,
            "toggle": self.toggle,
            "hide_current": self.hide_current,
            "geom_restore": self.geom_restore_current,
            "geom_dump": self.geom_dump_current,
            "geom_save": self.geom_save_current,
            "geom_autosave_mode": self.autosave_toggle,
            "run": self.run_subtag,
            "reload": self.reload_config,
            "dialog": self.dialog_toggle,
        }[args[0]](*args[1:])

    def mark_tag(self, i3, event) -> None:
        win=event.container
        for tag in self.cfg:
            if self.match(win, tag):
                if self.check_dialog_win(win):
                    # scratch_move
                    win_cmd=f"{self.make_mark_str(tag)}, move scratchpad, {self.nsgeom.get_geom(tag)}"
                    win.command(win_cmd)
                    self.marked[tag].append(win)
                else:
                    self.transients.append(win)
        self.dialog_toggle()
        self.winlist=self.i3.get_tree()

    def unmark_tag(self, i3, event) -> None:
        win_ev=event.container
        for tag in self.cfg:
            for _,win in enumerate(self.marked[tag]):
                if win.id == win_ev.id:
                    del self.marked[tag][_]
                    self.focus(tag)
                    for tr in self.transients:
                        if tr.id == win.id:
                            self.transients.remove(tr)
                    break

    def mark_all_tags(self, hide : bool=True) -> None:
        self.winlist = self.i3.get_tree()
        leaves=self.winlist.leaves()
        for tag in self.cfg:
            for win in leaves:
                if self.match(win, tag):
                    if self.check_dialog_win(win):
                        # scratch move
                        hide_cmd=''
                        if hide:
                            hide_cmd='[con_id=__focused__] scratchpad show'
                        win_cmd=f"{self.make_mark_str(tag)}, move scratchpad, {self.nsgeom.get_geom(tag)}, {hide_cmd}"
                        win.command(win_cmd)
                        self.marked[tag].append(win)
                    else:
                        self.transients.append(win)
        self.winlist = self.i3.get_tree()