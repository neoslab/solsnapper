# SolSnapper - Python Based Solana Snapshot Finder

![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**SolSnapper** is a Python-based tool designed to automate the discovery, evaluation, and downloading of Solana blockchain snapshot files from RPC nodes. It helps node operators and developers bootstrap Solana validators or full nodes by identifying the most recent and optimal snapshots based on slot age, latency, download speed, and version constraints. The tool leverages multithreading for efficient scanning and provides detailed logging for debugging and monitoring.

This project is a fork and enhancement of the original [solana-snapshot-finder](https://github.com/c29r3/solana-snapshot-finder) by c29r3, with additional features and optimizations.

* * *

## Features

- **Automated Snapshot Discovery**: Scans Solana RPC nodes to find available snapshot files (full and incremental).
- **Performance Filtering**: Evaluates nodes based on download speed, latency, slot age, and software version.
- **Multithreaded Processing**: Uses concurrent threads to check multiple RPC nodes quickly.
- **Flexible Configuration**: Supports command-line arguments for customizing snapshot age, download speed, latency thresholds, and more.
- **Blacklist Support**: Allows filtering out specific IPs, slots, or archive hashes.
- **Private RPC Inclusion**: Optionally queries private RPC nodes derived from gossip IPs.
- **Comprehensive Logging**: Outputs detailed logs to both file and console for traceability.
- **Progress Tracking**: Displays a progress bar during RPC node scanning.
- **Retry Logic**: Automatically retries failed attempts with configurable sleep intervals.
- **JSON Output**: Saves snapshot metadata to a JSON file for further analysis.

* * *

## Requirements

- **Python**: Version 3.8 or higher
- **Operating System**: Linux, macOS, or Windows (with wget installed)
- **Dependencies**:
  - `argparse`
  - `glob`
  - `json`
  - `logging`
  - `math`
  - `os`
  - `requests`
  - `shutil`
  - `statistics`
  - `subprocess`
  - `sys`
  - `time`
  - `multiprocessing`
  - `pathlib`
  - `tqdm`
- **External Tools**:
  - `wget` (required for downloading snapshots)

Install Python dependencies using:

```bash
pip install requests tqdm
```

Ensure `wget` is installed on your system:
- **Ubuntu/Debian**: `sudo apt-get install wget`
- **macOS**: `brew install wget`
- **Windows**: Download and install `wget` from a trusted source or use a package manager like Chocolatey.

* * *

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/neoslab/solsnapper.git
   cd solsnapper
   ```

2. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Ensure `wget` is installed and accessible in your system's PATH.

* * *

### Usage

Run the script with default settings:

```bash
python main.py
```

* * *

### Command-Line Arguments

| Argument                     | Description                                                                 | Default Value                     |
|------------------------------|-----------------------------------------------------------------------------|-----------------------------------|
| `-t, --threads-count`        | Number of concurrent threads for checking snapshots                         | `1000`                            |
| `-r, --rpcaddress`           | RPC address to fetch the current slot number                               | `https://api.mainnet-beta.solana.com` |
| `--slot`                     | Search for a snapshot with a specific slot number                          | `0` (disabled)                    |
| `--version`                  | Search for snapshots from a specific Solana version                        | `None`                            |
| `--wildcard_version`         | Search for snapshots with a major/minor version (e.g., `1.18`)             | `None`                            |
| `--max_snapshot_age`         | Maximum slot age for snapshots (in slots)                                  | `5000`                            |
| `--min_download_speed`       | Minimum download speed (in MB/s)                                           | `30`                              |
| `--max_download_speed`       | Maximum download speed (in MB/s)                                           | `None`                            |
| `--max_latency`              | Maximum latency for RPC nodes (in milliseconds)                            | `200`                             |
| `--with_private_rpc`         | Enable checking private RPC nodes derived from gossip IPs                  | `False`                           |
| `--measurement_time`         | Time to measure download speed (in seconds)                                | `7`                               |
| `--snapshot_path`            | Absolute path for downloading snapshots                                    | `.` (current directory)           |
| `--num_of_retries`           | Number of retries if no suitable server is found                           | `10`                              |
| `--sleep`                    | Sleep duration between retries (in seconds)                                | `7`                               |
| `--sort_order`               | Sort servers by `latency` or `slotdiff`                                    | `latency`                         |
| `-ipb, --ip_blacklist`       | Comma-separated list of blacklisted IP:port pairs                          | `""`                              |
| `-b, --blacklist`            | Comma-separated list of blacklisted slot numbers or archive hashes         | `""`                              |
| `-v, --verbose`              | Enable verbose (DEBUG) logging                                             | `False`                           |

* * *

### Example Commands

1. Run with default settings but specify a custom snapshot path:

```bash
python main.py --snapshot_path /path/to/snapshots
```

2. Search for a snapshot with a specific slot and verbose logging:

```bash
python main.py --slot 123456789 --verbose
```

3. Filter by Solana version and include private RPCs:

```bash
python main.py --version 1.18.1 --with_private_rpc
```

4. Set custom download speed and latency thresholds:

```bash
python main.py --min_download_speed 50 --max_latency 100
```

* * *

### Output

- **Logs**: Written to both `snapshot-finder.log` in the snapshot path and the console.
- **Snapshot Metadata**: Saved as `snapshot.json` in the snapshot path, containing:
  - Last update timestamp and slot
  - Total RPC nodes scanned
  - Nodes with valid snapshots
  - Detailed node metadata (address, slot difference, latency, files to download)
- **Downloaded Snapshots**: Saved in the specified snapshot path with their original filenames.

* * *

### Troubleshooting

- **"wget utility not found"**: Ensure `wget` is installed and added to your system's PATH.
- **Permission Errors**: Verify write permissions for the specified `snapshot_path`.
- **No Suitable Snapshots Found**:
  - Increase `--max_snapshot_age` or `--min_download_speed`.
  - Enable `--with_private_rpc` to include private RPC nodes.
  - Check network connectivity and RPC address (`--rpcaddress`).
- **High Latency or Timeouts**: Reduce `--threads-count` or increase `--max_latency`.
- **Debugging**: Use `--verbose` for detailed logs to diagnose issues.

* * *

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Make your changes and commit them (`git commit -m "Add your feature"`).
4. Push to your branch (`git push origin feature/your-feature`).
5. Open a pull request with a clear description of your changes.

Ensure your code follows PEP 8 style guidelines and includes appropriate tests.

* * *

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

* * *

## Contact

For any issues, suggestions, or questions regarding the project, please open a new issue on the official GitHub repository or reach out directly to the maintainer through the [GitHub Issues](issues) page for further assistance and follow-up.
