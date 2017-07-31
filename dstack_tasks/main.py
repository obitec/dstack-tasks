import pkg_resources
from invoke import Argument, Collection, Program

import dstack_tasks


class MainProgram(Program):
    def core_args(self):
        core_args = super(MainProgram, self).core_args()
        extra_args = [
            Argument(names=('project', 'n'), help="The project/package name being build"),
        ]
        return core_args + extra_args


version = pkg_resources.get_distribution("dstack_tasks").version
program = MainProgram(namespace=Collection.from_module(dstack_tasks), version=version)
