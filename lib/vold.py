import subprocess
import i3ipc
import socket
from singleton import Singleton
from cfg_master import CfgMaster
from threading import Thread, Event


class vol(Singleton, CfgMaster):
    def __init__(self):
        self.i3 = i3ipc.Connection()
        self.mpv_socket = "/tmp/mpv.socket"
        self.inc = 1
        self.mpd_addr = "127.0.0.1"
        self.mpd_port = "6600"
        self.use_mpv09 = True

        self.i3.on("window::focus", self.set_curr_win)
        self.player_event = Event()

        self.mpd_status = "none"
        self.counter = 0

        Thread(
            target=self.update_mpd_status, args=(), daemon=True
        ).start()

        Thread(
            target=self.wait_for_mpd_status_update, args=(), daemon=True
        ).start()

        self.player_event.set()
        self.current_win = self.i3.get_tree().find_focused()

    def set_curr_win(self, i3, event):
        self.current_win = event.container

    def switch(self, args) -> None:
        {
            "u": self.volume_up,
            "d": self.volume_down,
            "reload": self.reload_config,
        }[args[0]](*args[1:])

    def wait_for_mpd_status_update(self):
        while True:
            p = subprocess.Popen(
                ['mpc', 'idleloop', 'player'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            # Read mpc idleloop for player event
            while True:
                output = p.stdout.readline()
                if output == '' and p.poll() is not None:
                    self.player_event.clear()
                    break
                if output:
                    self.mpd_status = "none"
                    self.player_event.set()

    def check_mpd_status(self):
        p = subprocess.Popen(
            ['nc', self.mpd_addr, self.mpd_port],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        p.stdin.write(bytes('status\nclose\n', 'UTF-8'))
        p_com = p.communicate()[0].decode('UTF-8').split('\n')
        p.stdin.close()

        if p_com is not None:
            ret = [t for t in p_com if 'state' in t]
            if ret and ret == ['state: play']:
                self.mpd_status = "play"

        if self.mpd_status != "play":
            self.mpd_status = "none"

    def update_mpd_status(self):
        while True:
            if self.player_event.wait():
                self.check_mpd_status()
                self.player_event.clear()

    def reload_config(self):
        self.__init__()

    def change_volume(self, val):
        val_str = str(val)
        mpv_key = '9'
        mpv_cmd = '--decrease'
        if val > 0:
            val_str = "+" + str(val)
            mpv_key = '0'
            mpv_cmd = '--increase'
        if self.mpd_status == "play":
            self.mpd_socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )
            self.mpd_socket.connect((self.mpd_addr, int(self.mpd_port)))
            self.mpd_socket.send(bytes(f'volume {val_str}\nclose\n', 'UTF-8'))
            self.mpd_socket.recv(1024)
            self.mpd_socket.close()
        elif self.use_mpv09 and self.current_win.window_class == "mpv":
            subprocess.call([
                    'xdotool', 'type', '--clearmodifiers',
                    '--delay', '0', str(mpv_key) * abs(val)
                ])
        elif self.use_mpv09:
            subprocess.call([
                'mpvc', 'set', 'volume', mpv_cmd, str(abs(val))
            ])
        else:
            return

    def volume_up(self, *args):
        count = len(args)
        if count <= 0:
            count = 1
        self.change_volume(count)

    def volume_down(self, *args):
        count = len(args)
        if count <= 0:
            count = 1
        self.change_volume(-count)

