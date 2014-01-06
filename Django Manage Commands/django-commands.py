import sublime
import sublime_plugin
import threading
import subprocess
import os
import glob
import platform
import shlex
from functools import partial

SETTINGS_FILE = 'DjangoCommands.sublime-settings'
PLATFORM = platform.system()

def log(message):
    print(' - Django: {0}'.format(message))


class DjangoCommand(sublime_plugin.WindowCommand):

    def get_manage_py(self):
        for path in sublime.active_window().folders():
            for root, dirs, files in os.walk(path):
                if 'manage.py' in files:
                    return os.path.join(root, 'manage.py')

    def __init__(self, *args, **kwargs):
        self.settings = sublime.load_settings(SETTINGS_FILE)
        sublime_plugin.WindowCommand.__init__(self, *args, **kwargs)


    def choose(self, choices, action):
        on_input = partial(action, choices)
        self.window.show_quick_panel(choices, on_input)

    def go_to_project_home(self):
        if self.manage_py is None:
            return
        base_dir = os.path.abspath(os.path.join(self.manage_py, os.pardir))
        os.chdir(base_dir)

    # def is_enabled(self):
    #     return self.manage_py is not None

    def run_command(self, command):
        bin = self.settings.get('python_bin')
        self.manage_py = self.get_manage_py()
        self.go_to_project_home()

        command = [bin, self.manage_py] + command

        thread = CommandThread(command)
        thread.start()


class CommandThread(threading.Thread):

    def __init__(self, command):
        self.command = command
        threading.Thread.__init__(self)

    def run(self):
        command = ' '.join(self.command)

        if PLATFORM == 'Windows':
            command = [
                'cmd.exe',
                '/k', command
            ]
        if PLATFORM == 'Linux':
            command = [
                'gnome-terminal',
                '-e', 'bash -c \"{0}; read line\"'.format(command)
            ]
        if PLATFORM == 'Darwin':
            command = [
                'osascript',
                '-e', 'tell app "Terminal" to activate',
                '-e', 'tell application "System Events" to tell process "Terminal" to keystroke "t" using command down',
                '-e', 'tell application "Terminal" to do script "{0}" in front window'.format(command)
            ]

        log('Command is : {0}'.format(str(command)))
        subprocess.Popen(command, shell=False)


class DjangoSimpleCommand(DjangoCommand):
    command = ''

    def run(self):
        self.run_command([self.command])


class DjangoAppCommand(DjangoCommand):
    command = ''
    extra_args = []
    app_descriptor = 'models.py'

    def find_apps(self):
        apps = set()
        for project_folder in sublime.active_window().folders():
            dirs = [x[0] for x in os.walk(project_folder)]
            for dir in dirs:
                dir = os.path.expanduser(dir)
                pattern = os.path.join(dir, "*", self.app_descriptor)
                apps.update(list(map(lambda x: x, glob.glob(pattern))))
        return sorted(apps)

    def prettify(self, app_dir, base_dir):
        name = app_dir.replace(base_dir, '')
        name = name.replace(self.app_descriptor, '')
        name = name[1:-1]
        name = name.replace(os.path.sep, '.')
        return name

    def on_choose_app(self, apps, index):
        if index == -1:
            return
        name = apps[index]
        self.run_command([self.command, name] + self.extra_args)

    def run(self):

        self.go_to_project_home()
        choices = self.find_apps()
        base_dir = os.path.dirname(self.manage_py)
        choices = [self.prettify(path, base_dir) for path in choices]
        self.choose(choices, self.on_choose_app)


class DjangoRunCommand(DjangoSimpleCommand):
    command = 'runserver'


class DjangoSyncdbCommand(DjangoSimpleCommand):
    command = 'syncdb'


class DjangoShellCommand(DjangoSimpleCommand):
    command = 'shell'


class DjangoCheckCommand(DjangoSimpleCommand):
    command = 'check'


class DjangoHelpCommand(DjangoSimpleCommand):
    command = 'help'


class DjangoMigrateCommand(DjangoSimpleCommand):
    command = 'migrate'


class DjangoTestAllCommand(DjangoSimpleCommand):
    command = 'test'


class DjangoTestAppCommand(DjangoAppCommand):
    command = 'test'
    app_descriptor = 'tests.py'


class DjangoSchemaMigrationCommand(DjangoAppCommand):
    command = 'schemamigration'
    extra_args = ['--auto']


class DjangoListMigrationsCommand(DjangoSimpleCommand):
    command = 'migrate'
    extra_args = ['--list']


class DjangoCustomCommand(DjangoCommand):

    def run(self):
        caption = "Django manage.py command"
        self.window.show_input_panel(caption, '', self.on_done, None, None)

    def on_done(self, command):
        command = command
        if command.strip() == '':
            return
        command = shlex.split(command)
        self.run_command(command)


class VirtualEnvCommand(DjangoCommand):
    command = ''
    extra_args = []

    def is_enabled(self):
        return self.settings.get('python_bin') is not None

    def run(self):
        self.manage_py = self.get_manage_py()
        self.go_to_project_home()
        bin_dir = os.path.dirname(self.settings.get('python_bin'))
        command = [os.path.join(bin_dir, self.command)] + self.extra_args
        thread = CommandThread(command)
        thread.start()


class TerminalHereCommand(VirtualEnvCommand):
    command = 'activate'


class PipFreezeCommand(VirtualEnvCommand):
    command = 'pip'
    extra_args = ['freeze']


class SetVirtualEnvCommand(VirtualEnvCommand):

    def is_enabled(self):
        return True

    def find_virtualenvs(self, venv_paths):
        bin = "Scripts" if PLATFORM == 'Windows' else "bin"
        venvs = set()
        for path in venv_paths:
            path = os.path.expanduser(path)
            pattern = os.path.join(path, "*", bin, "activate_this.py")
            venvs.update(list(map(os.path.dirname, glob.glob(pattern))))
        return sorted(venvs)

    def set_virtualenv(self, venvs, index):
        if index == -1:
            return
        name, directory = venvs[index]
        log('Virtual environment "{0}" is set'.format(name))
        bin = os.path.join(directory, 'python')
        self.settings.set("python_bin", bin)
        sublime.save_settings(SETTINGS_FILE)

    def run(self):
        venv_paths = self.settings.get("python_virtualenv_paths", [])
        choices = self.find_virtualenvs(venv_paths)
        choices = [[path.split(os.path.sep)[-2], path] for path in choices]
        self.choose(choices, self.set_virtualenv)
