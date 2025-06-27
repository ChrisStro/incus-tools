#!/usr/bin/python3

import subprocess
import datetime
import asyncio
import argparse
import json

# def get_local_instances():
#     p = subprocess.run(["incus","list","-cn","-f","csv","user.auto-snapshot=true"], capture_output=True, text=True)
#     return p.stdout.splitlines()

class IncusSnapper():
    def __init__(self,**kwargs):
        # Instances
        self.filter         = "user.auto-snapshot=true"
        self.instances      = self.get_local_instances()
        # Storage
        self.pools          = self.get_local_pools() if kwargs['include_volumes'] == True else False
        # Snapshot
        self.expiry         = kwargs['expiry']
        self.snapshot_name  = self.create_snapshot_name(kwargs['prefix'])
        # Output
        self.verbose        = kwargs['verbose']

    def create_snapshot_name(self, prefix):
        now = datetime.datetime.now()
        return f"incus-auto-snap-{ prefix }-{ now.strftime('%H:%M:%S_%d-%m-%Y') }"

    # Instance
    def get_local_instances(self):
        p = subprocess.run(["incus","list","-cn","-f","csv",self.filter ], capture_output=True, text=True)
        return p.stdout.splitlines()

    async def _set_instance_expiry(self, instance):
        proc = await asyncio.create_subprocess_exec("incus","config","set",instance,"snapshots.expiry",self.expiry,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            raise RuntimeError(f"ERROR: bei {instance}: {error}")

    async def _unset_instance_expiry(self, instance):
        proc = await asyncio.create_subprocess_exec("incus","config","unset",instance,"snapshots.expiry",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            raise RuntimeError(f"ERROR: bei {instance}: {error}")

    async def _snap_instance(self, instance):

        proc = await asyncio.create_subprocess_exec("incus","snapshot","create",instance,self.snapshot_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            print(f"{instance}/{self.snapshot_name} expires in {self.expiry}")
        else:
            error = stderr.decode().strip()
            raise RuntimeError(f"ERROR: {instance}: {error}")

    # Storage
    def get_local_pools(self):
        p = subprocess.run(["incus","storage","list","-cn","-f","csv"], capture_output=True, text=True)
        return p.stdout.splitlines()

    def get_custom_volumes(self,pool):
        p = subprocess.run(["incus","storage","volume","list",pool,"-cn","-f","json","type=custom" ], capture_output=True, text=True)
        json_data = json.loads(p.stdout.strip())
        return [v for v in json_data if v.get('config',{}).get("user.auto-snapshot") == "true"]

    async def _set_volume_expiry(self, pool, volume_name):
        proc = await asyncio.create_subprocess_exec("incus","storage","volume","set",pool,f"custom/{volume_name}","snapshots.expiry",self.expiry,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            raise RuntimeError(f"ERROR: bei {pool}/{volume_name}: {error}")

    async def _unset_volume_expiry(self, pool, volume_name):
        proc = await asyncio.create_subprocess_exec("incus","storage","volume","unset",pool,f"custom/{volume_name}","snapshots.expiry",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            error = stderr.decode().strip()
            raise RuntimeError(f"ERROR: bei {pool}/{volume_name}: {error}")

    async def _snap_volume(self, pool, volume_name):
        proc = await asyncio.create_subprocess_exec("incus","storage","volume","snapshot","create",pool,f"custom/{volume_name}", self.snapshot_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            print(f"{pool}/{volume_name}/{self.snapshot_name} expires in {self.expiry}")
        else:
            error = stderr.decode().strip()
            raise RuntimeError(f"ERROR: {pool}/{volume_name}: {error}")

    async def invoke(self):
        # instance
        tasks_instance_set = [asyncio.create_task(self._set_instance_expiry(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_instance_set)
        tasks_instance_snap = [asyncio.create_task(self._snap_instance(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_instance_snap)
        tasks_instance_unset = [asyncio.create_task(self._unset_instance_expiry(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_instance_unset)

        # storage
        if self.pools:
            for pool in self.pools:
                volumes = self.get_custom_volumes(pool)
                tasks_storage_set = [asyncio.create_task(self._set_volume_expiry(pool,volume['name'])) for volume in volumes]
                await asyncio.gather(*tasks_storage_set)
                tasks_storage_snap = [asyncio.create_task(self._snap_volume(pool,volume['name'])) for volume in volumes]
                await asyncio.gather(*tasks_storage_snap)
                tasks_storage_unset = [asyncio.create_task(self._unset_volume_expiry(pool,volume['name'])) for volume in volumes]
                await asyncio.gather(*tasks_storage_unset)

if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Python script creating incus snapshots")
    _parser.add_argument('--prefix',type=str, required=True,
                help="Snapshots will be prefixed with this value (Example: weekly)")
    _parser.add_argument('--expiry',type=str, required=True,
                help="Snapshot lifetime, can be specified in minutes (M), hours (H), days (d), weeks (w), months (m) or years (y).")
    _parser.add_argument('--include-volumes',action="store_true", help="Verbose output")
    _parser.add_argument('--verbose',action="store_true", help="Verbose output")
    args    =   _parser.parse_args()

    snapper = IncusSnapper(**args.__dict__)
    asyncio.run(snapper.invoke())
