import subprocess


class DeferredProcess:
    def __init__(self):
        self.command = None
        self.process = None

    def set_command(self, cmd):
        self.command = cmd

    def execute(self):
        if not self.command:
            raise ValueError("Command not set!")
        self.process = subprocess.Popen(self.command, shell=True)

    def is_running(self):
        if self.process:
            return self.process.poll() == None
        else:
            return None

    def wait(self):
        if self.process:
            self.process.wait()
