#!/usr/bin/python3

import subprocess
import datetime
import asyncio

class IncusSnapper():
    def __init__(self,instances,snapshot_prefix,expiry):
        self.instances      = instances
        self.expiry         = expiry
        self.snapshot_name  = self.create_snapshot_name(snapshot_prefix)

    def create_snapshot_name(self, snapshot_prefix):
        now = datetime.datetime.now()
        return f"incus-auto-snap-{ snapshot_prefix }-{ now.strftime('%H:%M:%S_%d-%m-%Y') }"

    async def _set_expiry(self, instance):
        proc = await asyncio.create_subprocess_exec("incus","config","set",instance,"snapshots.expiry",self.expiry,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            print(f"*** Fehler bei {instance}: {error}")

    async def _unset_expiry(self, instance):
        proc = await asyncio.create_subprocess_exec("incus","config","unset",instance,"snapshots.expiry",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            print(f"*** Fehler bei {instance}: {error}")

    async def _snap(self, instance):

        proc = await asyncio.create_subprocess_exec("incus","snapshot","create",instance,self.snapshot_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            print(f"{instance}/{self.snapshot_name} expires in {self.expiry}")
        else:
            error = stderr.decode().strip()
            print(f"*** Fehler bei {instance}: {error}")

    async def invoke(self):
        tasks_set = [asyncio.create_task(self._set_expiry(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_set)
        tasks_snap = [asyncio.create_task(self._snap(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_snap)
        tasks_unset = [asyncio.create_task(self._unset_expiry(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_unset)

def list_instances():
    p = subprocess.run(["incus","ls","-cn","-f","csv"], capture_output=True, text=True)
    return p.stdout.splitlines()

if __name__ == "__main__":
    # Script arguments
    import argparse
    _parser = argparse.ArgumentParser(description="Python script creating incus snapshots")
    _parser.add_argument('--prefix',type=str, required=True,
                help="Snapshots will be prefixed with this value (Example: weekly)")
    _parser.add_argument('--expiry',type=str, required=True,
                help="Snapshot lifetime, can be specified in minutes (M), hours (H), days (d), weeks (w), months (m) or years (y).")
    _parser.add_argument('-v','--verbose',action="store_true", help="Verbose output")
    args    =   _parser.parse_args()

    instance_list = list_instances()
    snapper = IncusSnapper(instance_list,args.prefix,args.expiry)
    asyncio.run(snapper.invoke())
