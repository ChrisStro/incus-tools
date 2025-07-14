#!/usr/bin/python3

import subprocess
import logging
import datetime
import asyncio
import argparse
import json
import sys

class IncusSnapper():
    def __init__(self,**kwargs):
        # Instances
        self.filter         = "user.auto-snapshot=true"
        self.instances      = self.get_local_instances()
        # Storage
        self.pools          = self.get_local_pools()
        self.snap_volumes        = True if kwargs['include_volumes'] == True else False
        # Snapshot
        self.expiry         = kwargs['expiry']
        self.snapshot_name  = self.create_snapshot_name(kwargs['prefix'])
        # Args
        self.list_only      = kwargs['list_enabled']
        self.verbose        = kwargs['verbose']

    def create_snapshot_name(self, prefix):
        now = datetime.datetime.now()
        return f"incus-auto-snap-{ prefix }-{ now.strftime('%H:%M:%S_%d-%m-%Y') }"

    # Instance
    def get_local_instances(self):
        p = subprocess.run(["incus","list","-cn","-f","csv",self.filter ], capture_output=True, text=True)
        return p.stdout.splitlines()

    def _print_enabled_instances(self):
        p = subprocess.run(["incus","list",self.filter ], capture_output=True, text=True)
        print(p.stdout)

    async def _snap_instance(self, instance):

        proc = await asyncio.create_subprocess_exec("incus","snapshot","create",instance,self.snapshot_name,"--expiry",self.expiry,
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

    def _get_custom_volumes(self,pool):
        p = subprocess.run(["incus","storage","volume","list",pool,"-cn","-f","json","type=custom" ], capture_output=True, text=True)
        json_data = json.loads(p.stdout.strip())
        volumes = self._get_volume_filtered(json_data)
        return volumes

    def _get_volume_filtered(self,volume_data):
        # snap enabled
        volume_filtered = [v for v in volume_data if v.get('config',{}).get("user.auto-snapshot") == "true"]
        # exclude snapshots
        volumes_no_snaps = [v for v in volume_filtered if "/" not in v['name']]

        volumes_dict = []
        for volume in volumes_no_snaps:
            name                = volume.get('name')
            project             = volume.get('project')
            content_type        = volume.get('content_type')

            volume_snap_count   = self._get_source_volume_snap_count(volume_filtered,volume)
            volumes_dict.append(dict(name=name,project=project,content_type=content_type,snaps=volume_snap_count))
        return volumes_dict

    def _get_source_volume_snap_count(self,volume_data,volume):
        volume_name = volume.get('name')
        volume_snaps = [v for v in volume_data if f"{ volume_name }/" in v['name']]
        return len(volume_snaps)

    def _print_volumes_pretty(self,pool,volumes):
        table_data =  [["Pool", "Project", "Name", "Content-Type", "Snapshots"]]
        table_data += [[pool, volume['project'], volume['name'], volume['content_type'], volume['snaps']] for volume in volumes]
        col_widths = [max(len(str(row[i])) for row in table_data) for i in range(len(table_data[0]))]
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(table_data[0], col_widths)) + " |")
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        for data in table_data[1:]:
            print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(data, col_widths)) + " |")
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")

    async def _snap_volume(self, pool, volume_name):
        proc = await asyncio.create_subprocess_exec("incus","storage","volume","snapshot","create",pool,f"custom/{volume_name}", self.snapshot_name,"--expiry",self.expiry,
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
        if self.verbose:
            logging.info("Debug: Running in Debug mode")
            logging.getLogger().setLevel(logging.DEBUG)

        # Only show snapshot enabled resources
        if self.list_only:
            if self.instances:
                self._print_enabled_instances()
            for pool in self.pools:
                volumes = self._get_custom_volumes(pool)
                if volumes:
                    self._print_volumes_pretty(pool,volumes)
            sys.exit(0)

        # instance
        tasks_instance_snap = [asyncio.create_task(self._snap_instance(instance)) for instance in self.instances]
        await asyncio.gather(*tasks_instance_snap)

        # storage
        if self.snap_volumes:
            for pool in self.pools:
                volumes = self._get_custom_volumes(pool)
                tasks_storage_snap = [asyncio.create_task(self._snap_volume(pool,volume['name'])) for volume in volumes]
                await asyncio.gather(*tasks_storage_snap)

if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Python script creating incus snapshots")
    _parser.add_argument('--prefix',type=str, required=False,
                help="Snapshots will be prefixed with this value (Example: weekly)")
    _parser.add_argument('--expiry',type=str, required=False,
                help="Snapshot lifetime, can be specified in minutes (M), hours (H), days (d), weeks (w), months (m) or years (y).")
    _parser.add_argument('--include-volumes',action="store_true", help="Also snapshot volumes configured with user.auto-snapshot=true property")
    _parser.add_argument('--list-enabled',action="store_true", help="List auto-snapshot enabled resources and exit")
    _parser.add_argument('--verbose',action="store_true", help="Verbose output")
    args    =   _parser.parse_args()


    if (not args.list_enabled) and (not args.prefix and args.expiry):
        _parser.error("Wrong input, use incus-auto-snapshot --help")

    snapper = IncusSnapper(**args.__dict__)
    asyncio.run(snapper.invoke())
