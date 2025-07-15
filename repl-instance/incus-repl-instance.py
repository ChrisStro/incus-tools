#!/usr/bin/python3

import subprocess
import logging
import json
import argparse
import sys

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
        self.source_pools   = self._get_source_pools()
        self.target_pool    = kwargs['target_custom_volume_pool']
        # Replication
        self.filter         = "user.repl-instance=true"
        self.instances      = self.get_source_instances()
        # Clones
        self.keep           = kwargs['keep']
        self.keep_count     = kwargs['keep_count']
        # Args
        self.list_only      = kwargs['list_sources']
        self.verbose        = kwargs['verbose']

    # Instance
    def get_source_instances(self):
        logging.debug(f"Get list of all instances from { self.source_server }")
        p = subprocess.run(["incus","ls",f"{ self.source_server }:","-fjson","--all-projects","user.repl-instance=true"], capture_output=True, text=True)
        if not p.stdout.strip():
            raise RuntimeError(f"ERROR: Could not get any instances on { self.source_server }")
        return json.loads(p.stdout)

    def _print_source_instances(self):
        table_data =  [["Project", "Name", "Type", "Snapshots"]]
        table_data += [[instance['project'], instance['name'], instance['type'], len(instance['snapshots'] or [])] for instance in self.instances]
        col_widths = [max(len(str(row[i])) for row in table_data) for i in range(len(table_data[0]))]
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(table_data[0], col_widths)) + " |")
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        for data in table_data[1:]:
            print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(data, col_widths)) + " |")
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")

    def _check_local_repl(self, instance_name):
        logging.debug(f"Check if replicated instance already present")
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

    # Clones
    def _get_clone_instance_snap(self,instance_name):
        p = subprocess.run(["incus","snapshot","list",f"{ self.repl_prefix }--{ instance_name }","--project",self.target_project,"-cn","-fjson"], capture_output=True, text=True)
        try:
            json_data = json.loads(p.stdout.strip())
            all_snaps = [s['name'] for s in json_data if self.keep in s['name'] ]
            return all_snaps, all_snaps[-1] # return all and last
        except:
            logging.debug(f"No snapshots available for { instance_name }")
            return 0,0

    def _clone_instance_snap(self,instance_name,snap_name):
        clone_name=f"clone-{ self.repl_prefix }--{ instance_name }-{ snap_name }".replace(":","-").replace("_","-")
        try:
            p = subprocess.run(["incus","ls",clone_name,"-fcsv","--all-projects"], capture_output=True, text=True)
            if not p.stdout:
                logging.debug(f"Create { clone_name } from { snap_name }")
                p = subprocess.run(["incus","copy",f"{ self.repl_prefix }--{ instance_name }/{ snap_name }",clone_name,"--project",self.target_project,"--target-project",self.target_project],check=True, capture_output=True, text=True)
                if p.returncode != 0:
                    raise RuntimeError(f"CLONE[SNAP]: {p.stderr}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Could not clone snap, { e }, details: { e.stderr }")
        except Exception as e:
            logging.error(f"Could not clone snap, { e }")

    def _get_clone_instances(self,instance_name):
        p = subprocess.run(["incus","list","-cn","-fjson","--all-projects"], capture_output=True, text=True)
        try:
            json_data = json.loads(p.stdout.strip())
            all_clones = [s for s in json_data if f"clone-" in s['name'] ]
            instance_clones = [c['name'] for c in all_clones if f"{ self.repl_prefix }--{ instance_name }" in c['name'] ]
            return instance_clones
        except:
            logging.info(f"No clones available for { instance_name }")
            return 0

    def _purge_instance_clones(self,instance_names: list[str]):
        try:
            for instance in instance_names:
                logging.debug(f"Cleanup old clone: { instance }")
                subprocess.run(["incus","delete",instance,"--project",self.target_project,"--force"],check=True, capture_output=True, text=True)
        except:
            logging.error(f"Error on pruning { instance }")

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
    def _get_source_pools(self):
        p = subprocess.run(["incus","storage","list",f"{self.source_server}:","-cn","-f","csv"], capture_output=True, text=True)
        return p.stdout.splitlines()

    def _get_source_volumes(self,pool):
        p = subprocess.run(["incus","storage","volume","list",f"{ self.source_server }:{ pool }","-cn","-f","json","type=custom" ], capture_output=True, text=True)
        json_data = json.loads(p.stdout.strip())
        volume_rep_enabled = self._get_source_volume_filtered(json_data)
        volumes_no_snaps = [v for v in volume_rep_enabled if "/" not in v['name']]

        volumes_dict = []
        for volume in volumes_no_snaps:
            name                = volume.get('name')
            project             = volume.get('project')
            content_type        = volume.get('content_type')

            volume_snap_count   = self._get_source_volume_snap_count(volume_rep_enabled,volume)
            volumes_dict.append(dict(name=name,project=project,content_type=content_type,snaps=volume_snap_count))
        return volumes_dict

    def _get_source_volume_filtered(self,volume_data):
        volume_filtered = [v for v in volume_data if v.get('config',{}).get("user.repl-volume") == "true"]
        return volume_filtered

    def _get_source_volume_snap_count(self,volume_data,volume):
        volume_name = volume.get('name')
        volume_snaps = [v for v in volume_data if f"{ volume_name }/" in v['name']]
        return len(volume_snaps)

    def _print_source_volumes_pretty(self,pool,volumes):
        table_data =  [["Pool", "Project", "Name", "Content-Type", "Snapshots"]]
        table_data += [[pool, volume['project'], volume['name'], volume['content_type'], volume['snaps']] for volume in volumes]
        col_widths = [max(len(str(row[i])) for row in table_data) for i in range(len(table_data[0]))]
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(table_data[0], col_widths)) + " |")
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")
        for data in table_data[1:]:
            print("| " + " | ".join(str(cell).ljust(w) for cell, w in zip(data, col_widths)) + " |")
        print("+" + "+".join("-" * (w + 2) for w in col_widths) + "+")

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
            logging.getLogger().setLevel(logging.DEBUG)
            logging.debug("Debug: Running in Debug mode")

        if self.list_only: # handle list
            if self.instances:
                self._print_source_instances()
            for pool in self.source_pools:
                volumes = self._get_source_volumes(pool)
                if volumes:
                    self._print_source_volumes_pretty(pool,volumes)
            sys.exit(0)

        for instance in self.instances:
            self.repl_instance(instance) # handle replication
            if self.keep: # handle clones
                logging.info(f"Create clone for { instance['name'] }")
                all_snaps,last_snap_name = self._get_clone_instance_snap(instance['name'])
                if last_snap_name:
                    self._clone_instance_snap(instance['name'],last_snap_name)
                all_clones = self._get_clone_instances(instance['name'])
                if len(all_clones) > self.keep_count:
                    logging.info(f"Cleanup clones for { instance['name'] }")
                    clones_to_delete = all_clones[:-self.keep_count]
                    self._purge_instance_clones(clones_to_delete)

        if self.source_pools: # handle storage
            for pool in self.source_pools:
                volumes = self._get_source_volumes(pool)
                [self.repl_volume(pool,volume['name']) for volume in volumes]

