""" Advanced alt-tab module.

This module allows you to focus previous window a-la "alt-tab" not by workspace
but by window itself. To achieve that I am using self.focus_history to store
information about previous windows. We need this because previously selected
window may be closed, and then you cannot focus it.
"""

from typing import Iterator
from itertools import cycle
from cfg import cfg
from negewmh import NegEWMH
from extension import extension

class remember_focused(extension, cfg):
    """ Advanced alt-tab class. """
    def __init__(self, i3ipc) -> None:
        """ Init function
            i3ipc: i3ipc connection """
        cfg.__init__(self, i3ipc) # Initialize cfg.
        self.i3ipc = i3ipc # i3ipc connection, bypassed by negi3wm runner
        # previous / current window list
        self.focus_history = [] # depth of history list
        self.max_remember_focused = 4 # workspaces with auto alt-tab when close
        self.autoback = self.conf('autoback')
        self.bindings = {
            "switch": self.alt_tab,
            "reload": self.reload_config,
            "focus_next": self.focus_next,
            "focus_prev": self.focus_prev,
            "focus_next_visible": self.focus_next_visible,
            "focus_prev_visible": self.focus_prev_visible,
        }
        self.i3ipc.on('window::focus', self.on_window_focus)
        self.i3ipc.on('window::close', self.goto_nonempty_ws_on_close)

    def reload_config(self) -> None:
        """ Reloads config. Dummy. """
        self.__init__(self.i3ipc)

    def alt_tab(self) -> None:
        """ Focus previous window. """
        wids = set(w.id for w in self.i3ipc.get_tree().leaves())
        for wid in self.focus_history[1:]:
            if wid not in wids:
                self.focus_history.remove(wid)
            else:
                self.i3ipc.command(f'[con_id={wid}] focus')
                return

    def on_window_focus(self, _, event) -> None:
        """ Store information about current / previous windows.
            i3: i3ipc connection.
            event: i3ipc event. We can extract window from it using
            event.container. """
        wid = event.container.id
        if wid in self.focus_history:
            self.focus_history.remove(wid)
        self.focus_history.insert(0, wid)
        if len(self.focus_history) > self.max_remember_focused:
            del self.focus_history[self.max_remember_focused:]

    def get_windows_on_ws(self) -> Iterator:
        """ Return iterator for windows on the current workspace. """
        return filter(
            lambda x: x.window,
            self.i3ipc.get_tree().find_focused().workspace().leaves()
        )

    def goto_visible(self, reversed_order=False):
        """ Focus next visible window.
            reversed_order(bool) : [optional] predicate to change order. """
        wins = NegEWMH.find_visible_windows(self.get_windows_on_ws())
        self.goto_win(wins, reversed_order)

    def goto_win(self, wins, reversed_order=False):
        """ Goto target window """
        if reversed_order:
            cycle_windows = cycle(reversed(wins))
        else:
            cycle_windows = cycle(wins)
        for window in cycle_windows:
            if window.focused:
                focus_to = next(cycle_windows)
                self.i3ipc.command('[id="%d"] focus' % focus_to.window)
                break

    def goto_any(self, reversed_order: bool = False) -> None:
        """ Focus any next window.
            reversed_order(bool) : [optional] predicate to change order. """
        wins = self.i3ipc.get_tree().leaves()
        self.goto_win(wins, reversed_order)

    def focus_next(self) -> None:
        """ Focus any next window """
        self.goto_any(reversed_order=False)

    def focus_prev(self) -> None:
        """ Focus any previous window """
        self.goto_any(reversed_order=True)

    def focus_next_visible(self) -> None:
        """ Focus next visible window """
        self.goto_visible(reversed_order=False)

    def focus_prev_visible(self) -> None:
        """ Focus previous visible window """
        self.goto_visible(reversed_order=True)

    def goto_nonempty_ws_on_close(self, i3ipc, _) -> None:
        """ Go back for temporary tags like pictures or media. This function
        make auto alt-tab for workspaces which should by temporary. This is
        good if you do not want to see empty workspace after switching to the
        media content workspace.

        i3ipc: i3ipc connection.
        event: i3ipc event. We can extract window from it using
        event.container. """
        workspace = i3ipc.get_tree().find_focused().workspace()
        focused_ws_name = workspace.name
        if not workspace.leaves():
            for ws_substr in self.autoback:
                if focused_ws_name.endswith(ws_substr):
                    self.alt_tab()
                    return
