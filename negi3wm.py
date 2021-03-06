#!/usr/bin/python3

""" i3 negi3wm daemon script.

This module loads all negi3wm an start it via main's manager mailoop.
Inotify-based watchers for all negi3wm TOML-based configuration spawned here,
to use it just start it from any place without parameters. Moreover it contains
pid-lock which prevents running several times.

Usage:
    ./negi3wm.py [--debug|--tracemalloc|--start]

Options:
    --debug         disables signal handlers for debug.
    --tracemalloc   calculates and shows memory tracing with help of
                    tracemalloc.
    --start         make actions for the start, not reloading

Created by :: Neg
email :: <serg.zorg@gmail.com>
github :: https://github.com/neg-serg?tab=repositories
year :: 2020

"""

import os
import timeit
import atexit
import sys
import signal
import functools
import importlib
from importlib import util
import tracemalloc
from threading import Thread
from colored import fg

for m in ["inotipy", "i3ipc", "docopt", "pulsectl",
          "qtoml", "Xlib", "yaml", "yamlloader", "ewmh", "colored"]:
    if not util.find_spec(m):
        print(f"Cannot import [{m}], please install")

import asyncio
import inotipy

import i3ipc
from docopt import docopt

from lib.locker import get_lock
from lib.msgbroker import MsgBroker
from lib.misc import Misc
from lib.standalone_cfg import modconfig
from lib.checker import checker


class negi3wm(modconfig):
    def __init__(self, cmd_args):
        """ Init function

            Using of self.intern for better performance, create i3ipc
            connection, connects to the asyncio eventloop.
        """
        loop = asyncio.new_event_loop()
        self.tracemalloc_enabled = False
        if cmd_args["--tracemalloc"]:
            self.tracemalloc_enabled = True

        if self.tracemalloc_enabled:
            tracemalloc.start()

        self.first_run = False
        if cmd_args["--start"]:
            self.first_run = True

        if not (cmd_args['--debug'] or self.tracemalloc_enabled):
            def loop_exit(signame):
                print(f"Got signal {signame}: exit")
                loop.stop()
                os._exit(0)

            for signame in {'SIGINT', 'SIGTERM'}:
                loop.add_signal_handler(
                    getattr(signal, signame),
                    functools.partial(loop_exit, signame))
            loop.set_exception_handler(None)

        super().__init__()

        self.loop = loop
        self.mods = {}
        for mod in self.conf("module_list"):
            self.mods[sys.intern(mod)] = None

        self.prepare_notification_text()
        self.port = int(str(self.conf('port')))

        self.echo = Misc.echo_on
        self.notify = Misc.notify_off

        # main i3ipc connection created here and can be bypassed to the most of
        # modules here.
        self.i3 = i3ipc.Connection()

    def prepare_notification_text(self):
        """ stuff for startup notifications """
        self.notification_text = "Starting negi3wm\n\n"
        notification_color = '#395573'
        prefix = self.conf("prefix")
        self.msg_prefix = f"<span weight='normal' \
            color='{notification_color}'> {prefix} </span>"

    def load_modules(self):
        """ Load modules.

            This function init MsgBroker, use importlib to load all the
            stuff, then add_ipc and update notification with startup
            benchmarks.
        """
        mod_startup_times = []
        main_color, delim_color = fg(249), fg(25)
        delim = f'{delim_color}❯{main_color}'
        for mod in self.mods:
            start_time = timeit.default_timer()
            i3mod = importlib.import_module('lib.' + mod)
            self.mods[mod] = getattr(i3mod, mod)(self.i3)
            try:
                self.mods[mod].asyncio_init(self.loop)
            except Exception:
                pass
            mod_startup_times.append(timeit.default_timer() - start_time)
            time_elapsed = f'{mod_startup_times[-1]:4f}'
            mod_loaded_info = f'{main_color}{mod:<14s}{delim}' \
                f'{time_elapsed:>10s}'
            self.notification_text += self.msg_prefix + mod_loaded_info + '\n'
            self.echo(mod_loaded_info, flush=True)
        total_startup_time = str(round(sum(mod_startup_times), 6))
        loading_time_msg = f'{"total":<14s}{delim}' \
            f'{main_color}{total_startup_time:>11s}{fg(240)}'
        self.notification_text += loading_time_msg
        self.echo(loading_time_msg)

    @staticmethod
    def cfg_mods_watcher():
        """ cfg watcher to update modules config in realtime. """
        watcher = inotipy.Watcher.create()
        watcher.watch(Misc.i3path() + '/cfg/', inotipy.IN.MODIFY)
        return watcher

    def autostart(self):
        """ Autostart auto negi3wm initialization """
        if self.first_run:
            circle = self.mods.get('circle')
            if circle is not None:
                circle.bindings['next']('term')

    async def cfg_mods_worker(self, watcher, reload_one=True):
        """ Reloading configs on change. Reload only appropriate config by
            default.

            Args:
                watcher: watcher for cfg.
        """
        while True:
            event = await watcher.get()
            changed_mod = event.pathname[:-4]
            if changed_mod in self.mods:
                if reload_one:
                    self.mods[changed_mod].bindings['reload']()
                    self.notify(f'[Reloaded {changed_mod}]')
                else:
                    for mod in self.mods:
                        self.mods[mod].bindings['reload']()
                    self.notify(
                        '[Reloaded {' + ','.join(self.mods.keys()) + '}]'
                    )

    def run_config_watchers(self):
        """ Start all watchers here via ensure_future to run it in
            background.
        """
        asyncio.ensure_future(self.cfg_mods_worker(negi3wm.cfg_mods_watcher()))

    def run(self, verbose=False):
        """ Run negi3wm here. """
        def start(func, args=None):
            """ Helper for pretty-printing of loading process.

                Args:
                    func (callable): callable routine to run.
                    name: routine name.
                    args: routine args, optional.
            """
            if args is None:
                func()
            elif args is not None:
                func(*args)

        start(self.load_modules)
        start(self.run_config_watchers)

        # Start modules mainloop.
        mainloop = Thread(
            target=MsgBroker.mainloop,
            args=(self.loop, self.mods, self.port,),
            daemon=True
        )
        start((mainloop).start)

        if verbose:
            self.echo('... everything loaded ...')
            self.notify(self.notification_text)
        try:
            self.autostart()
            self.i3.main()
        except KeyboardInterrupt:
            self.i3.main_quit()


def main():
    """ Run negi3wm from here """
    get_lock(os.path.basename(__file__))

    # We need it because of thread_wait on Ctrl-C.
    atexit.register(lambda: os._exit(0))

    cmd_args = docopt(__doc__, version='0.8')

    negi3wm_instance = negi3wm(cmd_args)
    negi3wm_instance.run()

    if negi3wm_instance.tracemalloc_enabled:
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')

        for stat in top_stats[:10]:
            print(stat)

if __name__ == '__main__':
    checker().check(verbose=False)
    main()
