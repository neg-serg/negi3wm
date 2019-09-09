import subprocess
from functools import partial
from typing import Callable


class winact():
    def __init__(self, menu):
        self.menu = menu
        self.workspaces = menu.conf("workspaces")

    def win_act_simple(self, cmd: str, prompt: str) -> None:
        """ Run simple and fast selection dialog for window with given action.
            Args:
                cmd (str): action for window to run.
                prompt (str): custom prompt for rofi.
        """
        leaves = self.menu.i3ipc.get_tree().leaves()
        winlist = [win.name for win in leaves]
        winlist_len = len(winlist)
        rofi_params = {
            'cnum': winlist_len,
            'width': int(self.menu.screen_width * 0.75),
            'prompt': f"{prompt} {self.menu.conf('prompt')}"
        }
        if winlist and winlist_len > 1:
            win_name = subprocess.run(
                self.menu.rofi_args(rofi_params),
                stdout=subprocess.PIPE,
                input=bytes('\n'.join(winlist), 'UTF-8')
            ).stdout
        elif winlist_len:
            win_name = winlist[0].encode()

        if win_name is not None and win_name:
            win_name = win_name.decode('UTF-8').strip()
            for win in leaves:
                if win.name == win_name:
                    win.command(cmd)

    def goto_win(self) -> None:
        """ Run rofi goto selection dialog
        """
        self.win_act_simple('focus', self.menu.wrap_str('go'))

    def attach_win(self) -> None:
        """ Attach window to the current workspace.
        """
        self.win_act_simple(
            'move window to workspace current', self.menu.wrap_str('attach')
        )

    def select_ws(self, use_wslist: bool) -> str:
        """ Apply target function to workspace.
        """
        if use_wslist:
            wslist = self.workspaces
        else:
            wslist = [ws.name for ws in self.menu.i3ipc.get_workspaces()] + \
                ["[empty]"]
        rofi_params = {
            'cnum': len(wslist),
            'width': int(self.menu.screen_width * 0.66),
            'prompt': f'{self.menu.wrap_str("ws")} {self.menu.conf("prompt")}',
        }
        workspace_name = subprocess.run(
            self.menu.rofi_args(rofi_params),
            stdout=subprocess.PIPE,
            input=bytes('\n'.join(wslist), 'UTF-8')
        ).stdout

        selected_ws = workspace_name.decode('UTF-8').strip()
        return str(wslist.index(selected_ws) + 1) + ' :: ' + selected_ws

    @staticmethod
    def apply_to_ws(ws_func: Callable) -> None:
        """ Partial apply function to workspace.
        """
        ws_func()

    def goto_ws(self, use_wslist: bool = True) -> None:
        """ Go to workspace menu.
        """
        workspace_name = self.select_ws(use_wslist)
        if workspace_name is not None and workspace_name:
            self.apply_to_ws(
                partial(self.menu.i3ipc.command, f'workspace {workspace_name}')
            )

    def move_to_ws(self, use_wslist: bool = True) -> None:
        """ Move current window to the selected workspace
        """
        workspace_name = self.select_ws(use_wslist)
        if workspace_name is not None and workspace_name:
            self.apply_to_ws(
                partial(self.menu.i3ipc.command,
                        f'[con_id=__focused__] move to workspace {workspace_name}')
            )

