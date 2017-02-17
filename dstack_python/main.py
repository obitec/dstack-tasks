from invoke import Collection, Program, Argument
from . import tasks


class MainProgram(Program):
    def core_args(self):
        core_args = super(MainProgram, self).core_args()
        extra_args = [
            Argument(names=('project', 'n'), help="The project/package name being build"),
        ]
        return core_args + extra_args

program = MainProgram(namespace=Collection.from_module(tasks), version='1.0.5')
