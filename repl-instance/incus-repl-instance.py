#!/usr/bin/python3

import subprocess
import logging
import json
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S'
)

class IncusReplicator():
    def __init__(self,**kwargs):
        # Source
        self.source_server  = kwargs['source_server']
        self.repl_prefix    = kwargs['repl_prefix']
        self.target_project = kwargs['target_project']
        # Snapshots
        self.clear_snaps    = kwargs['snap_name_to_clear']
        # Storage
        self.source_pools   = self._get_remote_pools() if kwargs['target_custom_volume_pool'] else False
        self.target_pool    = kwargs['target_custom_volume_pool']
        # Replication
        self.filter         = "user.repl-instance=true"
        self.instances      = self.get_source_instances()
        # Output
        self.verbose        = kwargs['verbose']

    # Instance
    def get_source_instances(self):
        p = subprocess.run(["incus","ls",f"{ self.source_server }:","-cn","-fjson","--all-projects","user.repl-instance=true"], capture_output=True, text=True)
        if not p.stdout.strip():
            raise RuntimeError(f"ERROR: Could not get any instances on { self.source_server }")
        return json.loads(p.stdout)

    def _check_local_repl(self, instance_name):
        p = subprocess.run(["incus","ls","-cn","-fcsv",f"{ self.repl_prefix }--{ instance_name }",f"--all-projects",f"project={ self.target_project }"], capture_output=True, text=True)
        return bool(p.stdout.strip())

    def _init_instance_repl(self, instance_name, instance_type):
        if instance_type == "container":
            logging.warning(f"Container { instance_name } must be stopped before initial replication")
            subprocess.run(["incus","stop",f"{self.source_server}:{instance_name}"], capture_output=True, text=True)

        logging.info(f"Initial replication for { instance_name }")
        p = subprocess.run(["incus","copy",f"{self.source_server}:{instance_name}",f"{ self.repl_prefix}--{instance_name}",f"--target-project={ self.target_project }","--stateless"], capture_output=True, text=True)

        if instance_type == "container":
            logging.info(f"Starting { instance_name } after replication")
            subprocess.run(["incus","start",f"{self.source_server}:{instance_name}"], capture_output=True, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"ERROR[INIT]: {instance_name}: {p.stderr}")

    def _refresh_instance_repl(self, instance_name):
        logging.info(f"Update replication for { instance_name }")
        p = subprocess.run(["incus","copy",f"{self.source_server}:{instance_name}",f"{ self.repl_prefix}--{instance_name}",f"--target-project={ self.target_project }","--refresh","--refresh-exclude-older","-c","boot.autostart=false"], capture_output=True, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"ERROR[REFRESH]: {instance_name}: {p.stderr}")

    def repl_instance(self, instance):
        instance_type = instance['type']
        instance_name = instance['name']

        logging.info(f"Invoke replication for {instance_name }")
        [self._delete_snap(instance_name,s) for s in self._get_snap_by_name(instance_name)] if self.clear_snaps else False
        self._refresh_instance_repl(instance_name) if self._check_local_repl(instance_name) else self._init_instance_repl(instance_name,instance_type)

    # snapshot management
    def _get_snap_by_name(self,instance_name):
        p = subprocess.run(["incus","snapshot","list",f"{self.source_server}:{instance_name}","-cn","-fjson"], capture_output=True, text=True)
        json_data = json.loads(p.stdout.strip())
        return [s['name'] for s in json_data if self.clear_snaps in s['name'] ]

    def _delete_snap(self,instance_name,snap_name):
        logging.info(f"Clear snapshots { snap_name } for { instance_name }")
        p = subprocess.run(["incus","snapshot","delete",f"{self.source_server}:{instance_name}",snap_name], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"ERROR[CLEAR_SNAP]: {instance_name}: {p.stderr}")

    def _check_snap_by_name(self,instance_name):
        snaps = self._get_snap_by_name(instance_name)
        return snaps if snaps else False

    # Storage
    def _get_remote_pools(self):
        p = subprocess.run(["incus","storage","list",f"{self.source_server}:","-cn","-f","csv"], capture_output=True, text=True)
        return p.stdout.splitlines()

    def _get_remote_volumes(self,pool):
        p = subprocess.run(["incus","storage","volume","list",f"{ self.source_server }:{ pool }","-cn","-f","json","type=custom" ], capture_output=True, text=True)
        json_data = json.loads(p.stdout.strip())
        return [v for v in json_data if v.get('config',{}).get("user.repl-volume") == "true"]

    def _check_local_volumes(self, volume_name):
        p = subprocess.run(["incus","storage","volume","list","-cn","-fcsv",self.target_pool,f"{ self.repl_prefix }--{ volume_name }",f"--all-projects"], capture_output=True, text=True)
        return bool(p.stdout.strip())

    def _init_volume_repl(self, source_pool, volume_name):
        logging.info(f"Initial replication for storage volume { source_pool }/custom/{ volume_name }")
        p = subprocess.run(["incus","storage","volume","copy",f"{ self.source_server }:{ source_pool }/{ volume_name }",f"{ self.target_pool}/{ self.repl_prefix }--{volume_name}"], capture_output=True, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"ERROR[INIT]: { source_pool }/{ volume_name }: {p.stderr}")

    def _refresh_volume_repl(self, source_pool, volume_name):
        logging.info(f"Update replication for storage volume { source_pool }/custom/{ volume_name }")
        p = subprocess.run(["incus","storage","volume","copy",f"{ self.source_server }:{ source_pool }/{ volume_name }",f"{ self.target_pool}/{ self.repl_prefix }--{volume_name}","--refresh"], capture_output=True, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"ERROR[INIT]: { source_pool }/{ volume_name }: {p.stderr}")

    def repl_volume(self, source_pool, volume_name):
        self._refresh_volume_repl(source_pool,volume_name) if self._check_local_volumes(volume_name) else self._init_volume_repl(source_pool,volume_name)

    # replication
    def invoke(self):
        if self.verbose:
            logging.info("Debug: Running in Debug mode")
            logging.getLogger().setLevel(logging.DEBUG)

        [self.repl_instance(instance) for instance in self.instances]

        if self.source_pools:
            for pool in self.source_pools:
                volumes = self._get_remote_volumes(pool)
                [self.repl_volume(pool,volume['name']) for volume in volumes]


if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Python script creating incus snapshots")
    _parser.add_argument('--source-server',type=str, required=True,
                help="Remote source server")
    _parser.add_argument('--repl-prefix',type=str, required=True,
                help="Prefix instance name with entered value")
    _parser.add_argument('--target-project',type=str,default='default',
                help="Replicate instances to following project on local incus node")
    _parser.add_argument('--target-custom-volume-pool',type=str,
                help="Replicate custom storage volumes to following storage pool on local incus node")
    _parser.add_argument('--snap-name-to-clear',type=str,default="None",
                help="All snapshots containing this string, will be deleted on source before replication")
    _parser.add_argument('--verbose',action="store_true", help="Verbose output")
    args    =   _parser.parse_args()

    replicator = IncusReplicator(**args.__dict__)
    replicator.invoke()