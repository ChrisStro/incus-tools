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

def get_remote_instances(remote_server):
    p = subprocess.run(["incus","ls",f"{ remote_server }:","-cn","-fjson","user.repl-instance=true"], capture_output=True, text=True)
    if not p.stdout.splitlines():
        raise RuntimeError(f"ERROR: Could not get any instances on { remote_server }")
    return json.loads(p.stdout)

class IncusReplicator():
    def __init__(self,remote_server,instances: list,repl_prefix,target_project):
        self.instances      = instances
        self.remote_server  = remote_server
        self.repl_prefix    = repl_prefix
        self.target_project = target_project

    def check_local_repl(self, instance_name):
        p = subprocess.run(["incus","ls","-cn","-fcsv",f"{ self.repl_prefix }--{ instance_name }",f"--all-projects",f"project={ self.target_project }"], capture_output=True, text=True)
        return bool(p.stdout.strip())

    def init_repl(self, instance_name, instance_type):
        if instance_type == "container":
            logging.warning(f"Container { instance_name } must be stopped before initial replication")
            subprocess.run(["incus","stop",f"{self.remote_server}:{instance_name}"], capture_output=True, text=True)

        logging.info(f"Initial replication for { instance_name }")
        p = subprocess.run(["incus","copy",f"{self.remote_server}:{instance_name}",f"{ self.repl_prefix}--{instance_name}",f"--target-project={ self.target_project }"], capture_output=True, text=True)

        if instance_type == "container":
            logging.info(f"Starting { instance_name } after replication")
            subprocess.run(["incus","start",f"{self.remote_server}:{instance_name}"], capture_output=True, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"ERROR[INIT]: {instance_name}: {p.stderr}")

    def refresh_repl(self, instance_name):
        logging.info(f"Update replication for { instance_name }")
        p = subprocess.run(["incus","copy",f"{self.remote_server}:{instance_name}",f"{ self.repl_prefix}--{instance_name}",f"--target-project={ self.target_project }","--refresh","--refresh-exclude-older","-c","boot.autostart=false"], capture_output=True, text=True)

        if p.returncode != 0:
            raise RuntimeError(f"ERROR[REFRESH]: {instance_name}: {p.stderr}")

    def _invoke_repl(self, instance):
        instance_type = instance['type']
        instance_name = instance['name']
        self.refresh_repl(instance_name) if self.check_local_repl(instance_name) else self.init_repl(instance_name,instance_type)

    def invoke(self):
        [self._invoke_repl(instance) for instance in self.instances]


if __name__ == "__main__":
    _parser = argparse.ArgumentParser(description="Python script creating incus snapshots")
    _parser.add_argument('--remote-server',type=str, required=True,
                help="Remote source server")
    _parser.add_argument('--repl-prefix',type=str, required=True,
                help="Prefix instance name with entered value")
    _parser.add_argument('--target-project',type=str,default='default',
                help="Replicate instances to following project on local incus node")
    _parser.add_argument('-v','--verbose',action="store_true", help="Verbose output")
    args    =   _parser.parse_args()

    all_instances = get_remote_instances(args.remote_server)
    #all_instances = '[{"name": "c1", "type": "container"}]'
    replicator = IncusReplicator(args.remote_server,all_instances,args.repl_prefix,args.target_project)
    replicator.invoke()