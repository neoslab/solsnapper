# === Import libraries ===
import argparse
import glob
import json
import logging
import math
import os
import requests
import shutil
import statistics
import subprocess
import sys
import time

# === Import packages ===
from multiprocessing.dummy import Pool as ThreadPool
from pathlib import Path
from requests import ConnectionError
from requests import ConnectTimeout
from requests import HTTPError
from requests import ReadTimeout
from requests import Timeout
from tqdm import tqdm


# === Class 'SolanaSnapper' ===
class SolanaSnapper:
    """
    The SolanaSnapper class is designed to scan and evaluate Solana RPC nodes for usable snapshot files.
    It automates the discovery, filtering, and downloading of snapshot archives based on slot age, latency,
    and version constraints. This tool is particularly useful for blockchain node operators and developers
    who need to bootstrap a validator or full node using the most recent and optimal snapshot available.

    Parameters:
    - None (all configuration is loaded through command-line arguments and internal defaults)

    Returns:
    - None
    """

    # === Function '__init__' ===
    def __init__(self):
        """
        Initializes the SolanaSnapper instance by setting up argument parsing, configuration loading,
        logging, and snapshot discovery. It also performs internal preparation such as fetching local
        snapshots, assigning runtime variables, and configuring attributes to avoid linter issues.

        Parameters:
        - None

        Returns:
        - None
        """
        # --- Argument parser ---
        self.parser = argparse.ArgumentParser(description='Solana snapshot finder')
        self.initagrs()
        self.args = self.parser.parse_args()
        self.defaultheaders = None
        self.hostrpc = None
        self.specificslot = None
        self.specificversion = None
        self.wildcardversion = None
        self.maxsnapshotage = 0
        self.withprivaterpc = False
        self.retryprivaterpc = False
        self.threadscount = 0
        self.mindownloadspeed = 0
        self.maxdownloadspeed = None
        self.speedmeasuretime = 0
        self.maxlatency = 0
        self.snapshotpath = ""
        self.nbrmaxattempts = 0
        self.waitretry = 0
        self.nbrinitattempts = 1
        self.sortorder = ""
        self.blacklisted = []
        self.hostbanned = []
        self.localsnapslot = 0
        self.timeslot = 0
        self.localsnapshot = []
        self.discardtype = 0
        self.discardlatency = 0
        self.discardslot = 0
        self.discardversion = 0
        self.discarderrors = 0
        self.discardtimeout = 0
        self.badservers = set()
        self.wgetpath = shutil.which("wget")
        self.initconfig()
        self.logger = None
        self.initlogging()

        # --- Snapshot metadata holder ---
        self.jsondata = {
            "last_update_at": 0.0,
            "last_update_slot": 0,
            "total_rpc_nodes": 0,
            "rpc_nodes_with_actual_snapshot": 0,
            "rpc_nodes": []
        }

        # --- Progress bar holder ---
        self.pbar = None

        # --- Detect existing local snapshots ---
        self.localsnapshot = glob.glob(f'{self.snapshotpath}/snapshot-*tar*')
        if self.localsnapshot:
            self.localsnapshot.sort(reverse=True)
            try:
                self.localsnapslot = int(self.localsnapshot[0].split("-")[1].split(".")[0])
            except (IndexError, ValueError):
                self.localsnapslot = 0

    # === Function 'initagrs' ===
    def initagrs(self):
        """
        Configures and registers all command-line arguments required for SolanaSnapper to operate.
        This includes parameters for threading, snapshot age, download speed, latency, RPC filtering,
        snapshot paths, and verbosity. These inputs drive the filtering logic and download behavior
        for selecting the optimal snapshot host from the Solana RPC cluster.

        Parameters:
        - None (modifies self.parser in place)

        Returns:
        - None
        """
        self.parser.add_argument(
            '-t',
            '--threads-count',
            default=1000,
            type=int,
            help='the number of concurrently running threads that check snapshots for rpc nodes'
        )

        self.parser.add_argument(
            '-r',
            '--rpcaddress',
            default='https://api.mainnet-beta.solana.com',
            type=str,
            help='RPC address of the node from which the current slot number will be taken'
        )

        self.parser.add_argument(
            '--slot',
            default=0,
            type=int,
            help='search for a snapshot with a specific slot number'
        )

        self.parser.add_argument(
            '--version',
            default=None,
            help='search for a snapshot from a specific version node'
        )

        self.parser.add_argument(
            '--wildcard_version',
            default=None,
            help='search for a snapshot with a major/minor version e.g. 1.18'
        )

        self.parser.add_argument(
            '--max_snapshot_age',
            default=5000,
            type=int,
            help='How many slots ago the snapshot was created'
        )

        self.parser.add_argument(
            '--min_download_speed',
            default=30,
            type=int,
            help='Minimum average snapshot download speed in megabytes'
        )

        self.parser.add_argument(
            '--max_download_speed',
            type=int,
            help='Maximum snapshot download speed in megabytes'
        )

        self.parser.add_argument(
            '--max_latency',
            default=200,
            type=int,
            help='The maximum value of latency (milliseconds)'
        )

        self.parser.add_argument(
            '--with_private_rpc',
            action='store_true',
            help='Enable adding and checking RPCs with private RPC option'
        )

        self.parser.add_argument(
            '--measurement_time',
            default=7,
            type=int,
            help='Time in seconds to measure download speed'
        )

        self.parser.add_argument(
            '--snapshot_path',
            type=str,
            default='.',
            help='Absolute path where snapshot will be downloaded'
        )

        self.parser.add_argument(
            '--num_of_retries',
            default=10,
            type=int,
            help='Number of retries if suitable server not found'
        )

        self.parser.add_argument(
            '--sleep',
            default=7,
            type=int,
            help='Sleep before next retry (seconds)'
        )

        self.parser.add_argument(
            '--sort_order',
            default='latency',
            type=str,
            help='Priority way to sort servers (latency or slotdiff)'
        )

        self.parser.add_argument(
            '-ipb',
            '--ip_blacklist',
            default='',
            type=str,
            help='Comma separated list of blacklisted ip:port'
        )

        self.parser.add_argument(
            '-b',
            '--blacklist',
            default='',
            type=str,
            help='Blacklisted slot numbers or archive hashes'
        )

        self.parser.add_argument(
            '-v',
            '--verbose',
            action='store_true',
            help='Increase output verbosity to DEBUG'
        )

    # === Function 'initconfig' ===
    def initconfig(self):
        """
        Loads configuration values based on the parsed command-line arguments and stores them into
        instance attributes. It processes values for snapshot constraints, speed/latency thresholds,
        retries, blacklists, and directory paths. This internal function is essential to prepare the
        runtime environment before beginning RPC checks and snapshot downloads.

        Parameters:
        - None (uses self.args for input)

        Returns:
        - None
        """
        self.defaultheaders = {"Content-Type": "application/json"}
        self.hostrpc = self.args.rpcaddress
        self.specificslot = int(self.args.slot)
        self.specificversion = self.args.version
        self.wildcardversion = self.args.wildcard_version
        self.maxsnapshotage = 0 if self.args.slot != 0 else self.args.max_snapshot_age
        self.withprivaterpc = self.args.with_private_rpc
        self.retryprivaterpc = False  # will be set to True later if needed
        self.threadscount = self.args.threads_count
        self.mindownloadspeed = self.args.min_download_speed
        self.maxdownloadspeed = self.args.max_download_speed
        self.speedmeasuretime = self.args.measurement_time
        self.maxlatency = self.args.max_latency
        self.snapshotpath = self.args.snapshot_path.rstrip('/')
        self.nbrmaxattempts = self.args.num_of_retries
        self.waitretry = self.args.sleep
        self.nbrinitattempts = 1
        self.sortorder = self.args.sort_order
        self.blacklisted = str(self.args.blacklist).split(",") if self.args.blacklist else []
        self.hostbanned = str(self.args.ip_blacklist).split(",") if self.args.ip_blacklist else []

    # === Function 'initlogging' ===
    def initlogging(self):
        """
        Initializes the logging system for SolanaSnapper using Python's built-in logging module.
        It configures log level based on verbosity flags, outputs logs to both a file and stdout,
        and suppresses verbose urllib3 logging. This allows detailed traceability and debugging
        during snapshot discovery and downloading.

        Parameters:
        - None (uses self.args to determine log level)

        Returns:
        - None
        """
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        loglevel = logging.DEBUG if self.args.verbose else logging.INFO
        logging.basicConfig(level=loglevel, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.FileHandler(f'{self.snapshotpath}/snapshot.log'), logging.StreamHandler(sys.stdout)])
        self.logger = logging.getLogger(__name__)

    # === Function 'sizeconv' ===
    @staticmethod
    def sizeconv(sizebytes):
        """
        Converts a size in bytes into a human-readable string using binary units (e.g., KB, MB, GB).
        This function is typically used to present download speeds or file sizes in logs or console
        output, offering better readability for operators evaluating node performance.

        Parameters:
        - sizebytes (int): The number of bytes to convert.

        Returns:
        - str: A human-readable file size string (e.g., "12.5 MB").
        """
        if sizebytes == 0:
            return "0B"
        sizename = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(sizebytes, 1024)))
        p = math.pow(1024, i)
        s = round(sizebytes / p, 2)
        return "%s %s" % (s, sizename[i])

    # === Function 'speedtest' ===
    def speedtest(self, url: str, measuretime: int) -> float:
        """
        Measures the approximate download speed (in bytes/second) of a snapshot file from the
        provided RPC address. It streams the content for a fixed duration and calculates transfer
        speed based on chunk size and elapsed time. The result is used to decide if an RPC node
        is suitable for downloading the snapshot.

        Parameters:
        - url (str): RPC endpoint address.
        - measuretime (int): Duration to stream data for speed calculation in seconds.

        Returns:
        - float: Estimated download speed in bytes/second. Returns 0 on error or timeout.
        """
        self.logger.debug('speedtest()')

        # noinspection HttpUrlsUsage
        url = f'http://{url}/snapshot.tar.bz2'
        try:
            r = requests.get(url, stream=True, timeout=measuretime+2)
            r.raise_for_status()
            timestart = time.monotonic_ns()
            timestop = timestart
            loaded = 0
            speeds = []
            for chunk in r.iter_content(chunk_size=81920):
                curtime = time.monotonic_ns()
                worktime = (curtime - timestart) / 1000000000
                if worktime >= measuretime:
                    break
                delta = (curtime - timestop) / 1000000000
                loaded += len(chunk)
                if delta > 1:
                    bytesbysecond = loaded * (1 / delta)
                    speeds.append(bytesbysecond)
                    timestop = curtime
                    loaded = 0
            return statistics.median(speeds) if speeds else 0
        except Exception as e:
            self.logger.debug(f'Error in speedtest: {e}')
            return 0

    # === Function 'fetchrequest' ===
    def fetchrequest(self, s_url: str, s_method: str = 'GET', s_data: str = '', s_timeout: int = 3, s_headers: dict = None):
        """
        Performs an HTTP request using the specified method, headers, and timeout settings.
        It supports GET, POST, and HEAD requests and returns the response object or None on failure.
        The function also increments discard counters and logs errors when exceptions occur during
        request attempts.

        Parameters:
        - s_url (str): The target URL for the request.
        - s_method (str): HTTP method ('GET', 'POST', or 'HEAD').
        - s_data (str): Payload for POST requests.
        - s_timeout (int): Timeout in seconds.
        - s_headers (dict): Optional HTTP headers.

        Returns:
        - requests.Response | None: The response object if successful, or None on error.
        """
        r = None
        if s_headers is None:
            s_headers = self.defaultheaders
        try:
            if s_method.lower() == 'get':
                r = requests.get(s_url, headers=s_headers, timeout=(s_timeout, s_timeout))
            elif s_method.lower() == 'post':
                r = requests.post(s_url, headers=s_headers, data=s_data, timeout=(s_timeout, s_timeout))
            elif s_method.lower() == 'head':
                r = requests.head(s_url, headers=s_headers, timeout=(s_timeout, s_timeout))
            return r
        except (ReadTimeout, ConnectTimeout, HTTPError, Timeout, ConnectionError) as reqErr:
            self.discardtimeout += 1
            self.logger.debug(f'Error in fetchrequest: {reqErr}')
            return None
        except Exception as unknwErr:
            self.discarderrors += 1
            self.logger.debug(f'Unknown error in fetchrequest: {unknwErr}')
            return None

    # === Function 'currentslot' ===
    def currentslot(self):
        """
        Retrieves the latest Solana slot number from the configured RPC endpoint by issuing a
        JSON-RPC request using 'getSlot'. If the response is valid, the slot number is extracted
        and returned. Errors are logged appropriately, and None is returned if the request fails.

        Parameters:
        - None

        Returns:
        - int | None: The latest Solana slot number, or None if the request fails.
        """
        self.logger.debug("currentslot()")
        d = '{"jsonrpc":"2.0","id":1, "method":"getSlot"}'
        try:
            r = self.fetchrequest(s_url=self.hostrpc, s_method='post', s_data=d, s_timeout=25)
            if r and 'result' in r.text:
                return r.json()["result"]
            else:
                self.logger.error('Can\'t get current slot')
                if r:
                    self.logger.debug(f'Status code: {r.status_code}')
                return None
        except Exception as e:
            self.logger.error(f'Can\'t get current slot: {e}')
            return None

    # === Function 'rpchosts' ===
    def rpchosts(self):
        """
        Fetches the list of available Solana RPC nodes by querying the 'getClusterNodes' endpoint.
        Filters out nodes based on version constraints and blacklists. If enabled, it includes
        private RPCs derived from gossip IPs. The resulting list is used to test for snapshots.

        Parameters:
        - None

        Returns:
        - list[str]: A list of RPC node addresses that meet the version and blacklist criteria.
        """
        self.logger.debug("rpchosts()")
        d = '{"jsonrpc":"2.0", "id":1, "method":"getClusterNodes"}'
        r = self.fetchrequest(s_url=self.hostrpc, s_method='post', s_data=d, s_timeout=25)
        if r and 'result' in r.text:
            rpcips = []
            for node in r.json()["result"]:
                if (self.wildcardversion is not None and node.get("version") and self.wildcardversion not in node["version"]) or \
                   (self.specificversion is not None and node.get("version") and node["version"] != self.specificversion):
                    self.discardversion += 1
                    continue
                if node.get("rpc"):
                    rpcips.append(node["rpc"])
                elif self.withprivaterpc or self.retryprivaterpc:
                    gossiphost = node["gossip"].split(":")[0]
                    rpcips.append(f'{gossiphost}:8899')
            rpcips = list(set(rpcips))
            self.logger.debug(f'RPC_IPS LEN before blacklisting: {len(rpcips)}')
            if self.hostbanned and self.hostbanned != ['']:
                rpcips = list(set(rpcips) - set(self.hostbanned))
            self.logger.debug(f'RPC_IPS LEN after blacklisting: {len(rpcips)}')
            return rpcips
        else:
            self.logger.error(f'Can\'t get RPC ip addresses: {r.text if r else "No response"}')
            sys.exit()

    # === Function 'snapshotslot' ===
    def snapshotslot(self, rpcaddress: str):
        """
        Evaluates whether a given RPC node hosts a suitable snapshot for download. It checks for
        both full and incremental snapshot availability, slot age compliance, latency, and archive
        type. If valid, it appends the node's metadata to the internal snapshot list for later use.

        Parameters:
        - rpcaddress (str): IP address or domain of the RPC node.

        Returns:
        - None
        """
        if self.pbar:
            self.pbar.update(1)

        # noinspection HttpUrlsUsage
        baseurl = f'http://{rpcaddress}/snapshot.tar.bz2'

        # noinspection HttpUrlsUsage
        incurl = f'http://{rpcaddress}/incremental-snapshot.tar.bz2'
        try:
            r = self.fetchrequest(s_url=incurl, s_method='head', s_timeout=1)
            if r and 'location' in r.headers and 'error' not in r.text and r.elapsed.total_seconds() * 1000 > self.maxlatency:
                self.discardlatency += 1
                return None
            if r and 'location' in r.headers and 'error' not in r.text:
                snappathloc = r.headers["location"]
                if snappathloc.endswith('tar'):
                    self.discardtype += 1
                    return None
                incsnapslot = int(snappathloc.split("-")[2])
                snapslotbase = int(snappathloc.split("-")[3])
                slotdiff = self.timeslot - snapslotbase
                if slotdiff < -100:
                    self.logger.error(f'Something wrong with snapshot\\rpc_node - {slotdiff=}. Skipping {rpcaddress=}')
                    self.discardslot += 1
                    return None
                if slotdiff > self.maxsnapshotage:
                    self.discardslot += 1
                    return None
                if str(self.localsnapslot) == str(incsnapslot):
                    self.jsondata["rpc_nodes"].append({
                        "snapshot_address": rpcaddress,
                        "slotdiff": slotdiff,
                        "latency": r.elapsed.total_seconds() * 1000,
                        "files_to_download": [snappathloc]
                    })
                    return None
                r2 = self.fetchrequest(s_url=baseurl, s_method='head', s_timeout=1)
                if r2 and 'location' in r2.headers and 'error' not in r.text:
                    self.jsondata["rpc_nodes"].append({
                        "snapshot_address": rpcaddress,
                        "slotdiff": slotdiff,
                        "latency": r.elapsed.total_seconds() * 1000,
                        "files_to_download": [snappathloc, r2.headers['location']],
                    })
                    return None
            r = self.fetchrequest(s_url=baseurl, s_method='head', s_timeout=1)
            if r and 'location' in r.headers and 'error' not in r.text:
                snappathloc = r.headers["location"]
                if snappathloc.endswith('tar'):
                    self.discardtype += 1
                    return None
                full_snapslotbase = int(snappathloc.split("-")[1])
                slotdiff_full = self.timeslot - full_snapslotbase
                if slotdiff_full <= self.maxsnapshotage and r.elapsed.total_seconds() * 1000 <= self.maxlatency:
                    self.jsondata["rpc_nodes"].append({
                        "snapshot_address": rpcaddress,
                        "slotdiff": slotdiff_full,
                        "latency": r.elapsed.total_seconds() * 1000,
                        "files_to_download": [snappathloc]
                    })
                    return None
            return None
        except Exception as e:
            self.logger.debug(f'Error in snapshotslot: {e}')
            return None

    # === Function 'download' ===
    def download(self, url: str):
        """
        Downloads a snapshot file from the specified URL using the wget command-line tool.
        It optionally limits download speed and renames the temporary file upon success.
        Any errors encountered during execution are logged, including missing wget utility.

        Parameters:
        - url (str): Direct URL to the snapshot archive file.

        Returns:
        - None
        """
        fname = url[url.rfind('/')+1:]
        tmpsnap = f'{self.snapshotpath}/tmp-{fname}'
        try:
            cmd = [self.wgetpath, '--progress=dot:giga', '--trust-server-names', url, f'-O{tmpsnap}']
            if self.maxdownloadspeed is not None:
                cmd.insert(2, f'--limit-rate={self.maxdownloadspeed}M')
            subprocess.run(cmd, stdout=subprocess.PIPE, universal_newlines=True)
            self.logger.info(f'Rename the downloaded file to {fname}')
            os.rename(tmpsnap, f'{self.snapshotpath}/{fname}')
        except Exception as e:
            self.logger.error(f'Exception in download: {e}. Ensure wget is installed')

    # === Function 'workers' ===
    def workers(self):
        """
        The main routine that coordinates snapshot discovery, speed testing, filtering, and
        downloading. It uses threading to concurrently query RPC nodes, validates snapshot
        metadata, applies performance filters, and persists results to disk. The first suitable
        snapshot found is downloaded. Retries and summary stats are logged throughout the process.

        Parameters:
        - None

        Returns:
        - int: 0 if a snapshot was successfully downloaded, 1 otherwise.
        """
        try:
            rpc_nodes = list(set(self.rpchosts()))
            self.pbar = tqdm(total=len(rpc_nodes))
            self.logger.info(f'RPC servers in total: {len(rpc_nodes)} | Current slot number: {self.timeslot}\n')

            if self.localsnapshot:
                self.logger.info(f'Found full local snapshot {self.localsnapshot[0]} | {self.localsnapslot=}')
            else:
                self.logger.info(f'No full local snapshots in {self.snapshotpath}')

            self.logger.info('Searching information about snapshots on all found RPCs')
            with ThreadPool(self.threadscount) as pool:
                pool.map(self.snapshotslot, rpc_nodes)

            self.pbar.close()
            self.logger.info(f'Found suitable RPCs: {len(self.jsondata["rpc_nodes"])}')
            self.logger.info(f'Skipped RPCs: {self.discardtype=} | {self.discardlatency=} | 'f'{self.discardslot=} | {self.discardversion=} | 'f'{self.discardtimeout=} | {self.discarderrors=}')
            if not self.jsondata["rpc_nodes"]:
                self.logger.info(f'No snapshot nodes found matching parameters: {self.args.max_snapshot_age=}')
                return 1

            rpc_nodes_sorted = sorted(self.jsondata["rpc_nodes"], key=lambda k: k[self.sortorder])
            self.jsondata.update({
                "last_update_at": time.time(),
                "last_update_slot": self.timeslot,
                "total_rpc_nodes": len(rpc_nodes),
                "rpc_nodes_with_actual_snapshot": len(self.jsondata["rpc_nodes"]),
                "rpc_nodes": rpc_nodes_sorted
            })
            with open(f'{self.snapshotpath}/snapshot.json', "w") as result_f:
                json.dump(self.jsondata, result_f, indent=2)
            self.logger.info(f'All data saved to {self.snapshotpath}/snapshot.json')

            snapshotmode = None
            num_of_rpc_to_check = 15
            self.logger.info("TRYING TO DOWNLOAD FILES")
            for i, rpc_node in enumerate(self.jsondata["rpc_nodes"], start=1):
                if i > num_of_rpc_to_check:
                    self.logger.info(f'RPC node check limit reached {num_of_rpc_to_check=}')
                    break
                if self.blacklisted and self.blacklisted != ['']:
                    if any(b in str(rpc_node["files_to_download"]) for b in self.blacklisted):
                        self.logger.info(f'{i}/{len(self.jsondata["rpc_nodes"])} blacklisted --> {rpc_node}')
                        continue
                self.logger.info(f'{i}/{len(self.jsondata["rpc_nodes"])} checking speed {rpc_node}')
                if rpc_node["snapshot_address"] in self.badservers:
                    self.logger.info(f'Rpc node in unsuitable list --> skip {rpc_node["snapshot_address"]}')
                    continue
                    
                downspeedbytes = self.speedtest(url=rpc_node["snapshot_address"], measuretime=self.speedmeasuretime)
                downspeedmb = self.sizeconv(downspeedbytes)
                if downspeedbytes < self.mindownloadspeed * 1e6:
                    self.logger.info(f'Too slow: {rpc_node=} {downspeedmb=}')
                    self.badservers.add(rpc_node["snapshot_address"])
                    continue
                self.logger.info(f'Suitable snapshot server found: {rpc_node=} {downspeedmb=}')
                for path in reversed(rpc_node["files_to_download"]):
                    if str(path).startswith("/snapshot-"):
                        full_snapslotbase = path.split("-")[1]
                        if full_snapslotbase == str(self.localsnapslot):
                            continue
                    if 'incremental' in path:
                        # noinspection HttpUrlsUsage
                        r = self.fetchrequest(f'http://{rpc_node["snapshot_address"]}/incremental-snapshot.tar.bz2', s_method='head', s_timeout=2)

                        if r and 'location' in r.headers and 'error' not in r.text:
                            # noinspection HttpUrlsUsage
                            snapshotmode = f'http://{rpc_node["snapshot_address"]}{r.headers["location"]}'
                        else:
                            # noinspection HttpUrlsUsage
                            snapshotmode = f'http://{rpc_node["snapshot_address"]}{path}'
                    else:
                        # noinspection HttpUrlsUsage
                        snapshotmode = f'http://{rpc_node["snapshot_address"]}{path}'
                    self.logger.info(f'Downloading {snapshotmode} snapshot to {self.snapshotpath}')
                    self.download(url=snapshotmode)
                if snapshotmode:
                    return 0

            if not snapshotmode:
                self.logger.error(f'No snapshot nodes found matching parameters: {self.args.min_download_speed=}\n'
                                  f'Try restarting with --with_private_rpc\n'
                                  f'RETRY #{self.nbrinitattempts}/{self.nbrmaxattempts}')
                return 1

        except KeyboardInterrupt:
            self.logger.info('Interrupted by user')
            sys.exit(1)
        except Exception as e:
            self.logger.error(f'Error in workers: {e}')
            return 1

    # === Function 'run' ===
    def run(self):
        """
        Entry point for executing the SolanaSnapper workflow. It validates the output path, ensures
        required tools like wget are present, determines the current slot, and initiates snapshot
        discovery using worker threads. It supports retries and can optionally include private RPCs
        in its search. Logs comprehensive progress and error messages throughout execution.

        Parameters:
        - None

        Returns:
        - None (Exits the program with status 0 or 1 based on success/failure)
        """
        self.logger.info("Version: 0.3.9")
        self.logger.info("https://github.com/neoslab/solanasnapper\n")
        self.logger.info(f'{self.hostrpc=}\n{self.maxsnapshotage=}\n{self.mindownloadspeed=}\n'
                         f'{self.maxdownloadspeed=}\n{self.snapshotpath=}\n{self.threadscount=}\n'
                         f'{self.nbrmaxattempts=}\n{self.withprivaterpc=}\n{self.sortorder=}')

        try:
            Path(self.snapshotpath).mkdir(parents=True, exist_ok=True)
            testfile = Path(self.snapshotpath) / 'write_perm_test'
            testfile.touch()
            testfile.unlink()
        except IOError as e:
            self.logger.error(f'Check {self.snapshotpath=} and permissions: {e}')
            sys.exit(1)

        if not self.wgetpath:
            self.logger.error("wget utility not found, it is required")
            sys.exit(1)

        while self.nbrinitattempts <= self.nbrmaxattempts:
            if self.specificslot != 0 and isinstance(self.specificslot, int):
                self.timeslot = self.specificslot
            else:
                self.timeslot = self.currentslot()

            if self.timeslot is None:
                self.nbrinitattempts += 1
                self.logger.info(f'Failed to get current slot, retrying ({self.nbrinitattempts}/{self.nbrmaxattempts})')
                time.sleep(self.waitretry)
                continue

            self.logger.info(f'Attempt number: {self.nbrinitattempts}/{self.nbrmaxattempts}')
            self.nbrinitattempts += 1

            workresp = self.workers()
            if workresp == 0:
                self.logger.info("Done")
                sys.exit(0)

            self.logger.info("Trying with --with_private_rpc")
            self.retryprivaterpc = True

            if self.nbrinitattempts > self.nbrmaxattempts:
                self.logger.error('Could not find a suitable snapshot, exiting')
                sys.exit(1)

            self.logger.info(f"Sleeping {self.waitretry} seconds before next try")
            time.sleep(self.waitretry)


# === Main Callback ===
if __name__ == "__main__":
    """ 
    Executes the SolanaSnapper script when run as a standalone application. 
    It instantiates the SolanaSnapper class and starts the main run routine 
    for snapshot discovery and download. The main guard ensures safe import 
    behavior if used as a module.

    Parameters:
    - None

    Returns:
    - None
    """
    snapshot_finder = SolanaSnapper()
    snapshot_finder.run()