if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Python script for automate replications")
    # list group
    _parser.add_argument('--source-server', type=str, required=True,
                help="Remote source server")
    _parser.add_argument('--repl-prefix', type=str, required=False,
                help="Prefix instance name with entered value")
    _parser.add_argument('--target-project', type=str, default='default',
                help="Replicate instances to following project on local incus node")
    _parser.add_argument('--target-custom-volume-pool', type=str,
                help="Replicate custom storage volumes to following storage pool on local incus node")
    _parser.add_argument('--snap-name-to-clear', type=str, default="None",
                help="All snapshots containing this string, will be deleted on source before replication")
    _parser.add_argument('--list-sources', action="store_true", help="List replication enables resources on source server and exit")
    _parser.add_argument('--keep', type=str, help="Clone after run and keep x numbers of clones")
    _parser.add_argument('--keep-count', type=int, default=0, help="Clone after run and keep x numbers of clones")
    _parser.add_argument('--verbose',action="store_true", help="Verbose output")
    args    =   _parser.parse_args()

    if args.list_sources and (not args.source_server):
        _parser.error("When --list-sources, --source-server is required.")

    if args.keep and (not args.keep_count):
        _parser.error("When --keep, --keep-count is required.")

    #print(args.__dict__)
    replicator = IncusReplicator(**args.__dict__)
    replicator.invoke()