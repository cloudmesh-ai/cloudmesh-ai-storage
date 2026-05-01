import os
import hashlib
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Callable, Optional
from cloudmesh.ai.common.io import console

class StorageManager:
    """
    Handles the logic for finding and recording equivalent directory trees on a file system.
    """

    def __init__(self):
        self.config_dir = Path.home() / ".config" / "cloudmesh" / "storage"
        self.storage_file = self.config_dir / "equivalencies.yaml"

    def get_file_hash(self, path: Path) -> str:
        """Computes the SHA256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(path, "rb") as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError):
            return "error"

    def get_dir_signature(self, path: Path) -> Tuple:
        """
        Computes a signature for a directory based on its contents.
        The signature is a sorted tuple of (name, type, hash/signature).
        This ensures that directories are only equivalent if they have the 
        exact same set of files and subdirectories with identical content.
        """
        entries = []
        try:
            for item in sorted(path.iterdir()):
                if item.is_file():
                    entries.append((item.name, "file", self.get_file_hash(item)))
                elif item.is_dir():
                    # For directories, we use their own signature recursively
                    entries.append((item.name, "dir", self.get_dir_signature(item)))
        except (OSError, IOError):
            return ("error",)
        
        return tuple(entries)

    def _load_storage_data(self) -> Dict:
        """Helper to load the storage YAML file."""
        if not self.storage_file.exists():
            return {"equivalencies": {}, "candidates": {}}
        try:
            with open(self.storage_file, "r") as f:
                data = yaml.safe_load(f) or {}
                # Ensure the expected structure exists
                if "equivalencies" not in data:
                    data["equivalencies"] = {}
                if "candidates" not in data:
                    data["candidates"] = {}
                return data
        except Exception:
            return {"equivalencies": {}, "candidates": {}}

    def save_equivalency(self, group: List[str]):
        """Saves a group of equivalent directories to the config file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = self._load_storage_data()
        
        # Use the first path as the key for the group
        key = group[0]
        data["equivalencies"][key] = group[1:]
        
        with open(self.storage_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def get_dir_metadata(self, path: Path) -> Dict:
        """
        Calculates directory metadata (size, file count, dir count) using CLI tools for speed.
        """
        metadata = {"size": -1, "files": 0, "dirs": 0}
        try:
            # 1. Get size using du -sk
            size_res = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True, check=True)
            metadata["size"] = int(size_res.stdout.split()[0]) * 1024

            # 2. Get file count
            file_res = subprocess.run(["find", str(path), "-type", "f"], capture_output=True, text=True, check=True)
            metadata["files"] = len(file_res.stdout.splitlines())

            # 3. Get dir count
            dir_res = subprocess.run(["find", str(path), "-type", "d"], capture_output=True, text=True, check=True)
            metadata["dirs"] = len(dir_res.stdout.splitlines())

        except (subprocess.CalledProcessError, FileNotFoundError, IndexError, ValueError):
            # Fallback to Python
            try:
                total_size = 0
                files = 0
                dirs = 0
                for entry in path.rglob('*'):
                    if entry.is_file():
                        total_size += entry.stat().st_size
                        files += 1
                    elif entry.is_dir():
                        dirs += 1
                metadata.update({"size": total_size, "files": files, "dirs": dirs})
            except (OSError, IOError):
                pass
        
        return metadata

    def save_candidates(self, name: str, candidates_data: Any):
        """
        Saves candidate directories to the config file.
        candidates_data can be a List[str] (paths only) or Dict[str, int] (paths and sizes).
        """
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = self._load_storage_data()
        
        data["candidates"][name] = candidates_data
        
        with open(self.storage_file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def find_directories_by_name(self, root_dir: Path, target_name: str) -> List[Path]:
        """
        Finds all directories under root_dir that have the specified basename.
        Tries mdfind (Spotlight) first for near-instant results on macOS, 
        then falls back to 'find', and finally to Python's os.walk.
        """
        # 1. Try mdfind (macOS Spotlight) - Near Instant
        try:
            # Query for folders with the exact name
            # kMDItemFSName is the filename, kMDItemContentType == 'public.folder' ensures it's a directory
            query = f"kMDItemFSName == '{target_name}' && kMDItemContentType == 'public.folder'"
            result = subprocess.run(
                ["mdfind", query],
                capture_output=True,
                text=True,
                check=True
            )
            paths = result.stdout.splitlines()
            # Filter results to ensure they are actually under the root_dir
            matches = [Path(p) for p in paths if p and Path(p).absolute().is_relative_to(root_dir.absolute())]
            if matches:
                return matches
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass # Fall back to 'find'

        # 2. Try 'find' command - Fast
        try:
            result = subprocess.run(
                ["find", str(root_dir), "-type", "d", "-name", target_name],
                capture_output=True,
                text=True,
                check=True
            )
            paths = result.stdout.splitlines()
            return [Path(p) for p in paths if p]
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            console.warning(f"CLI search failed, falling back to Python walk: {e}")
            
            # 3. Fallback to Python walk - Slow
            matches = []
            for dirpath, dirnames, filenames in os.walk(root_dir):
                if Path(dirpath).name == target_name:
                    matches.append(Path(dirpath))
            return matches

    def find_equivalent_directories(self, root_dir: Path, 
                                   on_scan_progress: Optional[Callable[[int], None]] = None,
                                   on_compare_progress: Optional[Callable[[int], None]] = None,
                                   on_match_found: Optional[Callable[[str, List[str]], None]] = None):
        """
        Main logic to find equivalent directories.
        """
        # 1. Find all directories and group them by name
        name_map: Dict[str, List[Path]] = {}
        
        for dirpath, dirnames, filenames in os.walk(root_dir):
            path = Path(dirpath)
            name = path.name
            if name not in name_map:
                name_map[name] = []
            name_map[name].append(path)
            if on_scan_progress:
                on_scan_progress(1)
        
        # 2. Compare directories with the same name
        candidate_names = [name for name, paths in name_map.items() if len(paths) >= 2]
        
        for name in candidate_names:
            paths = name_map[name]
            
            # Group paths by their signature
            signatures: Dict[Tuple, List[str]] = {}
            for path in paths:
                sig = self.get_dir_signature(path)
                sig_str = str(sig)
                if sig_str not in signatures:
                    signatures[sig_str] = []
                signatures[sig_str].append(str(path))
                
            # 3. Write matches to file as soon as they are found
            for sig, group in signatures.items():
                if len(group) > 1:
                    if on_match_found:
                        on_match_found(name, group)
                    self.save_equivalency(group)
            
            if on_compare_progress:
                on_compare_progress(1)